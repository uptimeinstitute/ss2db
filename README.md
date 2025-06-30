# ss2db - Smartsheet to Database Export Tool

[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/uptimeinstitute/ss2db/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)](https://github.com/uptimeinstitute/ss2db)

A powerful command-line tool for extracting data from Smartsheet and generating database import scripts for PostgreSQL and MySQL. Designed to handle large datasets with rate limiting, pagination, and comprehensive error handling.

## Features

- 🚀 **High Performance**: Handles 90K+ row datasets with chunked processing
- 🔄 **Rate Limiting**: Respects Smartsheet API limits (100 req/min) with automatic backoff
- 📊 **Dual Database Support**: Generates scripts for both PostgreSQL and MySQL
- 🗂️ **Complex Data Types**: Supports JSONB/JSON for contacts, multi-select, and attachments
- 📈 **Progress Tracking**: Real-time progress updates with ETA estimates
- 🛡️ **Error Handling**: Comprehensive retry logic and data validation
- 🔧 **Flexible Workflow**: Skip phases, use existing files, dry-run mode
- 📋 **Metadata Capture**: Complete schema information and column mappings

## Installation

### Prerequisites

- Python 3.12 or higher
- Smartsheet API token
- PostgreSQL and/or MySQL database (for testing connections)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/uptimeinstitute/ss2db.git
cd ss2db

# Install in development mode
pip install -e .
```

### Running the Application

After installation, you can run ss2db in several ways:

```bash
# Method 1: Using the installed command (recommended)
ss2db --help

# Method 2: As a Python module
python -m ss2db --help

# Method 3: Direct execution (development only)
python ss2db/main.py --help
```

**Note**: If you get "command not found" errors, ensure you have installed the package with `pip install -e .` or use the module method: `python -m ss2db`.

## Quick Start

### 1. Set up Environment

Create a `.env` file with your Smartsheet API token:

```bash
cp .env.example .env
# Edit .env and add your SMARTSHEET_API_TOKEN
```

### 2. Configure Application

Copy and customize the configuration:

```bash
cp config.yaml.example config.yaml
# Edit config.yaml to adjust settings
```

### 3. Extract Data

```bash
# Extract from a Smartsheet report to PostgreSQL
ss2db --report-id 1234567890 --db-type postgresql

# Extract from a sheet to MySQL
ss2db --sheet-id 9876543210 --db-type mysql --output-dir ./my-exports

# Dry run to see what would happen
ss2db --report-id 1234567890 --dry-run --verbose
```

## Usage

### Basic Commands

```bash
# Extract complete workflow
ss2db --report-id REPORT_ID --db-type postgresql

# Skip specific phases
ss2db --sheet-id SHEET_ID --skip-extraction --input-data existing_data.json

# Use existing files
ss2db --report-id REPORT_ID --skip-extraction --skip-schema \
      --input-data data.json --input-schema schema.json

# Test with small sample
ss2db --report-id REPORT_ID --dry-run --verbose
```

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--sheet-id` | Smartsheet sheet ID to process | `--sheet-id 1234567890` |
| `--report-id` | Smartsheet report ID to process | `--report-id 9876543210` |
| `--db-type` | Database type (postgresql/mysql) | `--db-type postgresql` |
| `--output-dir` | Output directory | `--output-dir ./exports` |
| `--table-name` | Override table name | `--table-name my_data` |
| `--config` | Config file path | `--config my-config.yaml` |
| `--env-file` | Environment file path | `--env-file my.env` |
| `--skip-extraction` | Skip data extraction phase | `--skip-extraction` |
| `--skip-schema` | Skip schema extraction phase | `--skip-schema` |
| `--skip-sql` | Skip SQL generation phase | `--skip-sql` |
| `--input-data` | Use existing data file | `--input-data data.json` |
| `--input-schema` | Use existing schema file | `--input-schema schema.json` |
| `--dry-run` | Show what would be done | `--dry-run` |
| `--verbose` | Enable verbose logging | `--verbose` |
| `--quiet` | Suppress non-error output | `--quiet` |
| `--log-file` | Write logs to file | `--log-file export.log` |

## Configuration

### Environment Variables (.env)

```bash
# Required: Smartsheet API Token
SMARTSHEET_API_TOKEN=your_api_token_here

# Optional: Database connection testing
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=test_db
POSTGRES_USER=username
POSTGRES_PASSWORD=password

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=test_db
MYSQL_USER=username
MYSQL_PASSWORD=password
```

### Application Configuration (config.yaml)

```yaml
# Smartsheet API settings
smartsheet:
  api_base_url: "https://api.smartsheet.com/2.0"
  request_timeout: 30
  retry_attempts: 3
  retry_delay: 5
  rate_limit_buffer: 5

# Output configuration
output:
  directory: "./exports"
  file_prefix: "smartsheet"
  backup_existing: true
  compression: false
  timestamp_format: "%Y%m%d_%H%M%S"

# Database settings
database:
  type: "postgresql"  # or "mysql"

  postgresql:
    schema_name: "public"
    table_prefix: "smartsheet_"
    create_indexes: true
    include_metadata_columns: true
    use_jsonb: true

  mysql:
    database_name: null
    table_prefix: "smartsheet_"
    create_indexes: true
    include_metadata_columns: true
    engine: "InnoDB"
    charset: "utf8mb4"
    use_json: true

# Processing options
processing:
  validate_data: true
  skip_empty_rows: true
  handle_duplicates: "error"
  date_format: "iso"
  timezone: "UTC"

# Advanced settings
advanced:
  memory_limit_mb: 1024
  chunk_size: 10000
  parallel_processing: false
  cache_responses: true
```

## Data Type Mapping

### PostgreSQL Mapping

| Smartsheet Type | PostgreSQL Type | Notes |
|----------------|-----------------|--------|
| `TEXT_NUMBER` | `TEXT` | Handles both text and numeric |
| `CHECKBOX` | `BOOLEAN` | Direct boolean mapping |
| `CONTACT_LIST` | `JSONB` | `{email, displayValue}` object |
| `MULTI_CONTACT_LIST` | `JSONB` | Array of contact objects |
| `DATE` | `DATE` | ISO format YYYY-MM-DD |
| `DATETIME` | `TIMESTAMPTZ` | UTC with timezone |
| `DURATION` | `INTERVAL` | Native PostgreSQL duration |
| `PICKLIST` | `VARCHAR(255)` | Single selection |
| `MULTI_PICKLIST` | `JSONB` | Array of values |
| `PREDECESSOR` | `JSONB` | Complex dependencies |

### MySQL Mapping

| Smartsheet Type | MySQL Type | Notes |
|----------------|------------|--------|
| `TEXT_NUMBER` | `TEXT` | Handles both text and numeric |
| `CHECKBOX` | `BOOLEAN` | MySQL boolean equivalent |
| `CONTACT_LIST` | `JSON` | `{email, displayValue}` object |
| `MULTI_CONTACT_LIST` | `JSON` | Array of contact objects |
| `DATE` | `DATE` | ISO format YYYY-MM-DD |
| `DATETIME` | `DATETIME` | UTC timestamps |
| `DURATION` | `TIME` | Time interval |
| `PICKLIST` | `VARCHAR(255)` | Single selection |
| `MULTI_PICKLIST` | `JSON` | Array of values |
| `PREDECESSOR` | `JSON` | Complex dependencies |

## Output Files

### File Structure

```
exports/
├── {resource_id}/
│   ├── {timestamp}_data.json          # Raw Smartsheet data
│   ├── {timestamp}_schema.json        # Column metadata
│   ├── {timestamp}_import.sql         # Database import script
│   ├── {timestamp}_log.txt           # Execution log
│   └── config_used.yaml              # Configuration snapshot
```

### Data File Format

```json
{
  "metadata": {
    "id": 1234567890,
    "name": "Project Data",
    "source_type": "report",
    "total_row_count": 1000,
    "columns": [...]
  },
  "rows": [
    {
      "smartsheet_row_id": 123,
      "Task Name": "Setup Environment",
      "Assigned To": {"email": "user@example.com", "displayValue": "User Name"},
      "Status": "In Progress",
      "Due Date": "2024-01-15",
      "Complete": false
    }
  ]
}
```

### Schema File Format

```json
{
  "id": 1234567890,
  "name": "Project Data",
  "source_type": "report",
  "total_row_count": 1000,
  "columns": [
    {
      "id": 456789,
      "title": "Task Name",
      "type": "TEXT_NUMBER",
      "postgres_type": "TEXT",
      "mysql_type": "TEXT",
      "index": 0,
      "primary": false
    }
  ]
}
```

## Examples

### Large Dataset Extraction

```bash
# Extract a large report with progress tracking
ss2db --report-id 5001829600415620 \
      --db-type postgresql \
      --verbose \
      --log-file extraction.log

# Output:
# [INFO] Starting ss2db export (report=5001829600415620, postgresql)
# [INFO] ✓ Smartsheet API connection verified
# [INFO] Schema extracted: 42 columns, 93443 rows
# [INFO] Extracting data: 93443 rows, 42 columns
# [INFO] Progress: 10000/93443 rows (10.7%)
# [INFO] Progress: 20000/93443 rows (21.4%)
# [INFO] ✓ Data extraction completed: 93443 rows in 189.2s
```

### Multi-Phase Workflow

```bash
# Phase 1: Extract data and schema only
ss2db --report-id 1234567890 --skip-sql --db-type postgresql

# Phase 2: Generate PostgreSQL script from existing files
ss2db --report-id 1234567890 \
      --skip-extraction --skip-schema \
      --input-data exports/1234567890/20240115_143022_data.json \
      --input-schema exports/1234567890/20240115_143022_schema.json \
      --db-type postgresql

# Phase 3: Generate MySQL script from same data
ss2db --report-id 1234567890 \
      --skip-extraction --skip-schema \
      --input-data exports/1234567890/20240115_143022_data.json \
      --input-schema exports/1234567890/20240115_143022_schema.json \
      --db-type mysql
```

### Development Testing

```bash
# Test with Docker databases
cd docker && docker compose up -d postgres mysql

# Dry run to check API access
ss2db --report-id 1234567890 --dry-run --verbose

# Extract schema only for inspection
ss2db --sheet-id 9876543210 --skip-extraction --skip-sql

# Test different database types
ss2db --report-id 1234567890 --db-type postgresql --dry-run
ss2db --report-id 1234567890 --db-type mysql --dry-run
```

## Development

### Project Structure

```
ss2db/
├── ss2db/
│   ├── main.py                    # CLI entry point
│   ├── config.py                  # Configuration management
│   ├── smartsheet/
│   │   ├── client.py              # API client with rate limiting
│   │   ├── models.py              # Data models
│   │   └── extractors.py          # Data extraction logic
│   ├── database/
│   │   ├── __init__.py            # Database integration
│   │   ├── postgresql.py          # PostgreSQL-specific code
│   │   └── mysql.py               # MySQL-specific code
│   └── utils/
│       ├── logging.py             # Logging utilities
│       ├── files.py               # File operations
│       └── validation.py          # Data validation
├── docker/                       # Docker test environment
├── tests/                        # Unit tests
└── docs/                         # Documentation
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ss2db

# Run specific test
pytest tests/test_client.py::test_rate_limiting
```

### Docker Test Environment

```bash
# Start test databases
cd docker && docker compose up -d

# Test PostgreSQL connection
ss2db --report-id 1234567890 --db-type postgresql --dry-run

# Test MySQL connection
ss2db --report-id 1234567890 --db-type mysql --dry-run

# View databases via Adminer
open http://localhost:8080
```

## Performance

### Benchmarks

| Dataset Size | Extraction Time | Rate | Memory Usage |
|-------------|----------------|------|--------------|
| 1K rows | 2.1s | 476 rows/sec | 45MB |
| 10K rows | 18.3s | 546 rows/sec | 125MB |
| 50K rows | 94.7s | 528 rows/sec | 380MB |
| 93K rows | 189.2s | 492 rows/sec | 650MB |

### Optimization Tips

1. **Adjust chunk size**: Increase `chunk_size` for faster processing of large datasets
2. **Memory limits**: Set `memory_limit_mb` based on available system memory
3. **Rate limiting**: Increase `rate_limit_buffer` if you have dedicated API access
4. **Parallel processing**: Enable `parallel_processing` for multi-core systems
5. **Compression**: Enable `compression` for storage-constrained environments

## Troubleshooting

### Common Issues

**API Authentication Errors**
```bash
# Check your API token
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.smartsheet.com/2.0/users/me
```

**Rate Limiting**
```bash
# If you're hitting rate limits frequently, adjust the buffer
# In config.yaml:
smartsheet:
  rate_limit_buffer: 10  # Keep more requests in reserve
```

**Memory Issues**
```bash
# Reduce chunk size for large datasets
# In config.yaml:
advanced:
  chunk_size: 5000
  memory_limit_mb: 512
```

**Large Dataset Timeouts**
```bash
# Increase timeouts and use progress logging
ss2db --report-id LARGE_REPORT \
      --verbose \
      --log-file progress.log \
      --config large-dataset-config.yaml
```

### Debug Mode

```bash
# Enable debug logging
ss2db --report-id 1234567890 --verbose --log-file debug.log

# Test API connectivity separately
python test_smartsheet_api.py

# Inspect generated files
cat exports/1234567890/20240115_143022_schema.json | jq '.columns[0:5]'
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update documentation for user-facing changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 **Email**: kevin.jarnot@uptimeinstitute.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/uptimeinstitute/ss2db/issues)
- 📖 **Documentation**: [Wiki](https://github.com/uptimeinstitute/ss2db/wiki)

## Changelog

### v1.0.0 (Current - Production Release)

- ✅ Complete Smartsheet API integration with rate limiting
- ✅ Full PostgreSQL and MySQL SQL generation support
- ✅ Comprehensive data type mapping for all 13 Smartsheet column types
- ✅ Robust error handling and retry logic
- ✅ CLI interface with dry-run mode and flexible workflow options
- ✅ 83 comprehensive test cases with 80%+ core module coverage
- ✅ Docker test environment for development
- ✅ Progress tracking and detailed logging
- ✅ Production-ready documentation and configuration management

See [CHANGELOG.md](CHANGELOG.md) for complete release notes.

### Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed development roadmap including:
- 📈 Enhanced testing and configuration validation (v1.1.0)
- 🔄 Incremental sync and error recovery features (v1.2.0)  
- 🚀 Performance optimizations and advanced features (v1.3.0)
- 🏢 Enterprise integration capabilities (v1.4.0)