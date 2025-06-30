# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Smartsheet to Database Export Project

## Project Overview

This project implements a data export system to transfer data from Smartsheet to PostgreSQL and MySQL databases. The system handles complex data type mapping, API rate limiting, bulk operations, and provides comprehensive monitoring capabilities.

## Development Commands

Since this is a new project, common development commands will be added as the implementation progresses. Expected commands will include:
- Database setup and migration scripts
- API token configuration  
- Data export execution
- Testing and validation utilities

## Architecture

The system is designed with four main phases:
1. **Setup**: API authentication and database connection
2. **Schema Generation**: Dynamic table creation based on Smartsheet structure  
3. **Data Export**: Bulk data transfer with type conversion
4. **Error Handling & Optimization**: Rate limiting, monitoring, and incremental updates

## Key Implementation Notes

- All API requests must include `level=2` and `objectValue=true` parameters for complex data types
- PostgreSQL JSONB and MySQL JSON are used for Smartsheet's complex types (contacts, multi-select, predecessors)
- Bulk operations use psycopg2's execute_values for optimal performance
- Rate limiting: 100 requests per minute with exponential backoff
- Data validation includes constraint checking and truncation for oversized values

# ss2db Application Requirements

## Core Application Specifications

### Application Details
- **Name**: `ss2db` (Smartsheet to Database)
- **Language**: Python 3.12
- **Type**: Command-line application
- **Purpose**: Extract Smartsheet data and generate database import scripts for PostgreSQL and MySQL

### Core Functionality
1. **Smartsheet API Integration**
   - Connect to Smartsheet API using bearer token authentication
   - Support both sheet and report data extraction
   - Handle API rate limiting with exponential backoff
   - Include required parameters: `level=2`, `objectValue=true`, `include=columnType,format`

2. **Data Extraction Phase**
   - Extract complete data from specified sheet or report
   - Save raw data to local JSON file (`{sheet_id}_data.json`)
   - Handle pagination for large datasets (>10,000 rows)
   - Support incremental extraction with date filters

3. **Schema Extraction Phase**
   - Extract column metadata and data types
   - Save schema information to local JSON file (`{sheet_id}_schema.json`)
   - Map Smartsheet column types to PostgreSQL equivalents
   - Store column order, constraints, and formatting information

4. **Database Script Generation Phase**
   - Generate CREATE TABLE statement with proper data types for PostgreSQL or MySQL
   - Generate INSERT statements with parameterized queries
   - Create complete SQL script file (`{sheet_id}_import.sql`)
   - Handle data type conversions and NULL values
   - Include table constraints and indexes
   - Support database-specific syntax and features

## Configuration Management

### Environment Variables (.env)
```
SMARTSHEET_API_TOKEN=your_api_token_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_database
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

### Configuration File (config.yaml)
```yaml
# Smartsheet Configuration
smartsheet:
  api_base_url: "https://api.smartsheet.com/2.0"
  request_timeout: 30
  retry_attempts: 3
  retry_delay: 5

# Output Configuration
output:
  directory: "./exports"
  file_prefix: "smartsheet"
  backup_existing: true
  compression: false

# PostgreSQL Configuration
postgresql:
  schema_name: "public"
  table_prefix: "smartsheet_"
  create_indexes: true
  include_metadata_columns: true
  batch_size: 1000

# Processing Options
processing:
  validate_data: true
  skip_empty_rows: true
  handle_duplicates: "error"  # error, skip, overwrite
  date_format: "iso"
  timezone: "UTC"
```

## Command Line Interface

### Basic Usage
```bash
# Extract sheet data and generate PostgreSQL SQL
ss2db --sheet-id 1234567890 --output-dir ./exports --db-type postgresql

# Extract report data and generate MySQL SQL
ss2db --report-id 9876543210 --output-dir ./exports --db-type mysql

# Skip phases
ss2db --sheet-id 1234567890 --skip-extraction --input-file data.json

