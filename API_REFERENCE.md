# ss2db API Reference

Complete API documentation for the ss2db (Smartsheet to Database) library.

## Table of Contents

- [Overview](#overview)
- [Smartsheet Client API](#smartsheet-client-api)
- [Data Models API](#data-models-api)
- [Database Generators API](#database-generators-api)
- [Configuration API](#configuration-api)
- [Extractors API](#extractors-api)
- [Utility APIs](#utility-apis)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Overview

The ss2db library provides a programmatic interface for extracting data from Smartsheet and generating SQL import scripts for PostgreSQL and MySQL databases. The API is designed for production use with comprehensive error handling, rate limiting, and memory management.

### Key Features

- **Rate-Limited API Client**: Automatic rate limiting with configurable buffer
- **Type-Safe Data Models**: Comprehensive type hints and Pydantic validation
- **Memory-Efficient Processing**: Streaming data extraction with configurable chunking
- **Database Abstraction**: Support for PostgreSQL and MySQL with extensible architecture
- **Comprehensive Error Handling**: Detailed exceptions with context and retry logic

### Installation

Since ss2db is not available on PyPI, install directly from the Git repository:

#### Production Installation

```bash
# Install from GitHub (stable version)
pip install git+https://github.com/uptimeinstitute/ss2db.git

# Install specific version/tag
pip install git+https://github.com/uptimeinstitute/ss2db.git@v1.0.0

# Install from specific branch
pip install git+https://github.com/uptimeinstitute/ss2db.git@main
```

#### Development Installation

```bash
# Clone repository
git clone https://github.com/uptimeinstitute/ss2db.git
cd ss2db

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Or install just the package in editable mode
pip install -e .
```

#### Requirements

- Python 3.12 or higher
- Git (for repository installation)

#### Verify Installation

```bash
# Check if ss2db command is available
ss2db --help

# Verify in Python
python -c "import ss2db; print('Installation successful')"
```

### Quick Start

```python
from ss2db.smartsheet.client import SmartsheetClient
from ss2db.smartsheet.extractors import SheetExtractor
from ss2db.database.postgresql import generate_postgresql_script

# Initialize client
client = SmartsheetClient("your_api_token")

# Extract data
extractor = SheetExtractor(client)
schema = extractor.extract_schema("sheet_id")

# Generate SQL
generate_postgresql_script(
    data_file="data.json",
    schema_file="schema.json", 
    output_file="import.sql"
)
```

## Smartsheet Client API

### SmartsheetClient

The main client for interacting with the Smartsheet API.

#### Class Definition

```python
class SmartsheetClient:
    def __init__(
        self, 
        api_token: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> None
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_token` | `str` | Required | Smartsheet API token for authentication |
| `config` | `Optional[Dict[str, Any]]` | `None` | Configuration dictionary for client behavior |

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `request_timeout` | `int` | `30` | Request timeout in seconds |
| `retry_attempts` | `int` | `3` | Number of retry attempts for failed requests |
| `retry_delay` | `int` | `5` | Base delay between retries in seconds |
| `rate_limit_buffer` | `int` | `5` | Number of requests to keep in reserve |

#### Methods

##### `get_user_info() -> Dict[str, Any]`

Get current user information to test API connectivity.

**Returns:** User information dictionary

**Raises:** `SmartsheetAPIError` if request fails

**Example:**
```python
client = SmartsheetClient("token")
user_info = client.get_user_info()
print(f"User: {user_info['email']}")
```

##### `get_sheet(sheet_id: str, include_all: bool = True, page_size: Optional[int] = None) -> Dict[str, Any]`

Retrieve complete sheet data with metadata.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sheet_id` | `str` | Required | Smartsheet sheet ID |
| `include_all` | `bool` | `True` | Include column types and formatting |
| `page_size` | `Optional[int]` | `None` | Pagination size (if supported) |

**Returns:** Complete sheet data dictionary

**Example:**
```python
sheet_data = client.get_sheet("1234567890")
print(f"Sheet: {sheet_data['name']}")
print(f"Rows: {len(sheet_data['rows'])}")
```

##### `get_report(report_id: str, include_all: bool = True, page_size: Optional[int] = None, page: Optional[int] = None) -> Dict[str, Any]`

Retrieve report data with pagination support.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `report_id` | `str` | Required | Smartsheet report ID |
| `include_all` | `bool` | `True` | Include metadata and formatting |
| `page_size` | `Optional[int]` | `None` | Rows per page (max 10,000) |
| `page` | `Optional[int]` | `None` | Page number (1-based) |

**Returns:** Report data dictionary

**Example:**
```python
import math

# Get first page to determine total row count
report_data = client.get_report("9876543210", page_size=1000, page=1)

# Calculate total pages from total row count
total_row_count = report_data.get('totalRowCount', 0)
page_size = 1000
total_pages = math.ceil(total_row_count / page_size) if total_row_count > 0 else 1

print(f"Report has {total_row_count} rows across {total_pages} pages")

# Paginate through all data
for page in range(1, total_pages + 1):
    page_data = client.get_report("9876543210", page_size=page_size, page=page)
    process_data(page_data['rows'])
    print(f"Processed page {page}/{total_pages}")
```

##### `get_sheet_columns(sheet_id: str) -> List[Dict[str, Any]]`

Get only column metadata for a sheet.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sheet_id` | `str` | Smartsheet sheet ID |

**Returns:** List of column dictionaries

##### `get_report_columns(report_id: str) -> List[Dict[str, Any]]`

Get column metadata for a report.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `report_id` | `str` | Smartsheet report ID |

**Returns:** List of column dictionaries

##### `test_connection() -> bool`

Test API connectivity and authentication.

**Returns:** `True` if connection successful, `False` otherwise

**Example:**
```python
if client.test_connection():
    print("API connection successful")
else:
    print("Connection failed")
```

##### `get_rate_limit_status() -> Dict[str, Any]`

Get current rate limit usage statistics.

**Returns:** Rate limit status dictionary

**Example:**
```python
status = client.get_rate_limit_status()
print(f"Usage: {status['usage_percentage']:.1f}%")
print(f"Requests: {status['requests_in_last_minute']}/{status['effective_limit']}")
```

### RateLimiter

Handles API rate limiting with sliding window algorithm.

#### Class Definition

```python
@dataclass
class RateLimiter:
    max_requests_per_minute: int = 100
    buffer_requests: int = 5
    request_times: List[float] = field(default_factory=list)
```

#### Methods

##### `wait_if_needed() -> float`

Check rate limits and wait if necessary.

**Returns:** Wait time in seconds (0.0 if no wait required)

##### `get_current_usage() -> Dict[str, Any]`

Get rate limit usage statistics.

**Returns:** Dictionary with usage metrics

## Data Models API

### ColumnType

Enumeration of supported Smartsheet column types.

```python
class ColumnType(str, Enum):
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
```

### SmartsheetColumn

Represents a Smartsheet column with metadata and type mappings.

#### Class Definition

```python
@dataclass
class SmartsheetColumn:
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
```

#### Class Methods

##### `from_api_response(data: Dict[str, Any]) -> SmartsheetColumn`

Create column from Smartsheet API response data.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `Dict[str, Any]` | API response column data |

**Returns:** `SmartsheetColumn` instance

**Example:**
```python
column_data = {
    "id": 123,
    "title": "Task Name",
    "type": "TEXT_NUMBER",
    "primary": True
}
column = SmartsheetColumn.from_api_response(column_data)
```

#### Instance Methods

##### `get_postgres_type() -> str`

Get corresponding PostgreSQL data type.

**Returns:** PostgreSQL type string

**Type Mappings:**
| Smartsheet Type | PostgreSQL Type |
|-----------------|-----------------|
| `TEXT_NUMBER` | `TEXT` |
| `CHECKBOX` | `BOOLEAN` |
| `CONTACT_LIST` | `JSONB` |
| `DATE` | `DATE` |
| `DATETIME` | `TIMESTAMPTZ` |
| `DURATION` | `INTERVAL` |
| `PICKLIST` | `VARCHAR(255)` |

##### `get_mysql_type() -> str`

Get corresponding MySQL data type.

**Returns:** MySQL type string

### SmartsheetCell

Represents a cell value with metadata and transformation logic.

#### Class Definition

```python
@dataclass
class SmartsheetCell:
    column_id: int
    value: Any = None
    display_value: Optional[str] = None
    object_value: Any = None
    formula: Optional[str] = None
    hyperlink: Optional[Dict[str, str]] = None
    strict: bool = True
```

#### Class Methods

##### `from_api_response(data: Dict[str, Any]) -> SmartsheetCell`

Create cell from API response data.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `Dict[str, Any]` | API response cell data |

**Returns:** `SmartsheetCell` instance

#### Instance Methods

##### `get_transformed_value(column: SmartsheetColumn) -> Any`

Get properly transformed value for database storage.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `column` | `SmartsheetColumn` | Column metadata for transformation |

**Returns:** Transformed value ready for database insertion

**Example:**
```python
cell = SmartsheetCell(column_id=123, value=True)
column = SmartsheetColumn(id=123, type=ColumnType.CHECKBOX, title="Complete")
transformed = cell.get_transformed_value(column)  # Returns: True
```

### SmartsheetRow

Represents a complete row with cells and metadata.

#### Class Definition

```python
@dataclass
class SmartsheetRow:
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
```

#### Class Methods

##### `from_api_response(data: Dict[str, Any]) -> SmartsheetRow`

Create row from API response data.

#### Instance Methods

##### `get_cell_by_column_id(column_id: int) -> Optional[SmartsheetCell]`

Find cell by column ID.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `column_id` | `int` | Column ID to search for |

**Returns:** Cell if found, `None` otherwise

##### `to_dict(columns: List[SmartsheetColumn]) -> Dict[str, Any]`

Convert row to dictionary with column names as keys.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `columns` | `List[SmartsheetColumn]` | Column definitions |

**Returns:** Dictionary representation of row

### SmartsheetSchema

Represents the complete schema of a sheet or report.

#### Class Definition

```python
@dataclass
class SmartsheetSchema:
    id: int
    name: str
    columns: List[SmartsheetColumn]
    total_row_count: Optional[int] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    permalink: Optional[str] = None
    source_type: str = "sheet"  # "sheet" or "report"
```

#### Class Methods

##### `from_sheet_response(data: Dict[str, Any]) -> SmartsheetSchema`

Create schema from sheet API response.

##### `from_report_response(data: Dict[str, Any]) -> SmartsheetSchema`

Create schema from report API response.

##### `from_dict(data: Dict[str, Any]) -> SmartsheetSchema`

Create schema from dictionary (e.g., loaded from JSON).

#### Instance Methods

##### `get_column_by_id(column_id: int) -> Optional[SmartsheetColumn]`

Find column by ID.

##### `get_column_by_title(title: str) -> Optional[SmartsheetColumn]`

Find column by title.

##### `get_primary_column() -> Optional[SmartsheetColumn]`

Get the primary column.

##### `to_dict() -> Dict[str, Any]`

Convert schema to dictionary for JSON serialization.

### ExtractionProgress

Tracks progress of data extraction operations.

#### Class Definition

```python
@dataclass
class ExtractionProgress:
    total_rows: Optional[int] = None
    extracted_rows: int = 0
    current_page: int = 0
    total_pages: Optional[int] = None
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    rate_limit_waits: int = 0
    total_wait_time: float = 0.0
```

#### Instance Methods

##### `update(rows_processed: int) -> None`

Update progress with newly processed rows.

##### `add_error(error: str) -> None`

Add an error to progress tracking.

##### `add_rate_limit_wait(wait_time: float) -> None`

Record a rate limit wait.

##### `get_progress_percentage() -> Optional[float]`

Get progress as percentage if total is known.

##### `get_estimated_time_remaining() -> Optional[float]`

Estimate time remaining based on current progress.

##### `to_dict() -> Dict[str, Any]`

Convert progress to dictionary.

## Database Generators API

### PostgreSQLGenerator

Generates PostgreSQL-compatible SQL scripts from Smartsheet data.

#### Class Definition

```python
class PostgreSQLGenerator:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None
```

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `schema_name` | `str` | `"public"` | PostgreSQL schema name |
| `table_prefix` | `str` | `"smartsheet_"` | Table name prefix |
| `create_indexes` | `bool` | `True` | Generate index statements |
| `include_metadata_columns` | `bool` | `True` | Include row metadata columns |
| `batch_size` | `int` | `1000` | INSERT batch size |
| `quote_identifiers` | `bool` | `True` | Quote column/table names |
| `use_jsonb` | `bool` | `True` | Use JSONB instead of JSON |

#### Methods

##### `sanitize_identifier(name: str) -> str`

Sanitize a name for use as PostgreSQL identifier.

##### `quote_identifier(identifier: str) -> str`

Quote an identifier if necessary.

##### `get_table_name(schema: SmartsheetSchema, custom_name: Optional[str] = None) -> str`

Generate table name from schema.

##### `convert_column_type(column: SmartsheetColumn) -> str`

Convert Smartsheet column type to PostgreSQL type.

##### `convert_value(value: Any, column: SmartsheetColumn) -> str`

Convert value to PostgreSQL-compatible format.

##### `escape_string(value: str) -> str`

Escape string value for PostgreSQL.

##### `generate_create_table_sql(schema: SmartsheetSchema, table_name: Optional[str] = None) -> str`

Generate CREATE TABLE statement.

##### `generate_indexes_sql(schema: SmartsheetSchema, table_name: Optional[str] = None) -> str`

Generate CREATE INDEX statements.

##### `generate_insert_sql_batch(rows: List[Dict], schema: SmartsheetSchema, table_name: Optional[str] = None) -> str`

Generate INSERT statements for a batch of rows.

##### `generate_complete_sql(data_file: Path, schema_file: Path, table_name: Optional[str] = None) -> str`

Generate complete SQL script from data and schema files.

#### Function: `generate_postgresql_script`

```python
def generate_postgresql_script(
    data_file: Path, 
    schema_file: Path, 
    output_file: Path, 
    config: Optional[Dict[str, Any]] = None,
    table_name: Optional[str] = None
) -> Dict[str, Any]
```

High-level function to generate PostgreSQL import script.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `data_file` | `Path` | Path to JSON data file |
| `schema_file` | `Path` | Path to JSON schema file |
| `output_file` | `Path` | Path for output SQL file |
| `config` | `Optional[Dict[str, Any]]` | PostgreSQL configuration |
| `table_name` | `Optional[str]` | Custom table name |

**Returns:** Dictionary with generation statistics

**Example:**
```python
from pathlib import Path
from ss2db.database.postgresql import generate_postgresql_script

result = generate_postgresql_script(
    data_file=Path("data.json"),
    schema_file=Path("schema.json"),
    output_file=Path("import.sql"),
    config={
        "schema_name": "warehouse",
        "table_prefix": "ss_",
        "batch_size": 2000
    }
)

print(f"Generated {result['lines']} lines")
print(f"File size: {result['file_size']} bytes")
```

### MySQLGenerator

Generates MySQL-compatible SQL scripts from Smartsheet data.

#### Class Definition

```python
class MySQLGenerator:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None
```

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `database_name` | `Optional[str]` | `None` | MySQL database name |
| `table_prefix` | `str` | `"smartsheet_"` | Table name prefix |
| `create_indexes` | `bool` | `True` | Generate index statements |
| `include_metadata_columns` | `bool` | `True` | Include row metadata |
| `batch_size` | `int` | `1000` | INSERT batch size |
| `quote_identifiers` | `bool` | `True` | Quote identifiers |
| `engine` | `str` | `"InnoDB"` | MySQL storage engine |
| `charset` | `str` | `"utf8mb4"` | Character set |
| `collation` | `str` | `"utf8mb4_unicode_ci"` | Collation |
| `use_json` | `bool` | `True` | Use JSON type for complex data |

#### Methods

Similar to PostgreSQLGenerator but with MySQL-specific implementations.

#### Function: `generate_mysql_script`

```python
def generate_mysql_script(
    data_file: Path, 
    schema_file: Path, 
    output_file: Path, 
    config: Optional[Dict[str, Any]] = None,
    table_name: Optional[str] = None
) -> Dict[str, Any]
```

High-level function to generate MySQL import script.

## Extractors API

### SmartsheetExtractor

Base class for data extraction with memory management and validation.

#### Class Definition

```python
class SmartsheetExtractor:
    def __init__(
        self, 
        client: SmartsheetClient, 
        config: Optional[Dict[str, Any]] = None
    ) -> None
```

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_size` | `int` | `10000` | Processing chunk size |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `memory_limit_mb` | `int` | `1024` | Memory limit in MB |
| `validate_data` | `bool` | `True` | Enable data validation |

#### Methods

##### `_estimate_memory_usage(row_count: int, column_count: int) -> float`

Estimate memory usage in MB for given data size.

##### `_adjust_chunk_size(total_rows: int, column_count: int) -> int`

Adjust chunk size based on memory limits.

##### `_validate_row_data(row: SmartsheetRow, schema: SmartsheetSchema) -> bool`

Validate row data for consistency.

### SheetExtractor

Extractor for Smartsheet sheets.

#### Class Definition

```python
class SheetExtractor(SmartsheetExtractor):
    pass
```

#### Methods

##### `extract_schema(sheet_id: str) -> SmartsheetSchema`

Extract schema information from a sheet.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sheet_id` | `str` | Smartsheet sheet ID |

**Returns:** Complete schema information

##### `extract_data(sheet_id: str, progress_callback: Optional[Callable] = None) -> Generator[List[SmartsheetRow], None, ExtractionProgress]`

Extract data from a sheet with chunking and progress tracking.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sheet_id` | `str` | Smartsheet sheet ID |
| `progress_callback` | `Optional[Callable]` | Progress callback function |

**Returns:** Generator yielding chunks of rows

**Example:**
```python
extractor = SheetExtractor(client, {"chunk_size": 5000})

def progress_callback(progress):
    print(f"Progress: {progress.extracted_rows} rows")

for chunk in extractor.extract_data("123456789", progress_callback):
    process_chunk(chunk)
```

### ReportExtractor

Extractor for Smartsheet reports with pagination support.

#### Class Definition

```python
class ReportExtractor(SmartsheetExtractor):
    pass
```

#### Methods

##### `extract_schema(report_id: str) -> SmartsheetSchema`

Extract schema information from a report.

##### `extract_data(report_id: str, progress_callback: Optional[Callable] = None) -> Generator[List[SmartsheetRow], None, ExtractionProgress]`

Extract data from a report with pagination.

**Note:** Reports support pagination up to 10,000 rows per page.

## Configuration API

### Configuration Classes

The ss2db library uses Pydantic models for type-safe configuration.

#### SmartsheetConfig

```python
class SmartsheetConfig(BaseModel):
    api_base_url: str = "https://api.smartsheet.com/2.0"
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    rate_limit_buffer: int = 5
```

#### OutputConfig

```python
class OutputConfig(BaseModel):
    directory: str = "./exports"
    file_prefix: str = "smartsheet"
    backup_existing: bool = True
    compression: bool = False
    timestamp_format: str = "%Y%m%d_%H%M%S"
```

#### PostgreSQLConfig

```python
class PostgreSQLConfig(BaseModel):
    schema_name: str = "public"
    table_prefix: str = "smartsheet_"
    create_indexes: bool = True
    include_metadata_columns: bool = True
    batch_size: int = 1000
    quote_identifiers: bool = True
    use_jsonb: bool = True
```

#### MySQLConfig

```python
class MySQLConfig(BaseModel):
    database_name: Optional[str] = None
    table_prefix: str = "smartsheet_"
    create_indexes: bool = True
    include_metadata_columns: bool = True
    batch_size: int = 1000
    quote_identifiers: bool = True
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    collation: str = "utf8mb4_unicode_ci"
    use_json: bool = True
```

#### ProcessingConfig

```python
class ProcessingConfig(BaseModel):
    validate_data: bool = True
    skip_empty_rows: bool = True
    handle_duplicates: str = "error"  # "error", "skip", "overwrite"
    date_format: str = "iso"
    timezone: str = "UTC"
    max_field_length: int = 65535
    null_values: List[str] = ["", "NULL", "null", "None"]
```

#### LoggingConfig

```python
class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "detailed"
    file_rotation: bool = True
    max_file_size: str = "10MB"
    backup_count: int = 5
```

#### AdvancedConfig

```python
class AdvancedConfig(BaseModel):
    memory_limit_mb: int = 1024
    chunk_size: int = 10000
    parallel_processing: bool = False
    cache_responses: bool = True
    cache_ttl_hours: int = 24
```

### ConfigManager

Manages configuration loading from multiple sources.

#### Class Definition

```python
class ConfigManager:
    def __init__(
        self, 
        config_path: Optional[str] = None, 
        env_file: Optional[str] = None
    ) -> None
```

#### Methods

##### `load() -> Config`

Load configuration from files and environment variables.

##### `get_api_token() -> str`

Get Smartsheet API token from environment.

##### `get_database_config(db_type: str = "postgresql") -> Optional[Dict[str, str]]`

Get database configuration from environment.

### Function: `load_config`

```python
def load_config(
    config_path: Optional[str] = None, 
    env_file: Optional[str] = None
) -> Tuple[Config, ConfigManager]
```

Load configuration and return config object and manager.

**Example:**
```python
from ss2db.config import load_config

config, manager = load_config("custom_config.yaml", ".env.production")
api_token = manager.get_api_token()
```

## Utility APIs

### File Operations

The `ss2db.utils.files` module provides file management utilities.

#### Functions

##### `get_file_manager(config: Dict[str, Any]) -> FileManager`

Get configured file manager instance.

##### `get_output_manager(config: Dict[str, Any]) -> OutputManager`

Get configured output manager instance.

### Logging

The `ss2db.utils.logging` module provides structured logging.

#### Functions

##### `get_logger(name: str) -> logging.Logger`

Get configured logger instance.

##### `setup_logging(...) -> logging.Logger`

Set up logging with specified configuration.

##### `log_operation_start(logger, operation: str, **kwargs) -> None`

Log the start of an operation with context.

##### `log_operation_complete(logger, operation: str, duration: float) -> None`

Log operation completion with timing.

## Error Handling

### SmartsheetAPIError

Primary exception class for API-related errors.

#### Class Definition

```python
class SmartsheetAPIError(Exception):
    def __init__(
        self, 
        status_code: int, 
        message: str, 
        response_data: Optional[Dict] = None
    ) -> None
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `message` | `str` | Error message |
| `response_data` | `Dict` | API response data |

#### Common Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| `400` | Bad Request | Check request parameters |
| `401` | Unauthorized | Check API token |
| `403` | Forbidden | Check permissions |
| `404` | Not Found | Verify sheet/report ID |
| `429` | Rate Limited | Automatic retry with backoff |
| `500-504` | Server Error | Automatic retry with backoff |

#### Example Error Handling

```python
from ss2db.smartsheet.client import SmartsheetClient, SmartsheetAPIError

try:
    client = SmartsheetClient("token")
    data = client.get_sheet("invalid_id")
except SmartsheetAPIError as e:
    if e.status_code == 404:
        print("Sheet not found")
    elif e.status_code == 401:
        print("Invalid API token")
    else:
        print(f"API error {e.status_code}: {e.message}")
```

## Examples

### Basic Data Extraction

```python
from ss2db.smartsheet.client import SmartsheetClient
from ss2db.smartsheet.extractors import SheetExtractor
import json

# Initialize client
client = SmartsheetClient("your_api_token")

# Extract schema
extractor = SheetExtractor(client)
schema = extractor.extract_schema("1234567890")

# Extract data with progress tracking
def progress_callback(progress):
    if progress.extracted_rows % 1000 == 0:
        print(f"Extracted {progress.extracted_rows} rows...")

all_rows = []
for chunk in extractor.extract_data("1234567890", progress_callback):
    all_rows.extend(chunk)

print(f"Total rows extracted: {len(all_rows)}")
```

### Report Processing with Pagination

```python
from ss2db.smartsheet.extractors import ReportExtractor

# Initialize report extractor
extractor = ReportExtractor(client, {
    "chunk_size": 5000,  # Adjust for memory constraints
    "memory_limit_mb": 512
})

# Extract report data (automatically handles pagination)
schema = extractor.extract_schema("9876543210")
total_rows = 0

for chunk in extractor.extract_data("9876543210"):
    total_rows += len(chunk)
    # Process chunk immediately to save memory
    process_chunk(chunk)

print(f"Processed {total_rows} rows from report")
```

### Custom Configuration

```python
from ss2db.config import Config, SmartsheetConfig, PostgreSQLConfig

# Create custom configuration
config = Config(
    smartsheet=SmartsheetConfig(
        request_timeout=60,
        retry_attempts=5,
        rate_limit_buffer=10
    ),
    database=DatabaseConfig(
        type="postgresql",
        postgresql=PostgreSQLConfig(
            schema_name="warehouse",
            table_prefix="import_",
            batch_size=2000,
            use_jsonb=True
        )
    )
)

# Use with client
client = SmartsheetClient("token", config.smartsheet.dict())
```

### Memory-Efficient Large Dataset Processing

```python
from ss2db.smartsheet.extractors import SheetExtractor
from ss2db.database.postgresql import PostgreSQLGenerator
import json

# Configure for large datasets
extractor = SheetExtractor(client, {
    "chunk_size": 2000,       # Smaller chunks
    "memory_limit_mb": 256,   # Conservative memory limit
    "validate_data": True     # Enable data validation
})

# Stream processing - never load all data into memory
schema = extractor.extract_schema("large_sheet_id")
generator = PostgreSQLGenerator({"batch_size": 500})

# Process in streaming fashion
with open("output.sql", "w") as sql_file:
    # Write schema
    sql_file.write(generator.generate_create_table_sql(schema))
    sql_file.write("\n")
    
    # Process data in chunks
    for chunk in extractor.extract_data("large_sheet_id"):
        # Convert to dict format
        dict_rows = [row.to_dict(schema.columns) for row in chunk]
        
        # Generate SQL for this chunk
        sql_batch = generator.generate_insert_sql_batch_from_dict(
            dict_rows, schema
        )
        sql_file.write(sql_batch)
        sql_file.write("\n")
```

### Rate Limit Monitoring

```python
import time
from ss2db.smartsheet.client import SmartsheetClient

client = SmartsheetClient("token", {
    "rate_limit_buffer": 10  # More conservative rate limiting
})

# Monitor rate limit usage
for i in range(10):
    try:
        data = client.get_sheet(f"sheet_{i}")
        
        # Check rate limit status
        status = client.get_rate_limit_status()
        print(f"Request {i}: {status['usage_percentage']:.1f}% of rate limit used")
        
        if status['usage_percentage'] > 80:
            print("Approaching rate limit, slowing down...")
            time.sleep(2)
            
    except SmartsheetAPIError as e:
        if e.status_code == 429:
            print("Hit rate limit, waiting...")
            time.sleep(60)
        else:
            raise
```

### Error Recovery and Retry Logic

```python
from ss2db.smartsheet.client import SmartsheetClient, SmartsheetAPIError
import time

def robust_data_extraction(sheet_ids, max_retries=3):
    """Extract data with comprehensive error handling."""
    client = SmartsheetClient("token")
    results = {}
    
    for sheet_id in sheet_ids:
        retries = 0
        while retries < max_retries:
            try:
                data = client.get_sheet(sheet_id)
                results[sheet_id] = data
                print(f"✓ Successfully extracted {sheet_id}")
                break
                
            except SmartsheetAPIError as e:
                retries += 1
                
                if e.status_code == 404:
                    print(f"✗ Sheet {sheet_id} not found, skipping")
                    break
                elif e.status_code in [500, 502, 503, 504]:
                    wait_time = 2 ** retries  # Exponential backoff
                    print(f"Server error for {sheet_id}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                elif e.status_code == 429:
                    print(f"Rate limited for {sheet_id}, waiting 60s...")
                    time.sleep(60)
                else:
                    print(f"✗ Failed to extract {sheet_id}: {e}")
                    break
                    
            except Exception as e:
                print(f"✗ Unexpected error for {sheet_id}: {e}")
                break
    
    return results
```

This API reference provides comprehensive documentation for programmatic use of the ss2db library. For CLI usage, see the main README.md and for development guidance, see DEVELOPER_GUIDE.md.