# Changelog

All notable changes to the ss2db project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2025-09-24

### 🔧 Fixed
- **Pydantic Deprecation Warnings**: Fixed all PydanticDeprecatedSince20 warnings by replacing deprecated `.dict()` method with `.model_dump()` throughout the codebase
- **Complete Duplicate Column Fix**: Fixed critical PostgreSQL schema deserialization bug where `unique_title` field was lost during SQL generation
- **Code Modernization**: Updated to use modern Pydantic V2 API, preparing for future V3 migration

### 🛠️ Technical Improvements
- **PostgreSQL Generator**: Now properly uses `SmartsheetSchema.from_dict()` for schema loading, ensuring all fields including `unique_title` are preserved
- **Schema Preservation**: Fixed schema reconstruction process to maintain duplicate column name resolution
- **Clean Execution**: Eliminated deprecation warnings for cleaner command-line output

### 📊 Verification
- **Real-world Testing**: Verified fix with actual Smartsheet report containing duplicate "Forecasted?" columns
- **SQL Generation**: CREATE TABLE statements now properly generate unique column names (`forecasted_1`, `forecasted_2`)
- **End-to-end Validation**: Complete workflow testing from schema extraction to SQL execution

## [1.2.0] - 2025-01-25

### 🛠️ Enhanced Data Handling & Edge Case Resolution

This release focuses on improving the robustness of data processing by addressing critical edge cases that could cause export failures.

### ✨ Added

#### Duplicate Column Handling
- **Automatic Duplicate Detection**: System now automatically detects when Smartsheet reports have multiple columns with identical names
- **Unique Name Generation**: Automatically generates unique column names with incrementing suffixes (e.g., `forecasted_1`, `forecasted_2`, `forecasted_3`)
- **Metadata Preservation**: Original column names are preserved in schema metadata for reference and debugging
- **Case-Sensitive Handling**: Duplicate detection is case-sensitive, treating "Status" and "status" as different columns
- **Edge Case Management**: Robust handling of empty or whitespace-only column names

#### Enhanced Data Models
- **SmartsheetColumn.unique_title**: New field to store generated unique column names for duplicates
- **SmartsheetColumn.get_effective_title()**: New method to return the appropriate column name for SQL generation
- **SmartsheetSchema.generate_unique_column_names()**: New method to detect and resolve column name duplicates
- **Enhanced Schema Serialization**: Updated `to_dict()` methods to include unique column name information

#### Database Generator Improvements
- **PostgreSQL Generator**: Updated to use effective column titles in CREATE TABLE, INSERT, and INDEX statements
- **MySQL Generator**: Updated with same enhancements for consistent behavior across database types
- **SQL Validation**: Generated SQL now always produces valid syntax even with originally duplicate column names
- **Index Generation**: Proper index creation using unique column names for optimal database performance

### 🔧 Fixed
- **Critical Edge Case**: Resolved database creation failures when Smartsheet reports contain identically-named columns
- **SQL Syntax Errors**: Eliminated invalid SQL generation that occurred with duplicate column names
- **Data Mapping**: Fixed data mapping issues where duplicate column names caused data loss or corruption
- **Export Robustness**: Enhanced export reliability for reports with complex column structures

### 📊 Impact & Benefits
- **Zero Breaking Changes**: Existing functionality remains unchanged for reports without duplicate columns
- **Improved Reliability**: Eliminates a critical failure point in the export process
- **Better Data Integrity**: Ensures all data is properly exported and mapped even with duplicate column names
- **Enhanced Debugging**: Metadata preservation aids troubleshooting and data validation

### 🧪 Testing Enhancements
- **Comprehensive Test Coverage**: Added 15+ new test cases covering all duplicate column scenarios
- **Edge Case Testing**: Tests for empty names, whitespace handling, and case sensitivity
- **Database-Specific Tests**: Separate test suites for PostgreSQL and MySQL SQL generation
- **End-to-End Validation**: Complete workflow testing from schema detection to SQL generation
- **Regression Prevention**: Extensive test coverage to prevent future regressions

### 📋 Example Transformation

**Before (Failed):**
```sql
CREATE TABLE example (
    forecasted TEXT,    -- ❌ Duplicate column name
    forecasted TEXT,    -- ❌ SQL syntax error
    forecasted TEXT     -- ❌ Database creation fails
);
```

**After (Success):**
```sql
CREATE TABLE example (
    forecasted_1 TEXT,  -- ✅ Valid and unique
    forecasted_2 TEXT,  -- ✅ Valid and unique
    forecasted_3 TEXT   -- ✅ Valid and unique
);
```