# Dry run mode
ss2db --sheet-id 1234567890 --dry-run --verbose --db-type postgresql
```

### Command Line Arguments
- `--sheet-id`: Smartsheet sheet ID to process
- `--report-id`: Smartsheet report ID to process
- `--output-dir`: Directory for output files (default: ./exports)
- `--config`: Path to config.yaml file (default: ./config.yaml)
- `--env-file`: Path to .env file (default: ./.env)
- `--skip-extraction`: Skip data extraction phase
- `--skip-schema`: Skip schema extraction phase
- `--skip-sql`: Skip SQL generation phase
- `--input-data`: Use existing data file instead of API call
- `--input-schema`: Use existing schema file instead of API call
- `--table-name`: Override database table name
- `--db-type`: Database type to generate scripts for (postgresql or mysql)
- `--dry-run`: Show what would be done without executing
- `--verbose`: Enable detailed logging
- `--quiet`: Suppress non-error output
- `--log-file`: Write logs to specified file

## Advanced Features

### Phase Control
- Allow skipping individual phases for workflow flexibility
- Support resuming from specific phase using existing files
- Validate input files before processing subsequent phases

### Data Processing
- Memory-efficient streaming for large datasets
- Progress indicators with ETA for long operations
- Data validation with detailed error reporting
- Support for custom field transformations via config

### Error Handling
- Comprehensive error logging with context
- Graceful handling of API errors and network issues
- Data validation with clear error messages
- Recovery options for partial failures

### Output Options
- Multiple output formats: JSON, CSV, Parquet
- Compressed output options (gzip, zip)
- Backup existing files before overwriting
- Timestamped output directories

### Connection Testing
- Test Smartsheet API connectivity
- Validate PostgreSQL connection parameters
- Check permissions and access rights
- Verify target database exists

### Monitoring and Logging
- Structured logging with configurable levels
- Progress tracking for long-running operations
- Performance metrics and timing information
- API usage monitoring and rate limit tracking

## File Structure

### Output Files
```
exports/
├── {sheet_id}/
│   ├── {timestamp}_data.json          # Raw Smartsheet data
│   ├── {timestamp}_schema.json        # Column metadata
│   ├── {timestamp}_import.sql         # PostgreSQL script
│   ├── {timestamp}_log.txt           # Execution log
│   └── config_used.yaml              # Config snapshot
```

### Application Structure
```
ss2db/
├── ss2db/
│   ├── __init__.py
│   ├── main.py                       # CLI entry point
│   ├── config.py                     # Configuration management
│   ├── smartsheet/
│   │   ├── __init__.py
│   │   ├── client.py                 # API client
│   │   ├── models.py                 # Data models
│   │   └── extractors.py             # Data extraction
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py                 # Schema generation
│   │   ├── queries.py                # SQL generation
│   │   ├── postgresql.py             # PostgreSQL-specific code
│   │   ├── mysql.py                  # MySQL-specific code
│   │   └── types.py                  # Type mapping
│   └── utils/
│       ├── __init__.py
│       ├── logging.py                # Logging setup
│       ├── validation.py             # Data validation
│       └── files.py                  # File operations
├── tests/
├── config.yaml.example
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

# Smartsheet API Data Export Capabilities

# Primary Export Methods
- `GET / sheets/{sheetId}` - Complete sheet data with columns, rows, and cells
- `GET / reports/{reportId}` - Filtered report data(max 10, 000 rows per request)
- Both return JSON with full metadata and type information

# Critical API Parameters
- `level = 2` - Enables multi-contact and multi-picklist data types
- `objectValue = true` - Required for complex data structures
- `include = columnType, format` - Returns column metadata and formatting
- `pageSize = 10000` - Maximum rows per request for reports

# API Request Example
```bash
curl - H "Authorization: Bearer YOUR_TOKEN" \
    "https://api.smartsheet.com/2.0/sheets/SHEET_ID?level=2&include=columnType&objectValue=true"
```

# Complete Data Type Mapping

### PostgreSQL Data Type Mapping

| Smartsheet Type | PostgreSQL Type | Notes |
|----------------- | ----------------- | -------|
| `TEXT_NUMBER` | `TEXT` | Handles both text and numeric values |
| `CHECKBOX` | `BOOLEAN` | Direct mapping for true/false |
| `CONTACT_LIST` | `JSONB` | Stores `{email, displayValue}` object |
| `DATE` | `DATE` | ISO format YYYY-MM-DD |
| `DATETIME` | `TIMESTAMPTZ` | UTC timestamps with timezone |
| `ABSTRACT_DATETIME` | `TIMESTAMPTZ` | System datetime(read-only) |
| `DURATION` | `INTERVAL` | Native PostgreSQL duration type |
| `MULTI_CONTACT_LIST` | `JSONB` | Array of contact objects |
| `PICKLIST` | `VARCHAR(255)` | Single dropdown selection |
| `MULTI_PICKLIST` | `JSONB` | Array of selected values |
| `PREDECESSOR` | `JSONB` | Complex dependency relationships |

