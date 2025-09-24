"""
PostgreSQL-specific SQL generation and data handling.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from ss2db.smartsheet.models import SmartsheetSchema, SmartsheetRow, SmartsheetColumn, ColumnType
from ss2db.utils.logging import get_logger


class PostgreSQLGenerator:
    """Generates PostgreSQL-compatible SQL scripts from Smartsheet data."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # PostgreSQL configuration
        self.schema_name = self.config.get('schema_name', 'public')
        self.table_prefix = self.config.get('table_prefix', 'smartsheet_')
        self.create_indexes = self.config.get('create_indexes', True)
        self.include_metadata_columns = self.config.get('include_metadata_columns', True)
        self.batch_size = self.config.get('batch_size', 1000)
        self.quote_identifiers = self.config.get('quote_identifiers', True)
        self.use_jsonb = self.config.get('use_jsonb', True)
    
    def sanitize_identifier(self, name: str) -> str:
        """Sanitize a name for use as a PostgreSQL identifier."""
        # Replace spaces and special characters with underscores
        sanitized = re.sub(r'[^\w]', '_', name)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f'col_{sanitized}'
        
        # Handle empty names
        if not sanitized:
            sanitized = 'unnamed_column'
        
        # Convert to lowercase for PostgreSQL convention
        sanitized = sanitized.lower()
        
        return sanitized
    
    def quote_identifier(self, identifier: str) -> str:
        """Quote an identifier if necessary."""
        if self.quote_identifiers:
            return f'"{identifier}"'
        return identifier
    
    def get_table_name(self, schema: SmartsheetSchema, custom_name: Optional[str] = None) -> str:
        """Generate table name from schema."""
        if custom_name:
            return self.sanitize_identifier(custom_name)
        
        # Use source type and ID
        base_name = f"{self.table_prefix}{schema.source_type}_{schema.id}"
        return self.sanitize_identifier(base_name)
    
    def convert_column_type(self, column: SmartsheetColumn) -> str:
        """Convert Smartsheet column type to PostgreSQL type."""
        postgres_types = {
            ColumnType.TEXT_NUMBER: "TEXT",
            ColumnType.CHECKBOX: "BOOLEAN", 
            ColumnType.CONTACT_LIST: "JSONB" if self.use_jsonb else "JSON",
            ColumnType.DATE: "DATE",
            ColumnType.DATETIME: "TIMESTAMPTZ",
            ColumnType.ABSTRACT_DATETIME: "TIMESTAMPTZ",
            ColumnType.DURATION: "INTERVAL",
            ColumnType.MULTI_CONTACT_LIST: "JSONB" if self.use_jsonb else "JSON",
            ColumnType.PICKLIST: "VARCHAR(255)",
            ColumnType.MULTI_PICKLIST: "JSONB" if self.use_jsonb else "JSON",
            ColumnType.PREDECESSOR: "JSONB" if self.use_jsonb else "JSON",
            ColumnType.SYMBOL: "VARCHAR(50)",
            ColumnType.ATTACHMENT: "JSONB" if self.use_jsonb else "JSON"
        }
        
        return postgres_types.get(column.type, "TEXT")
    
    def convert_value(self, value: Any, column: SmartsheetColumn) -> str:
        """Convert a value to PostgreSQL-compatible format."""
        if value is None:
            return "NULL"
        
        column_type = column.type
        
        # Handle boolean values
        if column_type == ColumnType.CHECKBOX:
            if isinstance(value, bool):
                return "TRUE" if value else "FALSE"
            elif isinstance(value, str):
                return "TRUE" if value.lower() in ('true', '1', 'yes', 'on') else "FALSE"
            else:
                return "TRUE" if value else "FALSE"
        
        # Handle JSON/JSONB types
        elif column_type in [ColumnType.CONTACT_LIST, ColumnType.MULTI_CONTACT_LIST, 
                           ColumnType.MULTI_PICKLIST, ColumnType.PREDECESSOR, ColumnType.ATTACHMENT]:
            if isinstance(value, (dict, list)):
                json_str = json.dumps(value, ensure_ascii=False)
                return f"'{self.escape_string(json_str)}'::JSONB" if self.use_jsonb else f"'{self.escape_string(json_str)}'::JSON"
            elif isinstance(value, str):
                # Try to parse as JSON, otherwise treat as simple string
                try:
                    parsed = json.loads(value)
                    json_str = json.dumps(parsed, ensure_ascii=False)
                    return f"'{self.escape_string(json_str)}'::JSONB" if self.use_jsonb else f"'{self.escape_string(json_str)}'::JSON"
                except (json.JSONDecodeError, ValueError):
                    # Treat as simple string value
                    json_str = json.dumps(value, ensure_ascii=False)
                    return f"'{self.escape_string(json_str)}'::JSONB" if self.use_jsonb else f"'{self.escape_string(json_str)}'::JSON"
            else:
                json_str = json.dumps(value, ensure_ascii=False, default=str)
                return f"'{self.escape_string(json_str)}'::JSONB" if self.use_jsonb else f"'{self.escape_string(json_str)}'::JSON"
        
        # Handle date/time types
        elif column_type in [ColumnType.DATE, ColumnType.DATETIME, ColumnType.ABSTRACT_DATETIME]:
            if isinstance(value, str):
                # Validate that the string is a valid date/datetime
                if self._is_valid_date_string(value):
                    return f"'{self.escape_string(value)}'"
                else:
                    # Invalid date string (like "X"), return NULL
                    self.logger.warning(f"Invalid date value '{value}' converted to NULL")
                    return "NULL"
            elif isinstance(value, datetime):
                return f"'{value.isoformat()}'"
            elif value is None:
                return "NULL"
            else:
                # Try to convert other types to string and validate
                str_value = str(value)
                if self._is_valid_date_string(str_value):
                    return f"'{self.escape_string(str_value)}'"
                else:
                    self.logger.warning(f"Invalid date value '{str_value}' converted to NULL")
                    return "NULL"
        
        # Handle duration
        elif column_type == ColumnType.DURATION:
            if isinstance(value, (int, float)):
                # Assuming value is in days, convert to PostgreSQL interval
                return f"'{value} days'"
            elif isinstance(value, str):
                return f"'{self.escape_string(value)}'"
            else:
                return f"'{self.escape_string(str(value))}'"
        
        # Handle numeric values
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        
        # Handle all other types as text
        else:
            return f"'{self.escape_string(str(value))}'"
    
    def escape_string(self, value: str) -> str:
        """Escape string value for PostgreSQL."""
        if not isinstance(value, str):
            value = str(value)
        
        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")
        
        # Escape backslashes
        escaped = escaped.replace("\\", "\\\\")
        
        return escaped
    
    def _is_valid_date_string(self, value: str) -> bool:
        """Check if a string represents a valid date/datetime."""
        if not value or not isinstance(value, str):
            return False
        
        # Common invalid date patterns in Smartsheet
        if value.strip().upper() in ['X', 'TBD', 'TBA', 'N/A', 'NA', '-', '']:
            return False
        
        # Try to parse as various date formats
        from datetime import datetime
        
        # ISO date formats that PostgreSQL accepts
        date_formats = [
            '%Y-%m-%d',           # 2023-01-15
            '%Y-%m-%dT%H:%M:%S',  # 2023-01-15T14:30:00
            '%Y-%m-%dT%H:%M:%SZ', # 2023-01-15T14:30:00Z
            '%Y-%m-%d %H:%M:%S',  # 2023-01-15 14:30:00
            '%m/%d/%Y',           # 01/15/2023
            '%m/%d/%y',           # 01/15/23
            '%d/%m/%Y',           # 15/01/2023
            '%Y/%m/%d',           # 2023/01/15
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(value.strip(), fmt)
                return True
            except ValueError:
                continue
        
        # Try parsing with dateutil if available (more flexible)
        try:
            from dateutil import parser
            parser.parse(value.strip())
            return True
        except (ValueError, ImportError):
            pass
        
        return False
    
    def generate_create_table_sql(self, schema: SmartsheetSchema, table_name: Optional[str] = None) -> str:
        """Generate CREATE TABLE statement."""
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        lines = [f"-- Table for {schema.source_type}: {schema.name}"]
        lines.append(f"-- Generated on: {datetime.now().isoformat()}")
        lines.append(f"-- Total rows: {schema.total_row_count or 'unknown'}")
        lines.append("")
        
        lines.append(f"DROP TABLE IF EXISTS {full_table_name};")
        lines.append("")
        lines.append(f"CREATE TABLE {full_table_name} (")
        
        column_definitions = []
        
        # Add metadata columns if enabled
        if self.include_metadata_columns:
            column_definitions.extend([
                f"    {self.quote_identifier('smartsheet_row_id')} BIGINT NOT NULL",
                f"    {self.quote_identifier('smartsheet_row_number')} INTEGER",
                f"    {self.quote_identifier('created_at')} TIMESTAMPTZ DEFAULT NOW()",
                f"    {self.quote_identifier('modified_at')} TIMESTAMPTZ DEFAULT NOW()"
            ])
        
        # Add data columns
        for column in schema.columns:
            if column.hidden:
                continue

            col_name = self.sanitize_identifier(column.get_effective_title())
            col_type = self.convert_column_type(column)

            col_def = f"    {self.quote_identifier(col_name)} {col_type}"

            # Don't add NOT NULL constraints for Smartsheet columns
            # Even "primary" columns in Smartsheet can have NULL values in practice
            # Only our metadata columns (smartsheet_row_id) should be NOT NULL

            column_definitions.append(col_def)
        
        lines.append(",\n".join(column_definitions))
        
        # Add primary key if we have metadata columns
        if self.include_metadata_columns:
            lines.append(f",\n    PRIMARY KEY ({self.quote_identifier('smartsheet_row_id')})")
        
        lines.append(");")
        
        return "\n".join(lines)
    
    def generate_indexes_sql(self, schema: SmartsheetSchema, table_name: Optional[str] = None) -> str:
        """Generate CREATE INDEX statements."""
        if not self.create_indexes:
            return ""
        
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        lines = ["", "-- Indexes"]
        
        # Index on metadata columns
        if self.include_metadata_columns:
            lines.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_modified_at ON {full_table_name} ({self.quote_identifier('modified_at')});")
            lines.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {full_table_name} ({self.quote_identifier('created_at')});")
        
        # Index on primary column
        primary_column = schema.get_primary_column()
        if primary_column and not primary_column.hidden:
            col_name = self.sanitize_identifier(primary_column.get_effective_title())
            lines.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{col_name} ON {full_table_name} ({self.quote_identifier(col_name)});")

        # Indexes on JSON columns for common queries
        for column in schema.columns:
            if column.hidden:
                continue

            if column.type in [ColumnType.CONTACT_LIST, ColumnType.MULTI_CONTACT_LIST]:
                col_name = self.sanitize_identifier(column.get_effective_title())
                # GIN index for JSON operations
                lines.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{col_name}_gin ON {full_table_name} USING GIN ({self.quote_identifier(col_name)});")

        return "\n".join(lines)
    
    def generate_insert_sql_batch(self, rows: List[SmartsheetRow], schema: SmartsheetSchema, 
                                 table_name: Optional[str] = None) -> str:
        """Generate INSERT statements for a batch of rows."""
        if not rows:
            return ""
        
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        # Build column list
        columns = []
        
        if self.include_metadata_columns:
            columns.extend([
                self.quote_identifier('smartsheet_row_id'),
                self.quote_identifier('smartsheet_row_number'),
                self.quote_identifier('created_at'),
                self.quote_identifier('modified_at')
            ])
        
        # Add data columns (non-hidden only)
        for column in schema.columns:
            if not column.hidden:
                col_name = self.sanitize_identifier(column.get_effective_title())
                columns.append(self.quote_identifier(col_name))
        
        # Build INSERT statement
        columns_str = ", ".join(columns)
        
        lines = [f"-- Batch INSERT for {len(rows)} rows"]
        lines.append(f"INSERT INTO {full_table_name} ({columns_str}) VALUES")
        
        # Generate value rows
        value_rows = []
        for row in rows:
            values = []
            
            # Add metadata values
            if self.include_metadata_columns:
                values.extend([
                    str(row.id),
                    str(row.row_number) if row.row_number else "NULL",
                    f"'{row.created_at.isoformat()}'" if row.created_at else "NOW()",
                    f"'{row.modified_at.isoformat()}'" if row.modified_at else "NOW()"
                ])
            
            # Add data values
            for column in schema.columns:
                if column.hidden:
                    continue
                    
                cell = row.get_cell_by_column_id(column.id)
                if cell:
                    value = cell.get_transformed_value(column)
                    values.append(self.convert_value(value, column))
                else:
                    values.append("NULL")
            
            value_rows.append(f"    ({', '.join(values)})")
        
        # Join value rows properly
        if value_rows:
            all_values = ",\n".join(value_rows)
            lines.append(all_values + ";")
        
        return "\n".join(lines)
    
    def generate_insert_sql_batch_from_dict(self, rows_data: List[Dict], schema: SmartsheetSchema, 
                                           table_name: Optional[str] = None) -> str:
        """Generate INSERT statements for a batch of dictionary rows."""
        if not rows_data:
            return ""
        
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        # Build column list
        columns = []
        
        if self.include_metadata_columns:
            columns.extend([
                self.quote_identifier('smartsheet_row_id'),
                self.quote_identifier('smartsheet_row_number'),
                self.quote_identifier('created_at'),
                self.quote_identifier('modified_at')
            ])
        
        # Add data columns (non-hidden only)
        for column in schema.columns:
            if not column.hidden:
                col_name = self.sanitize_identifier(column.get_effective_title())
                columns.append(self.quote_identifier(col_name))
        
        # Build INSERT statement
        columns_str = ", ".join(columns)
        
        lines = [f"-- Batch INSERT for {len(rows_data)} rows"]
        lines.append(f"INSERT INTO {full_table_name} ({columns_str}) VALUES")
        
        # Generate value rows
        value_rows = []
        for row_data in rows_data:
            values = []
            
            # Add metadata values
            if self.include_metadata_columns:
                row_id = row_data.get('smartsheet_row_id', 'NULL')
                row_number = row_data.get('smartsheet_row_number', 'NULL')
                created_at = row_data.get('created_at')
                modified_at = row_data.get('modified_at')
                
                values.extend([
                    str(row_id) if row_id != 'NULL' else "NULL",
                    str(row_number) if row_number != 'NULL' else "NULL",
                    f"'{created_at}'" if created_at else "NOW()",
                    f"'{modified_at}'" if modified_at else "NOW()"
                ])
            
            # Add data values
            for column in schema.columns:
                if column.hidden:
                    continue
                    
                value = row_data.get(column.get_effective_title())
                values.append(self.convert_value(value, column))
            
            value_rows.append(f"    ({', '.join(values)})")
        
        # Join value rows properly
        if value_rows:
            all_values = ",\n".join(value_rows)
            lines.append(all_values + ";")
        
        return "\n".join(lines)
    
    def generate_complete_sql(self, data_file: Path, schema_file: Path, 
                            table_name: Optional[str] = None) -> str:
        """Generate complete SQL script from data and schema files."""
        self.logger.info(f"Generating PostgreSQL script from {data_file} and {schema_file}")
        
        # Load schema
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        schema = SmartsheetSchema(
            id=schema_data['id'],
            name=schema_data['name'],
            columns=[SmartsheetColumn(
                id=col['id'],
                title=col['title'],
                type=col['type'],
                index=col['index'],
                primary=col['primary'],
                hidden=col['hidden'],
                width=col.get('width'),
                format=col.get('format'),
                options=col.get('options', []),
                symbol=col.get('symbol'),
                system_column_type=col.get('system_column_type')
            ) for col in schema_data['columns']],
            total_row_count=schema_data.get('total_row_count'),
            created_at=datetime.fromisoformat(schema_data['created_at']) if schema_data.get('created_at') else None,
            modified_at=datetime.fromisoformat(schema_data['modified_at']) if schema_data.get('modified_at') else None,
            permalink=schema_data.get('permalink'),
            source_type=schema_data.get('source_type', 'sheet')
        )
        
        # Start building SQL
        sql_parts = []
        
        # Header
        sql_parts.append("-- PostgreSQL import script generated by ss2db")
        sql_parts.append(f"-- Source: {schema.name} ({schema.source_type})")
        sql_parts.append(f"-- Generated: {datetime.now().isoformat()}")
        sql_parts.append(f"-- Total rows: {schema.total_row_count or 'unknown'}")
        sql_parts.append("")
        
        # Table creation
        sql_parts.append(self.generate_create_table_sql(schema, table_name))
        
        # Indexes
        if self.create_indexes:
            sql_parts.append(self.generate_indexes_sql(schema, table_name))
        
        # Data insertion
        sql_parts.append("")
        sql_parts.append("-- Data insertion")
        
        # Load and process data in batches
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both new format (with metadata) and old format (direct rows array)
        if 'rows' in data:
            rows_data = data['rows']
        else:
            # Fallback for old format where data is direct array
            rows_data = data if isinstance(data, list) else []
        total_rows = len(rows_data)
        
        self.logger.info(f"Processing {total_rows} rows in batches of {self.batch_size}")
        
        for i in range(0, total_rows, self.batch_size):
            batch_rows_data = rows_data[i:i + self.batch_size]
            
            if batch_rows_data:
                batch_sql = self.generate_insert_sql_batch_from_dict(batch_rows_data, schema, table_name)
                sql_parts.append(batch_sql)
                sql_parts.append("")
        
        # Footer
        sql_parts.append("-- End of script")
        sql_parts.append(f"-- Total rows inserted: {total_rows}")
        
        return "\n".join(sql_parts)


def generate_postgresql_script(data_file: Path, schema_file: Path, 
                             output_file: Path, config: Optional[Dict[str, Any]] = None,
                             table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate PostgreSQL import script from Smartsheet data files.
    
    Args:
        data_file: Path to JSON data file
        schema_file: Path to JSON schema file
        output_file: Path for output SQL file
        config: PostgreSQL configuration
        table_name: Custom table name (optional)
    
    Returns:
        Dictionary with generation statistics
    """
    import time
    
    logger = get_logger(__name__)
    start_time = time.time()
    
    try:
        generator = PostgreSQLGenerator(config)
        sql_content = generator.generate_complete_sql(data_file, schema_file, table_name)
        
        # Write SQL file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(sql_content)
        
        elapsed_time = time.time() - start_time
        file_size = output_file.stat().st_size
        
        # Count lines and statements
        lines = sql_content.count('\n') + 1
        insert_statements = sql_content.count('INSERT INTO')
        
        result = {
            'file_path': str(output_file),
            'file_size': file_size,
            'elapsed_time': elapsed_time,
            'lines': lines,
            'insert_statements': insert_statements,
            'table_name': generator.get_table_name(generator.schema) if hasattr(generator, 'schema') else table_name
        }
        
        logger.info(f"PostgreSQL script generated: {output_file}")
        logger.info(f"  File size: {file_size:,} bytes")
        logger.info(f"  Lines: {lines:,}")
        logger.info(f"  INSERT statements: {insert_statements}")
        logger.info(f"  Generation time: {elapsed_time:.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate PostgreSQL script: {e}")
        raise