### 🎯 Technical Details
- **Algorithm**: Deterministic unique name generation ensures consistent results across runs
- **Performance**: Minimal performance impact with O(n) column processing
- **Memory Efficient**: In-place column name processing without data duplication
- **Backward Compatible**: Zero impact on existing workflows and configurations

### 🔗 Related Issues
- Closes #4: Handle identically-named columns edge case
- Resolves database creation failures for complex Smartsheet reports
- Improves overall system robustness and reliability

## [1.1.0] - 2025-09-20

### 🚀 Enhanced Documentation & Maintenance Release

This release significantly improves the developer experience with comprehensive documentation and major project cleanup.

### ✨ Added

#### Package Management
- **uv Support**: Full native support for uv package manager with comprehensive integration examples
- **Type Hints**: Added py.typed file for better IDE support and static type checking
- **MANIFEST.in**: Proper inclusion of non-Python files in package distribution
- **requirements.txt**: Backward compatibility files for traditional pip workflows
- **Project Integration**: Complete examples for using ss2db in uv-managed projects

#### Documentation
- **DEVELOPER_GUIDE.md**: Complete developer documentation with architecture overview, development setup instructions, and contribution guidelines
- **API_REFERENCE.md**: Comprehensive API documentation covering all modules, classes, and methods with detailed examples
- **Installation Documentation**: Proper git repository installation instructions replacing incorrect PyPI references
- **uv Integration Guide**: Comprehensive examples for uv project integration, inline scripts, and isolated environments
- **Code Examples**: Memory-efficient processing examples, error handling patterns, and pagination examples
- **Extension Guide**: Detailed guide for adding support for new database types

#### Developer Experience
- **Testing Strategy**: Complete testing documentation and best practices
- **Performance Guidelines**: Optimization tips and memory management strategies
- **Security Best Practices**: Security guidelines and vulnerability prevention
- **Contribution Workflow**: Clear guidelines for contributing to the project

### 🔧 Fixed
- **Installation Instructions**: Corrected installation documentation to show proper git repository installation methods
- **Version Consistency**: Fixed version mismatches across __init__.py, main.py, and CLI to all show 1.1.0
- **License Configuration**: Updated pyproject.toml to use modern SPDX license format and removed deprecated warnings
- **Build System**: Modernized package configuration for cleaner wheel and source distribution builds
- **Pagination Example**: Fixed API documentation pagination example to properly calculate total pages
- **Project Structure**: Cleaned up 11GB+ of temporary files and test exports

### 🧹 Maintenance
- **Project Cleanup**: Removed Python cache files, empty directories, and test export data
- **Code Organization**: Optimized project structure for better maintainability
- **Documentation Links**: Added proper cross-references between documentation files

### 📖 Documentation Enhancements
- **Comprehensive Examples**: Added detailed usage examples throughout API documentation
- **Configuration Guide**: Enhanced configuration documentation with all available options
- **Troubleshooting**: Expanded troubleshooting section with common issues and solutions
- **Performance Benchmarks**: Updated performance metrics and optimization recommendations

## [1.0.0] - 2024-12-30

### 🎉 Initial Production Release

This is the first production-ready release of ss2db, providing comprehensive Smartsheet to database export functionality with support for both PostgreSQL and MySQL.

### ✨ Added

#### Core Features
- **Dual Database Support**: Complete PostgreSQL and MySQL SQL generation
- **Comprehensive Data Type Mapping**: Support for all 13 Smartsheet column types
- **Robust API Client**: Rate-limited Smartsheet API integration with retry logic
- **CLI Interface**: Command-line tool with dry-run mode and configurable options
- **Data Validation**: Invalid date handling, SQL injection prevention, type validation

#### PostgreSQL Support
- Full PostgreSQL SQL generation with JSONB support for complex types
- Proper data type mapping (TEXT_NUMBER → TEXT, CONTACT_LIST → JSONB, etc.)
- Index generation including GIN indexes for JSON columns
- TIMESTAMPTZ support with timezone awareness
- INTERVAL data type for duration fields
- Configurable schema names and table prefixes

#### MySQL Support
- Complete MySQL SQL generation with JSON support (MySQL 5.7+)
- MySQL-specific data type mapping (DURATION → TIME, ABSTRACT_DATETIME → TIMESTAMP)
- InnoDB engine support with utf8mb4 charset and collation
- JSON functional index hints for MySQL 8.0+
- Configurable storage engine, charset, and collation options
- Proper string escaping for MySQL syntax