### MySQL Data Type Mapping

| Smartsheet Type | MySQL Type | Notes |
|----------------- | ----------- | -------|
| `TEXT_NUMBER` | `TEXT` | Handles both text and numeric values |
| `CHECKBOX` | `BOOLEAN` / `TINYINT(1)` | MySQL boolean equivalent |
| `CONTACT_LIST` | `JSON` | Stores `{email, displayValue}` object (MySQL 5.7+) |
| `DATE` | `DATE` | ISO format YYYY-MM-DD |
| `DATETIME` | `DATETIME` | UTC timestamps |
| `ABSTRACT_DATETIME` | `TIMESTAMP` | System datetime with auto-update |
| `DURATION` | `TIME` | Time interval representation |
| `MULTI_CONTACT_LIST` | `JSON` | Array of contact objects |
| `PICKLIST` | `VARCHAR(255)` | Single dropdown selection |
| `MULTI_PICKLIST` | `JSON` | Array of selected values |
| `PREDECESSOR` | `JSON` | Complex dependency relationships |

# Implementation Strategy

# 1. Schema Generation Process
```python


def generate_schema(sheet_id, api_token):
    """Generate PostgreSQL schema from Smartsheet columns"""
    columns = get_smartsheet_columns(sheet_id, api_token)
    schema_parts = []

    for col in columns:
        pg_type = map_smartsheet_to_postgres(col['type'])
        safe_name = sanitize_column_name(col['title'])
        schema_parts.append(f'"{safe_name}" {pg_type}')

    return f"CREATE TABLE smartsheet_{sheet_id} (\n  " + ",\n  ".join(schema_parts) + "\n);"


def map_smartsheet_to_postgres(smartsheet_type):
    """Map Smartsheet column types to PostgreSQL types"""
    mapping = {
        'TEXT_NUMBER': 'TEXT',
        'CHECKBOX': 'BOOLEAN',
        'CONTACT_LIST': 'JSONB',
        'DATE': 'DATE',
        'DATETIME': 'TIMESTAMPTZ',
        'ABSTRACT_DATETIME': 'TIMESTAMPTZ',
        'DURATION': 'INTERVAL',
        'MULTI_CONTACT_LIST': 'JSONB',
        'PICKLIST': 'VARCHAR(255)',
        'MULTI_PICKLIST': 'JSONB',
        'PREDECESSOR': 'JSONB'
    }
    return mapping.get(smartsheet_type, 'TEXT')


```

# 2. Data Transformation Strategy
```python


def transform_cell_value(cell, column_type):
    """Transform Smartsheet cell data for PostgreSQL"""
    if not cell or 'value' not in cell:
        return None

    if column_type == 'CHECKBOX':
        return bool(cell.get('value'))

    elif column_type in ['CONTACT_LIST', 'MULTI_CONTACT_LIST']:
        if 'objectValue' in cell:
            return json.dumps(cell['objectValue'])
        return None

    elif column_type in ['DATE', 'DATETIME', 'ABSTRACT_DATETIME']:
        if cell['value']:
            # Convert ISO string to appropriate format
            return parse_iso_datetime(cell['value'])

    elif column_type in ['MULTI_PICKLIST', 'PREDECESSOR']:
        if 'objectValue' in cell:
            return json.dumps(cell['objectValue'])
        return cell.get('value')

    else:  # TEXT_NUMBER, PICKLIST, etc.
        return cell.get('value')


```

# 3. Recommended Table Structure
```sql
-- Main data table
CREATE TABLE smartsheet_data(
    smartsheet_row_id BIGINT PRIMARY KEY,
    smartsheet_sheet_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    modified_at TIMESTAMPTZ DEFAULT NOW(),
    -- Dynamic columns based on sheet structure
    CONSTRAINT unique_sheet_row UNIQUE(smartsheet_sheet_id, smartsheet_row_id)
)

-- Metadata table for column mapping
CREATE TABLE smartsheet_columns(
    id SERIAL PRIMARY KEY,
    sheet_id BIGINT NOT NULL,
    column_id BIGINT NOT NULL,
    column_title TEXT NOT NULL,
    smartsheet_type TEXT NOT NULL,
    postgres_type TEXT NOT NULL,
    column_index INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_sheet_column UNIQUE(sheet_id, column_id)
)

-- Export log table
CREATE TABLE smartsheet_exports(
    id SERIAL PRIMARY KEY,
    sheet_id BIGINT,
    report_id BIGINT,
    export_type VARCHAR(10) CHECK(export_type IN('sheet', 'report')),
    rows_exported INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT
)
```

