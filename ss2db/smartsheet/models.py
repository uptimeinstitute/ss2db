"""
Data models for Smartsheet API responses and data structures.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ColumnType(str, Enum):
    """Smartsheet column types."""
    TEXT_NUMBER = "TEXT_NUMBER"
    CHECKBOX = "CHECKBOX"
    CONTACT_LIST = "CONTACT_LIST"
    DATE = "DATE"
    DATETIME = "DATETIME"
    ABSTRACT_DATETIME = "ABSTRACT_DATETIME"
    DURATION = "DURATION"
    MULTI_CONTACT_LIST = "MULTI_CONTACT_LIST"
    PICKLIST = "PICKLIST"
    MULTI_PICKLIST = "MULTI_PICKLIST"
    PREDECESSOR = "PREDECESSOR"
    SYMBOL = "SYMBOL"
    ATTACHMENT = "ATTACHMENT"


@dataclass
class SmartsheetColumn:
    """Represents a Smartsheet column with metadata."""

    id: int
    title: str
    type: str
    index: int
    primary: bool = False
    hidden: bool = False
    width: Optional[int] = None
    format: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = field(default_factory=list)
    symbol: Optional[str] = None
    system_column_type: Optional[str] = None
    unique_title: Optional[str] = None  # For handling duplicate column names

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'SmartsheetColumn':
        """Create SmartsheetColumn from API response data."""
        # For reports: use virtualId (this is what cells reference)
        # For sheets: use id (this is what cells reference)
        # Reports have virtualId, sheets have id
        column_id = data.get('virtualId') or data.get('id')
        if column_id is None:
            raise ValueError("Column data missing both 'id' and 'virtualId' fields")

        return cls(
            id=column_id,
            title=data['title'],
            type=data.get('type', 'TEXT_NUMBER'),
            index=data.get('index', 0),
            primary=data.get('primary', False),
            hidden=data.get('hidden', False),
            width=data.get('width'),
            format=data.get('format'),
            options=data.get('options', []),
            symbol=data.get('symbol'),
            system_column_type=data.get('systemColumnType')
        )

    def get_effective_title(self) -> str:
        """Get the effective title to use for SQL generation (unique_title if set, otherwise title)."""
        return self.unique_title if self.unique_title else self.title

    def get_postgres_type(self) -> str:
        """Get the corresponding PostgreSQL data type."""
        type_mapping = {
            ColumnType.TEXT_NUMBER: "TEXT",
            ColumnType.CHECKBOX: "BOOLEAN",
            ColumnType.CONTACT_LIST: "JSONB",
            ColumnType.DATE: "DATE",
            ColumnType.DATETIME: "TIMESTAMPTZ",
            ColumnType.ABSTRACT_DATETIME: "TIMESTAMPTZ",
            ColumnType.DURATION: "INTERVAL",
            ColumnType.MULTI_CONTACT_LIST: "JSONB",
            ColumnType.PICKLIST: "VARCHAR(255)",
            ColumnType.MULTI_PICKLIST: "JSONB",
            ColumnType.PREDECESSOR: "JSONB",
            ColumnType.SYMBOL: "VARCHAR(50)",
            ColumnType.ATTACHMENT: "JSONB"
        }
        return type_mapping.get(self.type, "TEXT")

    def get_mysql_type(self) -> str:
        """Get the corresponding MySQL data type."""
        type_mapping = {
            ColumnType.TEXT_NUMBER: "TEXT",
            ColumnType.CHECKBOX: "BOOLEAN",
            ColumnType.CONTACT_LIST: "JSON",
            ColumnType.DATE: "DATE",
            ColumnType.DATETIME: "DATETIME",
            ColumnType.ABSTRACT_DATETIME: "TIMESTAMP",
            ColumnType.DURATION: "TIME",
            ColumnType.MULTI_CONTACT_LIST: "JSON",
            ColumnType.PICKLIST: "VARCHAR(255)",
            ColumnType.MULTI_PICKLIST: "JSON",
            ColumnType.PREDECESSOR: "JSON",
            ColumnType.SYMBOL: "VARCHAR(50)",
            ColumnType.ATTACHMENT: "JSON"
        }
        return type_mapping.get(self.type, "TEXT")


@dataclass
class SmartsheetCell:
    """Represents a cell value with metadata."""

    column_id: int
    value: Any = None
    display_value: Optional[str] = None
    object_value: Any = None
    formula: Optional[str] = None
    hyperlink: Optional[Dict[str, str]] = None
    strict: bool = True

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'SmartsheetCell':
        """Create SmartsheetCell from API response data."""
        # For reports: use virtualColumnId (matches report column schema)
        # For sheets: use columnId (matches sheet column schema)
        # Reports have both, but virtualColumnId is what matches the report column definitions
        column_id = data.get('virtualColumnId') or data.get('columnId')
        if column_id is None:
            raise ValueError("Cell data missing both 'columnId' and 'virtualColumnId' fields")

        return cls(
            column_id=column_id,
            value=data.get('value'),
            display_value=data.get('displayValue'),
            object_value=data.get('objectValue'),
            formula=data.get('formula'),
            hyperlink=data.get('hyperlink'),
            strict=data.get('strict', True)
        )

    def get_transformed_value(self, column: SmartsheetColumn) -> Any:
        """Get the properly transformed value for database storage."""
        # Use objectValue for complex types if available
        if self.object_value is not None and column.type in [
            ColumnType.CONTACT_LIST, ColumnType.MULTI_CONTACT_LIST,
            ColumnType.MULTI_PICKLIST, ColumnType.PREDECESSOR
        ]:
            return self.object_value

        # Handle specific types
        if column.type == ColumnType.CHECKBOX:
            return bool(self.value) if self.value is not None else None

        elif column.type in [ColumnType.DATE, ColumnType.DATETIME, ColumnType.ABSTRACT_DATETIME]:
            return self.value  # Already in ISO format from API

        elif column.type == ColumnType.DURATION:
            # Duration comes as fractional days, convert as needed
            return self.value

        else:
            return self.value


@dataclass
class SmartsheetRow:
    """Represents a Smartsheet row with cells."""

    id: int
    row_number: int
    cells: List[SmartsheetCell]
    expanded: bool = False
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    created_by: Optional[Dict[str, Any]] = None
    modified_by: Optional[Dict[str, Any]] = None
    parent_id: Optional[int] = None
    sibling_id: Optional[int] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'SmartsheetRow':
        """Create SmartsheetRow from API response data."""
        cells = [SmartsheetCell.from_api_response(cell) for cell in data.get('cells', [])]

        return cls(
            id=data['id'],
            row_number=data.get('rowNumber', 0),
            cells=cells,
            expanded=data.get('expanded', False),
            created_at=cls._parse_datetime(data.get('createdAt')),
            modified_at=cls._parse_datetime(data.get('modifiedAt')),
            created_by=data.get('createdBy'),
            modified_by=data.get('modifiedBy'),
            parent_id=data.get('parentId'),
            sibling_id=data.get('siblingId')
        )

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API response."""
        if not dt_str:
            return None
        try:
            # Smartsheet returns ISO format: 2023-01-01T12:00:00Z
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return None

    def get_cell_by_column_id(self, column_id: int) -> Optional[SmartsheetCell]:
        """Get cell value by column ID."""
        for cell in self.cells:
            if cell.column_id == column_id:
                return cell
        return None

    def to_dict(self, columns: List[SmartsheetColumn]) -> Dict[str, Any]:
        """Convert row to dictionary with column names as keys."""
        result = {
            'smartsheet_row_id': self.id,
            'smartsheet_row_number': self.row_number,
        }

        # Add metadata if available
        if self.created_at:
            result['created_at'] = self.created_at
        if self.modified_at:
            result['modified_at'] = self.modified_at

        # Add cell values
        for column in columns:
            cell = self.get_cell_by_column_id(column.id)
            effective_title = column.get_effective_title()
            if cell:
                result[effective_title] = cell.get_transformed_value(column)
            else:
                result[effective_title] = None

        return result


