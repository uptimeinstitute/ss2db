"""
Data extractors for Smartsheet sheets and reports with pagination and chunking.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
from datetime import datetime

from ss2db.smartsheet.client import SmartsheetClient, SmartsheetAPIError
from ss2db.smartsheet.models import (
    SmartsheetSchema, SmartsheetRow, SmartsheetColumn, 
    ExtractionProgress, ColumnType
)
from ss2db.utils.logging import get_logger, ProgressLogger


class SmartsheetExtractor:
    """Base class for Smartsheet data extraction."""
    
    def __init__(self, client: SmartsheetClient, config: Optional[Dict[str, Any]] = None):
        self.client = client
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Configuration
        self.chunk_size = self.config.get('chunk_size', 10000)
        self.max_retries = self.config.get('max_retries', 3)
        self.memory_limit_mb = self.config.get('memory_limit_mb', 1024)
        self.validate_data = self.config.get('validate_data', True)
        
    def _estimate_memory_usage(self, row_count: int, column_count: int) -> float:
        """Estimate memory usage in MB for given data size."""
        # Rough estimate: ~500 bytes per cell on average
        bytes_per_cell = 500
        total_bytes = row_count * column_count * bytes_per_cell
        return total_bytes / (1024 * 1024)  # Convert to MB
    
    def _adjust_chunk_size(self, total_rows: int, column_count: int) -> int:
        """Adjust chunk size based on memory limits and data size."""
        if not total_rows or not column_count:
            return self.chunk_size
        
        # Calculate chunk size that fits within memory limit
        memory_per_chunk = self._estimate_memory_usage(self.chunk_size, column_count)
        
        if memory_per_chunk > self.memory_limit_mb:
            # Reduce chunk size to fit memory limit
            adjusted_chunk_size = int((self.memory_limit_mb / memory_per_chunk) * self.chunk_size)
            adjusted_chunk_size = max(100, adjusted_chunk_size)  # Minimum chunk size
            self.logger.info(f"Adjusted chunk size from {self.chunk_size} to {adjusted_chunk_size} "
                           f"to fit memory limit ({self.memory_limit_mb}MB)")
            return adjusted_chunk_size
        
        return self.chunk_size
    
    def _validate_row_data(self, row: SmartsheetRow, schema: SmartsheetSchema) -> bool:
        """Validate row data for consistency and completeness."""
        if not self.validate_data:
            return True
        
        try:
            # Check if row has cells
            if not row.cells:
                self.logger.warning(f"Row {row.id} has no cells")
                return False
            
            # Check for critical data issues
            for cell in row.cells:
                column = schema.get_column_by_id(cell.column_id)
                if not column:
                    continue
                
                # Validate required data types
                if column.type == ColumnType.CHECKBOX and cell.value is not None:
                    if not isinstance(cell.value, bool):
                        try:
                            bool(cell.value)
                        except (ValueError, TypeError):
                            self.logger.warning(f"Invalid boolean value in row {row.id}, column {column.title}: {cell.value}")
                            return False
                
                # Check for extremely long text values
                if isinstance(cell.value, str) and len(cell.value) > 65535:
                    self.logger.warning(f"Text value too long in row {row.id}, column {column.title} ({len(cell.value)} chars)")
                    # Truncate instead of rejecting
                    cell.value = cell.value[:65535]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating row {row.id}: {e}")
            return False


class SheetExtractor(SmartsheetExtractor):
    """Extractor for Smartsheet sheets."""
    
    def extract_schema(self, sheet_id: str) -> SmartsheetSchema:
        """Extract schema information for a sheet."""
        self.logger.info(f"Extracting schema for sheet {sheet_id}")
        
        try:
            # Get sheet metadata (minimal data to get columns)
            response = self.client.get_sheet(sheet_id, include_all=True, page_size=1)
            schema = SmartsheetSchema.from_sheet_response(response)
            
            self.logger.info(f"Schema extracted: {len(schema.columns)} columns, "
                           f"{schema.total_row_count or 'unknown'} rows")
            
            return schema
            
        except SmartsheetAPIError as e:
            self.logger.error(f"Failed to extract schema for sheet {sheet_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error extracting schema: {e}")
            raise
    
    def extract_data(self, sheet_id: str, progress_callback: Optional[callable] = None) -> Generator[List[SmartsheetRow], None, ExtractionProgress]:
        """
        Extract data from a sheet with chunking and progress tracking.
        
        Yields chunks of rows and returns final progress.
        """
        progress = ExtractionProgress()
        progress.start_time = datetime.now()
        
        try:
            # First, get schema to understand the data structure
            schema = self.extract_schema(sheet_id)
            progress.total_rows = schema.total_row_count
            
            # Adjust chunk size based on data size
            chunk_size = self._adjust_chunk_size(
                schema.total_row_count or 10000, 
                len(schema.columns)
            )
            
            self.logger.info(f"Starting data extraction for sheet {sheet_id}")
            self.logger.info(f"Total rows: {schema.total_row_count}, Columns: {len(schema.columns)}")
            self.logger.info(f"Using chunk size: {chunk_size}")
            
            # For sheets, we need to get all data at once (no pagination)
            # Smartsheet sheets don't support server-side pagination
            self.logger.info("Fetching complete sheet data...")
            
            response = self.client.get_sheet(sheet_id, include_all=True)
            all_rows = [SmartsheetRow.from_api_response(row_data) 
                       for row_data in response.get('rows', [])]
            
            self.logger.info(f"Retrieved {len(all_rows)} rows from API")
            
            # Process rows in chunks
            total_processed = 0
            chunk_num = 0
            
            for i in range(0, len(all_rows), chunk_size):
                chunk = all_rows[i:i + chunk_size]
                chunk_num += 1
                
                # Validate rows if enabled
                if self.validate_data:
                    validated_chunk = []
                    for row in chunk:
                        if self._validate_row_data(row, schema):
                            validated_chunk.append(row)
                        else:
                            progress.add_error(f"Row {row.id} failed validation")
                    chunk = validated_chunk
                
                total_processed += len(chunk)
                progress.update(len(chunk))
                
                self.logger.info(f"Processing chunk {chunk_num}: {len(chunk)} rows "
                               f"({total_processed}/{len(all_rows)} total)")
                
                if progress_callback:
                    progress_callback(progress)
                
                yield chunk
            
            self.logger.info(f"Extraction completed: {total_processed} rows processed")
            return progress
            
        except SmartsheetAPIError as e:
            progress.add_error(f"API error: {e}")
            self.logger.error(f"API error during extraction: {e}")
            raise
        except Exception as e:
            progress.add_error(f"Unexpected error: {e}")
            self.logger.error(f"Unexpected error during extraction: {e}")
            raise


class ReportExtractor(SmartsheetExtractor):
    """Extractor for Smartsheet reports with pagination support."""
    
    def extract_schema(self, report_id: str) -> SmartsheetSchema:
        """Extract schema information for a report."""
        self.logger.info(f"Extracting schema for report {report_id}")
        
        try:
            # Get report metadata with minimal data
            response = self.client.get_report(report_id, include_all=True, page_size=1, page=1)
            schema = SmartsheetSchema.from_report_response(response)
            
            self.logger.info(f"Schema extracted: {len(schema.columns)} columns, "
                           f"{schema.total_row_count or 'unknown'} rows")
            
            return schema
            
        except SmartsheetAPIError as e:
            self.logger.error(f"Failed to extract schema for report {report_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error extracting schema: {e}")
            raise
    
    def extract_data(self, report_id: str, progress_callback: Optional[callable] = None) -> Generator[List[SmartsheetRow], None, ExtractionProgress]:
        """
        Extract data from a report with pagination and chunking.
        
        Yields chunks of rows and returns final progress.
        """
        progress = ExtractionProgress()
        progress.start_time = datetime.now()
        
        try:
            # First, get schema to understand the data structure
            schema = self.extract_schema(report_id)
            progress.total_rows = schema.total_row_count
            
            # Adjust chunk size (reports support pagination up to 10,000 rows per page)
            chunk_size = min(
                self._adjust_chunk_size(schema.total_row_count or 10000, len(schema.columns)),
                10000  # Smartsheet API limit for reports
            )
            
            # Calculate total pages
            if schema.total_row_count:
                progress.total_pages = (schema.total_row_count + chunk_size - 1) // chunk_size
            
            self.logger.info(f"Starting data extraction for report {report_id}")
            self.logger.info(f"Total rows: {schema.total_row_count}, Columns: {len(schema.columns)}")
            self.logger.info(f"Using page size: {chunk_size}, Estimated pages: {progress.total_pages}")
            
            # Extract data page by page
            page = 1
            total_processed = 0
            
            while True:
                self.logger.info(f"Fetching page {page}...")
                progress.current_page = page
                
                try:
                    response = self.client.get_report(
                        report_id, 
                        include_all=True, 
                        page_size=chunk_size, 
                        page=page
                    )
                    
                    rows_data = response.get('rows', [])
                    if not rows_data:
                        self.logger.info("No more rows to process")
                        break
                    
                    # Convert to SmartsheetRow objects
                    rows = [SmartsheetRow.from_api_response(row_data) for row_data in rows_data]
                    
                    # Validate rows if enabled
                    if self.validate_data:
                        validated_rows = []
                        for row in rows:
                            if self._validate_row_data(row, schema):
                                validated_rows.append(row)
                            else:
                                progress.add_error(f"Row {row.id} failed validation")
                        rows = validated_rows
                    
                    total_processed += len(rows)
                    progress.update(len(rows))
                    
                    self.logger.info(f"Page {page}: {len(rows)} rows "
                                   f"({total_processed} total processed)")
                    
                    if progress_callback:
                        progress_callback(progress)
                    
                    yield rows
                    
                    # Check if we've reached the end
                    if len(rows_data) < chunk_size:
                        self.logger.info("Reached end of data (partial page)")
                        break
                    
                    page += 1
                    
                    # Add small delay between pages to be respectful
                    time.sleep(0.1)
                    
                except SmartsheetAPIError as e:
                    if e.status_code == 404:
                        self.logger.info("Reached end of data (404 response)")
                        break
                    else:
                        raise
            
            self.logger.info(f"Extraction completed: {total_processed} rows processed across {page - 1} pages")
            return progress
            
        except SmartsheetAPIError as e:
            progress.add_error(f"API error: {e}")
            self.logger.error(f"API error during extraction: {e}")
            raise
        except Exception as e:
            progress.add_error(f"Unexpected error: {e}")
            self.logger.error(f"Unexpected error during extraction: {e}")
            raise


class DataExporter:
    """Handles exporting extracted data to files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger(__name__)
        self.compression = self.config.get('compression', False)
        self.backup_existing = self.config.get('backup_existing', True)
    
    def export_schema(self, schema: SmartsheetSchema, file_path: Path) -> None:
        """Export schema to JSON file."""
        self.logger.info(f"Exporting schema to {file_path}")
        
        # Backup existing file if requested
        if self.backup_existing and file_path.exists():
            backup_path = file_path.with_suffix(f'.backup.{int(time.time())}.json')
            file_path.rename(backup_path)
            self.logger.info(f"Backed up existing file to {backup_path}")
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write schema
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schema.to_dict(), f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Schema exported: {file_path} ({file_path.stat().st_size} bytes)")
    
    def export_data_chunked(self, rows_generator: Generator[List[SmartsheetRow], None, Any], 
                           schema: SmartsheetSchema, file_path: Path) -> Dict[str, Any]:
        """Export data chunks to JSON file with progress tracking."""
        self.logger.info(f"Exporting data to {file_path}")
        
        # Backup existing file if requested
        if self.backup_existing and file_path.exists():
            backup_path = file_path.with_suffix(f'.backup.{int(time.time())}.json')
            file_path.rename(backup_path)
            self.logger.info(f"Backed up existing file to {backup_path}")
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_rows = 0
        start_time = time.time()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(f'  "metadata": {json.dumps(schema.to_dict(), indent=4)},\n')
            f.write('  "rows": [\n')
            
            first_chunk = True
            
            for chunk in rows_generator:
                if not first_chunk:
                    f.write(',\n')
                
                for i, row in enumerate(chunk):
                    if not first_chunk or i > 0:
                        f.write(',\n')
                    
                    row_dict = row.to_dict(schema.columns)
                    f.write('    ' + json.dumps(row_dict, ensure_ascii=False, default=str))
                    total_rows += 1
                
                first_chunk = False
                
                # Log progress periodically
                if total_rows % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = total_rows / elapsed if elapsed > 0 else 0
                    self.logger.info(f"Exported {total_rows} rows ({rate:.1f} rows/sec)")
            
            f.write('\n  ]\n')
            f.write('}\n')
        
        elapsed_time = time.time() - start_time
        file_size = file_path.stat().st_size
        
        self.logger.info(f"Data export completed: {total_rows} rows in {elapsed_time:.2f}s")
        self.logger.info(f"Output file: {file_path} ({file_size:,} bytes)")
        
        return {
            'total_rows': total_rows,
            'elapsed_time': elapsed_time,
            'file_size': file_size,
            'file_path': str(file_path),
            'rows_per_second': total_rows / elapsed_time if elapsed_time > 0 else 0
        }