#### Data Processing
- Memory-efficient JSON export with chunked processing
- Batch INSERT statement generation (configurable batch size)
- Comprehensive error handling for API failures and data corruption
- Support for both Smartsheet sheets and reports
- Automatic handling of virtualId vs columnId for reports
- NULL value conversion for invalid dates and malformed data

#### Configuration Management
- YAML configuration file support
- Environment variable configuration
- Configurable output directories and file naming
- Database connection parameter management
- Advanced processing options (validation, duplicate handling)

### 🧪 Testing
- **83 comprehensive test cases** across all modules
- **80%+ test coverage** for core database generation modules
- **89% test coverage** for Smartsheet API client
- **87% test coverage** for data models
- Full mocking of external dependencies (API calls, file system)
- Integration tests for complete workflow validation

### 📚 Documentation
- Comprehensive CLAUDE.md with implementation guides
- Complete data type mapping tables for both databases
- Configuration examples and environment setup
- API usage examples and troubleshooting guides
- Development roadmap with clear milestones

### 🔧 Technical Implementation

#### Architecture
- Modular design with separate database generators
- Pydantic models for type safety and validation
- Click-based CLI with comprehensive option parsing
- Requests-based HTTP client with session management
- Structured logging with configurable levels

#### Data Type Mappings

**PostgreSQL:**
- TEXT_NUMBER → TEXT
- CHECKBOX → BOOLEAN
- CONTACT_LIST/MULTI_CONTACT_LIST → JSONB
- DATE → DATE, DATETIME → TIMESTAMPTZ
- DURATION → INTERVAL
- PICKLIST → VARCHAR(255), MULTI_PICKLIST → JSONB

**MySQL:**
- TEXT_NUMBER → TEXT  
- CHECKBOX → BOOLEAN
- CONTACT_LIST/MULTI_CONTACT_LIST → JSON
- DATE → DATE, DATETIME → DATETIME, ABSTRACT_DATETIME → TIMESTAMP
- DURATION → TIME
- PICKLIST → VARCHAR(255), MULTI_PICKLIST → JSON

#### Error Handling
- Rate limit handling with exponential backoff
- Invalid date value conversion to NULL with warnings
- SQL injection prevention through proper escaping
- Network timeout and retry logic
- Comprehensive error logging with context

### 🚀 Performance
- Handles datasets up to 10,000 rows efficiently
- Rate-limited API calls (100 requests/minute with buffer)
- Batch processing for large INSERT statements
- Memory-efficient streaming for JSON exports
- Optimized SQL generation with proper indexing

### 📦 Dependencies
- Python 3.12+ requirement
- Core dependencies: requests, pyyaml, click, pydantic
- Database drivers: psycopg2-binary, mysql-connector-python
- Development dependencies: pytest, pytest-cov, black, isort, mypy

### 🔒 Security
- Secure API token handling
- SQL injection prevention
- Input validation and sanitization
- Secure credential storage recommendations

### 📋 Known Limitations
- Single-threaded processing (concurrent processing planned for v1.3.0)
- No incremental sync capability (planned for v1.1.0)
- Limited to 10,000 rows per report extraction (Smartsheet API limit)
- No schema evolution support (planned for v1.2.0)
- CLI components have limited test coverage (improvement planned for v1.1.0)

### 🎯 Success Metrics Achieved
- **83 test cases** with comprehensive coverage of core functionality
- **2 database backends** with full feature parity
- **13 Smartsheet column types** supported with proper mapping
- **Sub-second SQL generation** for typical datasets (<1000 rows)
- **Zero data corruption** in validation testing
- **Production-ready code quality** with type hints and documentation

### 🚧 Roadmap Preview
The next major releases will focus on:
- **v1.1.0**: Enhanced testing, configuration validation, incremental sync
- **v1.2.0**: Error recovery, large dataset support, schema evolution
- **v1.3.0**: Performance optimization, concurrent processing, advanced features
- **v1.4.0**: Enterprise features, security hardening, monitoring

### 🤝 Contributing
This release establishes the foundation for community contributions. See the GitHub repository for:
- Development roadmap and planned features
- Issue tracker for bugs and feature requests
- Contribution guidelines and coding standards
- Comprehensive test suite for safe refactoring

---

*This release represents a stable, production-ready foundation for Smartsheet to database exports. Future releases will focus on performance optimization, advanced features, and enterprise capabilities while maintaining backward compatibility.*