@dataclass
class SmartsheetSchema:
    """Represents the schema of a Smartsheet (columns and metadata)."""

    id: int
    name: str
    columns: List[SmartsheetColumn]
    total_row_count: Optional[int] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    permalink: Optional[str] = None
    source_type: str = "sheet"  # "sheet" or "report"
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    processed_at: Optional[datetime] = None

    @classmethod
    def from_sheet_response(cls, data: Dict[str, Any]) -> 'SmartsheetSchema':
        """Create schema from sheet API response."""
        columns = [SmartsheetColumn.from_api_response(col) for col in data.get('columns', [])]

        schema = cls(
            id=data['id'],
            name=data['name'],
            columns=columns,
            total_row_count=data.get('totalRowCount'),
            created_at=cls._parse_datetime(data.get('createdAt')),
            modified_at=cls._parse_datetime(data.get('modifiedAt')),
            permalink=data.get('permalink'),
            source_type="sheet"
        )

        # Generate unique column names for duplicates
        schema.generate_unique_column_names()

        return schema

    @classmethod
    def from_report_response(cls, data: Dict[str, Any]) -> 'SmartsheetSchema':
        """Create schema from report API response."""
        columns = [SmartsheetColumn.from_api_response(col) for col in data.get('columns', [])]

        schema = cls(
            id=data['id'],
            name=data['name'],
            columns=columns,
            total_row_count=data.get('totalRowCount'),
            created_at=cls._parse_datetime(data.get('createdAt')),
            modified_at=cls._parse_datetime(data.get('modifiedAt')),
            permalink=data.get('permalink'),
            source_type="report"
        )

        # Generate unique column names for duplicates
        schema.generate_unique_column_names()

        return schema

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SmartsheetSchema':
        """Create schema from dictionary (e.g., loaded from JSON)."""
        columns = []
        for col_data in data.get('columns', []):
            # Create SmartsheetColumn from dict data
            column = SmartsheetColumn(
                id=col_data['id'],
                title=col_data['title'],
                type=col_data['type'],
                index=col_data['index'],
                primary=col_data.get('primary', False),
                hidden=col_data.get('hidden', False),
                width=col_data.get('width'),
                format=col_data.get('format'),
                options=col_data.get('options'),
                symbol=col_data.get('symbol'),
                system_column_type=col_data.get('system_column_type'),
                unique_title=col_data.get('unique_title')
            )
            columns.append(column)

        return cls(
            id=data['id'],
            name=data['name'],
            columns=columns,
            total_row_count=data.get('total_row_count'),
            created_at=cls._parse_datetime(data.get('created_at')),
            modified_at=cls._parse_datetime(data.get('modified_at')),
            permalink=data.get('permalink'),
            source_type=data.get('source_type', 'sheet'),
            workspace_id=data.get('workspace_id'),
            workspace_name=data.get('workspace_name'),
            processed_at=cls._parse_datetime(data.get('processed_at')),
        )

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API response."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return None

    def get_column_by_id(self, column_id: int) -> Optional[SmartsheetColumn]:
        """Get column by ID."""
        for column in self.columns:
            if column.id == column_id:
                return column
        return None

    def get_column_by_title(self, title: str) -> Optional[SmartsheetColumn]:
        """Get column by title."""
        for column in self.columns:
            if column.title == title:
                return column
        return None

    def get_primary_column(self) -> Optional[SmartsheetColumn]:
        """Get the primary column."""
        for column in self.columns:
            if column.primary:
                return column
        return None

    def generate_unique_column_names(self) -> None:
        """Generate unique column names for columns with duplicate titles."""
        # Count occurrences of each column title
        title_counts = {}
        title_seen = {}

        for column in self.columns:
            original_title = column.title.strip() if column.title else ''

            # Handle empty or whitespace-only titles
            if not original_title:
                original_title = 'unnamed_column'

            if original_title not in title_counts:
                title_counts[original_title] = 0
                title_seen[original_title] = 0
            title_counts[original_title] += 1


        # Assign unique names to duplicate columns
        for column in self.columns:
            original_title = column.title.strip() if column.title else ''

            # Handle empty or whitespace-only titles
            if not original_title:
                original_title = 'unnamed_column'

            # If this title appears more than once, generate unique names
            if title_counts[original_title] > 1:
                title_seen[original_title] += 1
                column.unique_title = f"{original_title}_{title_seen[original_title]}"
            else:
                # Single occurrence, no need for unique name
                column.unique_title = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary for JSON serialization."""

        result = {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'total_row_count': self.total_row_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'permalink': self.permalink,
            'columns': [
                {
                    'id': col.id,
                    'title': col.title,
                    'unique_title': col.unique_title,
                    'type': col.type,
                    'index': col.index,
                    'primary': col.primary,
                    'hidden': col.hidden,
                    'width': col.width,
                    'format': col.format,
                    'options': col.options,
                    'symbol': col.symbol,
                    'system_column_type': col.system_column_type,
                    'postgres_type': col.get_postgres_type(),
                    'mysql_type': col.get_mysql_type()
                }
                for col in self.columns
            ]
        }

        if self.workspace_id is not None:
            result['workspace_id'] = self.workspace_id
        if self.workspace_name is not None:
            result['workspace_name'] = self.workspace_name
        if self.processed_at is not None:
            result['processed_at'] = self.processed_at.isoformat()

        return result


@dataclass
class ExtractionProgress:
    """Tracks progress of data extraction."""

    total_rows: Optional[int] = None
    extracted_rows: int = 0
    current_page: int = 0
    total_pages: Optional[int] = None
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    rate_limit_waits: int = 0
    total_wait_time: float = 0.0

    def update(self, rows_processed: int):
        """Update progress with newly processed rows."""
        self.extracted_rows += rows_processed
        self.last_update = datetime.now()

    def add_error(self, error: str):
        """Add an error to the progress tracking."""
        self.errors.append(f"{datetime.now().isoformat()}: {error}")

    def add_rate_limit_wait(self, wait_time: float):
        """Record a rate limit wait."""
        self.rate_limit_waits += 1
        self.total_wait_time += wait_time

    def get_progress_percentage(self) -> Optional[float]:
        """Get progress as percentage if total is known."""
        if self.total_rows and self.total_rows > 0:
            return (self.extracted_rows / self.total_rows) * 100
        return None

    def get_estimated_time_remaining(self) -> Optional[float]:
        """Estimate time remaining based on current progress."""
        if not self.start_time or not self.total_rows or self.extracted_rows == 0:
            return None

        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.extracted_rows / elapsed
        remaining_rows = self.total_rows - self.extracted_rows

        if rate > 0:
            return remaining_rows / rate
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary."""
        return {
            'total_rows': self.total_rows,
            'extracted_rows': self.extracted_rows,
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'progress_percentage': self.get_progress_percentage(),
            'estimated_time_remaining': self.get_estimated_time_remaining(),
            'errors': len(self.errors),
            'rate_limit_waits': self.rate_limit_waits,
            'total_wait_time': self.total_wait_time,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }