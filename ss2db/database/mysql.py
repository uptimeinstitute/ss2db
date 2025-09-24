"""
MySQL SQL generation for Smartsheet data.
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ss2db.smartsheet.models import SmartsheetSchema, SmartsheetColumn, SmartsheetRow, ColumnType
from ss2db.utils.logging import get_logger


class MySQLGenerator:
    """Generate MySQL SQL statements from Smartsheet data."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize MySQL generator with configuration."""
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Configuration options
        self.schema_name = self.config.get('schema_name', 'smartsheet')
        self.table_prefix = self.config.get('table_prefix', '')
        self.create_indexes = self.config.get('create_indexes', True)
        self.include_metadata_columns = self.config.get('include_metadata_columns', True)
        self.use_json = self.config.get('use_json', True)  # MySQL uses JSON, not JSONB
        self.quote_identifiers = self.config.get('quote_identifiers', True)
        self.batch_size = self.config.get('batch_size', 1000)
        
        # MySQL specific options
        self.engine = self.config.get('engine', 'InnoDB')
        self.charset = self.config.get('charset', 'utf8mb4')
        self.collation = self.config.get('collation', 'utf8mb4_unicode_ci')
        
        self.logger.info("MySQL generator initialized")
    
    def sanitize_identifier(self, name: str) -> str:
        """Sanitize column/table names for MySQL."""
        if not name:
            return "unnamed_column"
        
        # Convert to lowercase and replace special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip())
        sanitized = re.sub(r'_+', '_', sanitized)  # Replace multiple underscores with single
        sanitized = sanitized.strip('_').lower()
        
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"col_{sanitized}"
        
        # Handle empty result
        if not sanitized:
            sanitized = "unnamed_column"
        
        # Check against MySQL reserved words and add prefix if needed
        mysql_reserved = {
            'select', 'insert', 'update', 'delete', 'from', 'where', 'join', 'inner', 'outer',
            'left', 'right', 'on', 'as', 'and', 'or', 'not', 'null', 'true', 'false',
            'primary', 'key', 'foreign', 'references', 'unique', 'index', 'table', 'database',
            'create', 'drop', 'alter', 'add', 'column', 'constraint', 'default', 'auto_increment',
            'timestamp', 'datetime', 'date', 'time', 'year', 'varchar', 'char', 'text',
            'int', 'integer', 'bigint', 'decimal', 'float', 'double', 'boolean', 'json'
        }
        
        if sanitized.lower() in mysql_reserved:
            sanitized = f"col_{sanitized}"
        
        return sanitized
    
    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier for MySQL if needed."""
        if self.quote_identifiers:
            return f"`{identifier}`"
        return identifier
    
    def get_table_name(self, schema: SmartsheetSchema, custom_name: Optional[str] = None) -> str:
        """Generate table name from schema."""
        if custom_name:
            return custom_name
        
        prefix = self.table_prefix
        source_type = schema.source_type
        schema_id = schema.id
        
        return f"{prefix}{source_type}_{schema_id}"
    
    def convert_column_type(self, column: SmartsheetColumn) -> str:
        """Convert Smartsheet column type to MySQL type."""
        column_type = column.type
        
        # Data type mapping from Smartsheet to MySQL
        type_mapping = {
            ColumnType.TEXT_NUMBER: "TEXT",
            ColumnType.CHECKBOX: "BOOLEAN",
            ColumnType.CONTACT_LIST: "JSON" if self.use_json else "TEXT",
            ColumnType.DATE: "DATE",
            ColumnType.DATETIME: "DATETIME",
            ColumnType.ABSTRACT_DATETIME: "TIMESTAMP",
            ColumnType.DURATION: "TIME",  # MySQL doesn't have INTERVAL like PostgreSQL
            ColumnType.MULTI_CONTACT_LIST: "JSON" if self.use_json else "TEXT",
            ColumnType.PICKLIST: "VARCHAR(255)",
            ColumnType.MULTI_PICKLIST: "JSON" if self.use_json else "TEXT",
            ColumnType.PREDECESSOR: "JSON" if self.use_json else "TEXT",
            ColumnType.SYMBOL: "VARCHAR(50)",
            ColumnType.ATTACHMENT: "JSON" if self.use_json else "TEXT"
        }
        
        return type_mapping.get(column_type, "TEXT")
    
    def convert_value(self, value: Any, column: SmartsheetColumn) -> str:
        """Convert a value to MySQL-compatible format."""
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
        
        # Handle JSON types
        elif column_type in [ColumnType.CONTACT_LIST, ColumnType.MULTI_CONTACT_LIST, 
                           ColumnType.MULTI_PICKLIST, ColumnType.PREDECESSOR, ColumnType.ATTACHMENT]:
            if self.use_json:
                if isinstance(value, (dict, list)):
                    json_str = json.dumps(value, ensure_ascii=False)
                    return f"'{self.escape_string(json_str)}'"
                elif isinstance(value, str):
                    # Try to parse as JSON, otherwise treat as simple string
                    try:
                        parsed = json.loads(value)
                        json_str = json.dumps(parsed, ensure_ascii=False)
                        return f"'{self.escape_string(json_str)}'"
                    except (json.JSONDecodeError, ValueError):
                        # Treat as simple string value
                        json_str = json.dumps(value, ensure_ascii=False)
                        return f"'{self.escape_string(json_str)}'"
                else:
                    json_str = json.dumps(value, ensure_ascii=False, default=str)
                    return f"'{self.escape_string(json_str)}'"
            else:
                # Store as text
                if isinstance(value, (dict, list)):
                    text_value = json.dumps(value, ensure_ascii=False)
                    return f"'{self.escape_string(text_value)}'"
                else:
                    return f"'{self.escape_string(str(value))}'"
        
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
                return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
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
        
        # Handle duration (convert to TIME format)
        elif column_type == ColumnType.DURATION:
            if isinstance(value, str):
                # Try to convert duration string to TIME format
                try:
                    # Assuming format like "2 hours 30 minutes" or "2:30:00"
                    if ":" in value:
                        return f"'{self.escape_string(value)}'"
                    else:
                        # Convert text duration to time format
                        return f"'{self.escape_string(value)}'"
                except:
                    return "NULL"
            else:
                return f"'{self.escape_string(str(value))}'"
        
        # Handle numeric values
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        
        # Handle all other types as text
        else:
            return f"'{self.escape_string(str(value))}'"
    
    def escape_string(self, value: str) -> str:
        """Escape string for MySQL."""
        if not isinstance(value, str):
            value = str(value)
        
        # MySQL string escaping
        escaped = value.replace("\\", "\\\\")  # Escape backslashes first
        escaped = escaped.replace("'", "\\'")  # Escape single quotes
        escaped = escaped.replace("\n", "\\n")  # Escape newlines
        escaped = escaped.replace("\r", "\\r")  # Escape carriage returns
        escaped = escaped.replace("\t", "\\t")  # Escape tabs
        # Note: Don't escape double quotes for JSON content
        
        return escaped
    
    def _is_valid_date_string(self, value: str) -> bool:
        """Check if a string represents a valid date/datetime."""
        if not value or not isinstance(value, str):
            return False
        
        # Common invalid placeholders
        invalid_values = {'x', 'tbd', 'tba', 'n/a', 'na', '-', '', 'null', 'none'}
        if value.strip().lower() in invalid_values:
            return False
        
        from datetime import datetime
        
        # MySQL date formats
        date_formats = [
            '%Y-%m-%d',           # 2023-01-15
            '%Y-%m-%d %H:%M:%S',  # 2023-01-15 14:30:00
            '%Y/%m/%d',           # 2023/01/15
            '%m/%d/%Y',           # 01/15/2023
            '%m/%d/%y',           # 01/15/23
            '%d/%m/%Y',           # 15/01/2023
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
        """Generate CREATE TABLE SQL for MySQL."""
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        lines = [
            f"-- Create table for {schema.source_type}: {schema.name}",
            f"DROP TABLE IF EXISTS {full_table_name};",
            f"CREATE TABLE {full_table_name} ("
        ]
        
        column_definitions = []
        
        # Add metadata columns
        if self.include_metadata_columns:
            column_definitions.extend([
                f"    {self.quote_identifier('smartsheet_row_id')} BIGINT NOT NULL",
                f"    {self.quote_identifier('smartsheet_row_number')} INT",
                f"    {self.quote_identifier('created_at')} TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                f"    {self.quote_identifier('modified_at')} TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
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
        
        # Add table options
        lines.append(f") ENGINE={self.engine} DEFAULT CHARSET={self.charset} COLLATE={self.collation};")
        
        return "\n".join(lines)
    
    def generate_indexes_sql(self, schema: SmartsheetSchema, table_name: Optional[str] = None) -> str:
        """Generate CREATE INDEX statements for MySQL."""
        if not self.create_indexes:
            return ""
        
        table_name = table_name or self.get_table_name(schema)
        full_table_name = f"{self.schema_name}.{self.quote_identifier(table_name)}"
        
        lines = ["", "-- Indexes"]
        
        # Index on metadata columns
        if self.include_metadata_columns:
            lines.append(f"CREATE INDEX idx_{table_name}_modified_at ON {full_table_name} ({self.quote_identifier('modified_at')});")
            lines.append(f"CREATE INDEX idx_{table_name}_created_at ON {full_table_name} ({self.quote_identifier('created_at')});")
        
        # Index on primary column
        primary_column = schema.get_primary_column()
        if primary_column and not primary_column.hidden:
            col_name = self.sanitize_identifier(primary_column.get_effective_title())
            lines.append(f"CREATE INDEX idx_{table_name}_{col_name} ON {full_table_name} ({self.quote_identifier(col_name)});")
        
        # Indexes on JSON columns for common queries (MySQL 5.7+)
        if self.use_json:
            for column in schema.columns:
                if column.hidden:
                    continue
                    
                if column.type in [ColumnType.CONTACT_LIST, ColumnType.MULTI_CONTACT_LIST]:
                    col_name = self.sanitize_identifier(column.get_effective_title())
                    # MySQL JSON functional indexes (MySQL 8.0+)
                    lines.append(f"-- Note: JSON functional indexes require MySQL 8.0+")
                    lines.append(f"-- CREATE INDEX idx_{table_name}_{col_name}_email ON {full_table_name} ((CAST({self.quote_identifier(col_name)}->'$.email' AS CHAR(255))));")
        
        return "\n".join(lines)
    
    def generate_insert_sql_batch_from_rows(self, rows: List[SmartsheetRow], schema: SmartsheetSchema, 
                                          table_name: Optional[str] = None) -> str:
        """Generate INSERT statements for a batch of SmartsheetRow objects."""
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
        lines = [f"INSERT INTO {full_table_name} ({columns_str}) VALUES"]
        
        # Build value rows
        value_rows = []
        for row in rows:
            values = []
            
            # Add metadata values
            if self.include_metadata_columns:
                values.extend([
                    str(row.id),
                    str(row.row_number) if row.row_number else "NULL",
                    f"'{row.created_at.strftime('%Y-%m-%d %H:%M:%S')}'" if row.created_at else "NOW()",
                    f"'{row.modified_at.strftime('%Y-%m-%d %H:%M:%S')}'" if row.modified_at else "NOW()"
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
        lines = [f"INSERT INTO {full_table_name} ({columns_str}) VALUES"]
        
        # Build value rows
        value_rows = []
        for row_data in rows_data:
            values = []
            
            # Add metadata values
            if self.include_metadata_columns:
                values.extend([
                    str(row_data.get('smartsheet_row_id', 0)),
                    str(row_data.get('smartsheet_row_number', 0)),
                    f"'{row_data.get('created_at', 'NOW()')}'" if 'created_at' in row_data else "NOW()",
                    f"'{row_data.get('modified_at', 'NOW()')}'" if 'modified_at' in row_data else "NOW()"
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


def generate_mysql_script(data_file: Union[str, Path], schema_file: Union[str, Path], 
                         output_file: Union[str, Path], config: Optional[Dict[str, Any]] = None,
                         table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate a complete MySQL import script from Smartsheet data.
    
    Args:
        data_file: Path to JSON file containing row data
        schema_file: Path to JSON file containing schema metadata
        output_file: Path where SQL script will be written
        config: MySQL generator configuration
        table_name: Custom table name (optional)
    
    Returns:
        Dict with generation statistics
    """
    start_time = time.time()
    logger = get_logger(__name__)
    
    # Convert paths
    data_file = Path(data_file)
    schema_file = Path(schema_file)
    output_file = Path(output_file)
    
    logger.info(f"Generating MySQL script from {data_file} to {output_file}")
    
    # Load schema
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    
    schema = SmartsheetSchema.from_dict(schema_data)
    
    # Load data
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rows_data = data.get('rows', [])
    
    # Initialize generator
    generator = MySQLGenerator(config)
    
    # Generate SQL
    sql_parts = []
    
    # Header
    sql_parts.append("-- MySQL import script generated by ss2db")
    sql_parts.append(f"-- Generated at: {datetime.now().isoformat()}")
    sql_parts.append(f"-- Source: {schema.source_type} '{schema.name}' (ID: {schema.id})")
    sql_parts.append(f"-- Total rows: {len(rows_data)}")
    sql_parts.append("")
    
    # Create table
    sql_parts.append(generator.generate_create_table_sql(schema, table_name))
    
    # Create indexes
    if generator.create_indexes:
        sql_parts.append(generator.generate_indexes_sql(schema, table_name))
    
    # Insert data in batches
    insert_statements = 0
    batch_size = generator.batch_size
    
    if rows_data:
        sql_parts.append("")
        sql_parts.append("-- Data")
        
        for i in range(0, len(rows_data), batch_size):
            batch = rows_data[i:i + batch_size]
            insert_sql = generator.generate_insert_sql_batch_from_dict(batch, schema, table_name)
            if insert_sql:
                sql_parts.append(insert_sql)
                insert_statements += 1
    
    # Write to file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sql_content = "\n".join(sql_parts)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    # Calculate statistics
    elapsed_time = time.time() - start_time
    file_size = output_file.stat().st_size
    line_count = len(sql_content.splitlines())
    
    result = {
        'file_path': str(output_file),
        'file_size': file_size,
        'lines': line_count,
        'rows_processed': len(rows_data),
        'insert_statements': insert_statements,
        'elapsed_time': elapsed_time
    }
    
    logger.info(f"MySQL script generated successfully: {file_size} bytes, {line_count} lines, {elapsed_time:.2f}s")
    
    return result