# API Rate Limits and Constraints

# Limits
- **Rate limit**: 100 requests per minute
- **Numeric range**: -9007199254740992 to 9007199254740992
- **Contact list limit**: 1, 000 predefined contacts per column
- **Report export limit**: 10, 000 rows per request
- **Sheet size limits**: 20, 000 rows, 400 columns, or 500, 000 cells

# Data Handling Notes
- All dates returned in UTC ISO-8601 format: `YYYY-MM-DDTHH: MM: SSZ`
- Multi-contact/multi-picklist require `level = 2` parameter
- Complex types need `objectValue` for proper data extraction
- Pagination required for large datasets using `page` and `pageSize` parameters

# Implementation Checklist

# Phase 1: Setup
- [] Generate Smartsheet API token
- [] Set up PostgreSQL database and connection
- [] Implement authentication and basic API connectivity
- [] Create metadata tables

# Phase 2: Schema Generation
- [] Fetch column metadata from Smartsheet
- [] Map column types to PostgreSQL equivalents
- [] Generate and execute CREATE TABLE statements
- [] Store column mapping in metadata tables

# Phase 3: Data Export
- [] Implement pagination for large datasets
- [] Handle complex data types(JSONB conversion)
- [] Implement proper datetime conversion
- [] Add data validation and constraint checking

# Phase 4: Error Handling & Optimization
- [] Implement exponential backoff for rate limiting
- [] Add connection pooling for API requests
- [] Implement bulk INSERT operations
- [] Add comprehensive logging and monitoring
- [] Plan for incremental updates(UPSERT strategy)

# Error Handling Strategy

# API Error Responses
```python


def handle_api_error(response):
    """Handle Smartsheet API error responses"""
    if response.status_code == 429:  # Rate limited
        retry_after = response.headers.get('Retry-After', 60)
        time.sleep(int(retry_after))
        return 'retry'

    elif response.status_code in [500, 502, 503, 504]:  # Server errors
        return 'retry_with_backoff'

    elif response.status_code == 404:  # Not found
        return 'skip'

    else:  # Client errors (400, 401, 403)
        raise Exception(f"API Error {response.status_code}: {response.text}")


```

# Data Validation
```python


def validate_data_constraints(value, postgres_type):
    """Validate data fits PostgreSQL constraints"""
    if postgres_type == 'VARCHAR(255)' and value and len(str(value)) > 255:
        return str(value)[:255]  # Truncate

    if postgres_type == 'BOOLEAN' and value not in [True, False, None]:
        return None  # Invalid boolean

    return value


```

# Performance Optimization

# Database Indexing Strategy
```sql
-- Indexes for common query patterns
CREATE INDEX idx_smartsheet_data_sheet_id ON smartsheet_data(smartsheet_sheet_id)
CREATE INDEX idx_smartsheet_data_modified ON smartsheet_data(modified_at)

-- JSONB indexes for contact and multi-select columns
CREATE INDEX idx_contact_email ON smartsheet_data USING GIN((contact_column -> >'email'))
CREATE INDEX idx_multi_select_values ON smartsheet_data USING GIN(multi_select_column)
```

# Bulk Operations
```python


def bulk_insert_rows(connection, table_name, rows, batch_size=1000):
    """Perform bulk INSERT with batching"""
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        # Use psycopg2's execute_values for optimal performance
        execute_values(
            connection.cursor(),
            f"INSERT INTO {table_name} VALUES %s",
            batch,
            template=None,
            page_size=batch_size
        )
        connection.commit()


```

# Security Considerations

- Store API tokens securely(environment variables, key vault)
- Use connection pooling with proper timeout settings
- Implement proper SQL injection prevention
- Log access and operations for audit trails
- Consider data encryption for sensitive contact information

# Monitoring and Maintenance

- Monitor API rate limit usage
- Track export success/failure rates
- Set up alerts for prolonged failures
- Regular validation of data integrity
- Plan for Smartsheet schema changes
