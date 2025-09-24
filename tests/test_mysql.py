"""Tests for MySQL SQL generation."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from ss2db.database.mysql import MySQLGenerator, generate_mysql_script
from ss2db.smartsheet.models import (
    SmartsheetSchema, SmartsheetColumn, SmartsheetRow, SmartsheetCell,
    ColumnType
)


class TestMySQLGenerator:
    """Test MySQL SQL generator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = MySQLGenerator({
            'schema_name': 'test_schema',
            'table_prefix': 'test_',
            'create_indexes': True,
            'include_metadata_columns': True,
            'use_json': True,
            'engine': 'InnoDB',
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'batch_size': 100
        })
    
    def test_sanitize_identifier(self):
        """Test identifier sanitization."""
        test_cases = [
            ('Normal Column', 'normal_column'),
            ('Column With Spaces', 'column_with_spaces'),
            ('Column-With-Dashes', 'column_with_dashes'),
            ('Column/With/Slashes', 'column_with_slashes'),
            ('123NumericStart', 'col_123numericstart'),
            ('', 'unnamed_column'),
            ('Special!@#$%Characters', 'special_characters'),
            ('Multiple___Underscores', 'multiple_underscores'),
            ('UPPERCASE', 'uppercase'),
            ('select', 'col_select'),  # MySQL reserved word
            ('table', 'col_table'),   # MySQL reserved word
        ]
        
        for input_name, expected in test_cases:
            result = self.generator.sanitize_identifier(input_name)
            assert result == expected
    
    def test_quote_identifier(self):
        """Test identifier quoting."""
        self.generator.quote_identifiers = True
        assert self.generator.quote_identifier('test') == '`test`'
        
        self.generator.quote_identifiers = False
        assert self.generator.quote_identifier('test') == 'test'
    
    def test_get_table_name(self):
        """Test table name generation."""
        schema = SmartsheetSchema(
            id=123456789,
            name='Test Schema',
            columns=[],
            source_type='report'
        )
        
        # Test with custom name
        result = self.generator.get_table_name(schema, 'custom_table')
        assert result == 'custom_table'
        
        # Test with auto-generated name
        result = self.generator.get_table_name(schema)
        assert result == 'test_report_123456789'
    
    def test_convert_column_type(self):
        """Test column type conversion."""
        test_cases = [
            (ColumnType.TEXT_NUMBER, "TEXT"),
            (ColumnType.CHECKBOX, "BOOLEAN"),
            (ColumnType.CONTACT_LIST, "JSON"),
            (ColumnType.DATE, "DATE"),
            (ColumnType.DATETIME, "DATETIME"),
            (ColumnType.ABSTRACT_DATETIME, "TIMESTAMP"),
            (ColumnType.DURATION, "TIME"),
            (ColumnType.MULTI_CONTACT_LIST, "JSON"),
            (ColumnType.PICKLIST, "VARCHAR(255)"),
            (ColumnType.MULTI_PICKLIST, "JSON"),
            (ColumnType.PREDECESSOR, "JSON"),
            (ColumnType.SYMBOL, "VARCHAR(50)"),
            (ColumnType.ATTACHMENT, "JSON")
        ]
        
        for column_type, expected_sql_type in test_cases:
            column = SmartsheetColumn(
                id=1, title="test", type=column_type, index=0
            )
            result = self.generator.convert_column_type(column)
            assert result == expected_sql_type

    def test_create_table_with_duplicate_column_names(self):
        """Test CREATE TABLE statement generation with duplicate column names."""
        columns = [
            SmartsheetColumn(id=111, title='forecasted', type=ColumnType.TEXT_NUMBER, index=0, unique_title='forecasted_1'),
            SmartsheetColumn(id=222, title='status', type=ColumnType.PICKLIST, index=1),
            SmartsheetColumn(id=333, title='forecasted', type=ColumnType.TEXT_NUMBER, index=2, unique_title='forecasted_2')
        ]

        schema = SmartsheetSchema(
            id=123,
            name='Test Schema',
            columns=columns,
            source_type='sheet'
        )

        sql = self.generator.generate_create_table_sql(schema, 'test_table')

        # Should use unique column names
        assert '`forecasted_1` TEXT' in sql
        assert '`forecasted_2` TEXT' in sql
        assert '`status` VARCHAR(255)' in sql

        # Should not contain the original duplicate column name
        assert '`forecasted` TEXT' not in sql

    def test_insert_sql_with_duplicate_column_names(self):
        """Test INSERT statement generation with duplicate column names."""
        columns = [
            SmartsheetColumn(id=111, title='forecasted', type=ColumnType.TEXT_NUMBER, index=0, unique_title='forecasted_1'),
            SmartsheetColumn(id=222, title='forecasted', type=ColumnType.TEXT_NUMBER, index=1, unique_title='forecasted_2')
        ]

        schema = SmartsheetSchema(
            id=123,
            name='Test Schema',
            columns=columns,
            source_type='sheet'
        )

        # Create row data using the effective column names
        rows_data = [
            {
                'smartsheet_row_id': 123,
                'smartsheet_row_number': 1,
                'forecasted_1': 'Value 1',
                'forecasted_2': 'Value 2'
            }
        ]

        sql = self.generator.generate_insert_sql_batch_from_dict(rows_data, schema, 'test_table')

        # Should reference unique column names
        assert '`forecasted_1`' in sql
        assert '`forecasted_2`' in sql
        assert "'Value 1'" in sql
        assert "'Value 2'" in sql

    def test_indexes_with_duplicate_column_names(self):
        """Test index generation with duplicate column names."""
        columns = [
            SmartsheetColumn(id=111, title='forecasted', type=ColumnType.TEXT_NUMBER, index=0,
                           unique_title='forecasted_1', primary=True),
            SmartsheetColumn(id=222, title='forecasted', type=ColumnType.TEXT_NUMBER, index=1,
                           unique_title='forecasted_2')
        ]

        schema = SmartsheetSchema(
            id=123,
            name='Test Schema',
            columns=columns,
            source_type='sheet'
        )

        sql = self.generator.generate_indexes_sql(schema, 'test_table')

        # Should use unique column names in index creation
        assert 'idx_test_table_forecasted_1' in sql
    
    def test_convert_column_type_without_json(self):
        """Test column type conversion without JSON support."""
        generator = MySQLGenerator({'use_json': False})
        
        column = SmartsheetColumn(
            id=1, title="contacts", type=ColumnType.CONTACT_LIST, index=0
        )
        result = generator.convert_column_type(column)
        assert result == "TEXT"
    
    def test_convert_value_boolean(self):
        """Test boolean value conversion."""
        column = SmartsheetColumn(
            id=1, title="checkbox", type=ColumnType.CHECKBOX, index=0
        )
        
        assert self.generator.convert_value(True, column) == "TRUE"
        assert self.generator.convert_value(False, column) == "FALSE"
        assert self.generator.convert_value(None, column) == "NULL"
        assert self.generator.convert_value("true", column) == "TRUE"
        assert self.generator.convert_value("false", column) == "FALSE"
        assert self.generator.convert_value("1", column) == "TRUE"
        assert self.generator.convert_value("0", column) == "FALSE"
    
    def test_convert_value_json(self):
        """Test JSON value conversion."""
        column = SmartsheetColumn(
            id=1, title="contacts", type=ColumnType.CONTACT_LIST, index=0
        )
        
        # Test dict value
        value = {"email": "test@example.com", "name": "Test User"}
        result = self.generator.convert_value(value, column)
        # JSON content should not have escaped double quotes
        assert result == "'{\"email\": \"test@example.com\", \"name\": \"Test User\"}'"
        
        # Test list value
        value = [{"email": "user1@example.com"}, {"email": "user2@example.com"}]
        result = self.generator.convert_value(value, column)
        assert "user1@example.com" in result
        assert "[" in result and "]" in result
        
        # Test None value
        assert self.generator.convert_value(None, column) == "NULL"
    
    def test_convert_value_json_disabled(self):
        """Test JSON value conversion when JSON is disabled."""
        generator = MySQLGenerator({'use_json': False})
        column = SmartsheetColumn(
            id=1, title="contacts", type=ColumnType.CONTACT_LIST, index=0
        )
        
        value = {"email": "test@example.com", "name": "Test User"}
        result = generator.convert_value(value, column)
        # Should store as escaped text
        assert result.startswith("'")
        assert result.endswith("'")
        assert "test@example.com" in result
    
    def test_convert_value_date_valid(self):
        """Test valid date value conversion."""
        column = SmartsheetColumn(
            id=1, title="date", type=ColumnType.DATE, index=0
        )
        
        # Valid date strings
        assert self.generator.convert_value("2023-01-15", column) == "'2023-01-15'"
        assert self.generator.convert_value("2023/01/15", column) == "'2023/01/15'"
        assert self.generator.convert_value("01/15/2023", column) == "'01/15/2023'"
        
        # Valid datetime object
        dt = datetime(2023, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = self.generator.convert_value(dt, column)
        assert result == "'2023-01-15 14:30:00'"
    
    def test_convert_value_date_invalid(self):
        """Test invalid date value conversion."""
        column = SmartsheetColumn(
            id=1, title="date", type=ColumnType.DATE, index=0
        )
        
        # Invalid date values should convert to NULL
        invalid_values = ["X", "TBD", "TBA", "N/A", "-", "", "Not a date", "123abc"]
        
        for invalid_value in invalid_values:
            result = self.generator.convert_value(invalid_value, column)
            assert result == "NULL"
    
    def test_convert_value_duration(self):
        """Test duration value conversion."""
        column = SmartsheetColumn(
            id=1, title="duration", type=ColumnType.DURATION, index=0
        )
        
        assert self.generator.convert_value("02:30:00", column) == "'02:30:00'"
        assert self.generator.convert_value("1 hour", column) == "'1 hour'"
        assert self.generator.convert_value(None, column) == "NULL"
    
    def test_convert_value_text(self):
        """Test text value conversion."""
        column = SmartsheetColumn(
            id=1, title="text", type=ColumnType.TEXT_NUMBER, index=0
        )
        
        assert self.generator.convert_value("Simple text", column) == "'Simple text'"
        assert self.generator.convert_value("Text with 'quotes'", column) == "'Text with \\'quotes\\''"
        assert self.generator.convert_value(123, column) == "123"
        assert self.generator.convert_value(123.45, column) == "123.45"
        assert self.generator.convert_value(None, column) == "NULL"
    
    def test_escape_string(self):
        """Test string escaping."""
        test_cases = [
            ("simple", "simple"),
            ("text with 'quotes'", "text with \\'quotes\\'"),
            ("text with \"double quotes\"", "text with \"double quotes\""),  # Double quotes not escaped
            ("text with \\ backslash", "text with \\\\ backslash"),
            ("text with 'quotes' and \\ backslash", "text with \\'quotes\\' and \\\\ backslash"),
            ("line\nbreak", "line\\nbreak"),
            ("tab\there", "tab\\there"),
        ]
        
        for input_str, expected in test_cases:
            result = self.generator.escape_string(input_str)
            assert result == expected
    
    def test_is_valid_date_string(self):
        """Test date string validation."""
        # Valid dates
        valid_dates = [
            "2023-01-15",
            "2023-01-15 14:30:00",
            "2023/01/15",
            "01/15/2023",
            "15/01/2023"
        ]
        
        for valid_date in valid_dates:
            assert self.generator._is_valid_date_string(valid_date) is True
        
        # Invalid dates
        invalid_dates = [
            "X", "TBD", "TBA", "N/A", "NA", "-", "",
            "Not a date", "123abc", "2023-13-45", "99/99/9999"
        ]
        
        for invalid_date in invalid_dates:
            assert self.generator._is_valid_date_string(invalid_date) is False
    
    def test_generate_create_table_sql(self):
        """Test CREATE TABLE SQL generation."""
        columns = [
            SmartsheetColumn(id=1, title='Name', type=ColumnType.TEXT_NUMBER, index=0, primary=True),
            SmartsheetColumn(id=2, title='Email', type=ColumnType.CONTACT_LIST, index=1),
            SmartsheetColumn(id=3, title='Active', type=ColumnType.CHECKBOX, index=2),
            SmartsheetColumn(id=4, title='Created Date', type=ColumnType.DATE, index=3)
        ]
        
        schema = SmartsheetSchema(
            id=123456789,
            name='Test Table',
            columns=columns,
            total_row_count=100,
            source_type='sheet'
        )
        
        sql = self.generator.generate_create_table_sql(schema, 'test_table')
        
        # Check basic structure
        assert 'DROP TABLE IF EXISTS test_schema.`test_table`' in sql
        assert 'CREATE TABLE test_schema.`test_table`' in sql
        
        # Check metadata columns
        assert '`smartsheet_row_id` BIGINT NOT NULL' in sql
        assert '`smartsheet_row_number` INT' in sql
        assert '`created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP' in sql
        assert '`modified_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP' in sql
        
        # Check data columns (no NOT NULL constraints)
        assert '`name` TEXT' in sql
        assert '`email` JSON' in sql
        assert '`active` BOOLEAN' in sql
        assert '`created_date` DATE' in sql
        
        # Check primary key
        assert 'PRIMARY KEY (`smartsheet_row_id`)' in sql
        
        # Check table options
        assert 'ENGINE=InnoDB' in sql
        assert 'DEFAULT CHARSET=utf8mb4' in sql
        assert 'COLLATE=utf8mb4_unicode_ci' in sql
        
        # Ensure no NOT NULL on data columns
        assert '`name` TEXT NOT NULL' not in sql
        assert '`email` JSON NOT NULL' not in sql
    
    def test_generate_indexes_sql(self):
        """Test index generation."""
        columns = [
            SmartsheetColumn(id=1, title='Name', type=ColumnType.TEXT_NUMBER, index=0, primary=True),
            SmartsheetColumn(id=2, title='Contacts', type=ColumnType.MULTI_CONTACT_LIST, index=1),
            SmartsheetColumn(id=3, title='Status', type=ColumnType.PICKLIST, index=2)
        ]
        
        schema = SmartsheetSchema(
            id=123,
            name='Test',
            columns=columns,
            source_type='sheet'
        )
        
        sql = self.generator.generate_indexes_sql(schema, 'test_table')
        
        # Check metadata column indexes
        assert 'idx_test_table_modified_at' in sql
        assert 'idx_test_table_created_at' in sql
        
        # Check primary column index
        assert 'idx_test_table_name' in sql
        
        # Check JSON functional index comment
        assert 'JSON functional indexes require MySQL 8.0+' in sql
    
    def test_generate_indexes_sql_disabled(self):
        """Test index generation when disabled."""
        generator = MySQLGenerator({'create_indexes': False})
        schema = SmartsheetSchema(
            id=123,
            name='Test',
            columns=[],
            source_type='test'
        )
        
        sql = generator.generate_indexes_sql(schema, 'test_table')
        assert sql == ""
    
    def test_generate_insert_sql_batch_from_dict(self):
        """Test INSERT SQL generation from dictionary data."""
        columns = [
            SmartsheetColumn(id=1, title='Name', type=ColumnType.TEXT_NUMBER, index=0),
            SmartsheetColumn(id=2, title='Active', type=ColumnType.CHECKBOX, index=1),
            SmartsheetColumn(id=3, title='Date', type=ColumnType.DATE, index=2)
        ]
        
        schema = SmartsheetSchema(
            id=123,
            name='Test',
            columns=columns,
            source_type='test'
        )
        
        rows_data = [
            {
                'smartsheet_row_id': 1001,
                'smartsheet_row_number': 1,
                'created_at': '2023-01-01 12:00:00',
                'modified_at': '2023-01-01 12:00:00',
                'Name': 'John Doe',
                'Active': True,
                'Date': '2023-01-15'
            },
            {
                'smartsheet_row_id': 1002,
                'smartsheet_row_number': 2,
                'created_at': '2023-01-02 12:00:00',
                'modified_at': '2023-01-02 12:00:00',
                'Name': 'Jane Smith',
                'Active': False,
                'Date': 'X'  # Invalid date
            }
        ]
        
        sql = self.generator.generate_insert_sql_batch_from_dict(rows_data, schema, 'test_table')
        
        # Check structure
        assert 'INSERT INTO test_schema.`test_table`' in sql
        assert 'VALUES' in sql
        
        # Check first row values
        assert '1001' in sql
        assert "'John Doe'" in sql
        assert 'TRUE' in sql
        assert "'2023-01-15'" in sql
        
        # Check second row values
        assert '1002' in sql
        assert "'Jane Smith'" in sql
        assert 'FALSE' in sql
        assert 'NULL' in sql  # Invalid date should become NULL
    
    def test_generate_insert_sql_batch_empty(self):
        """Test INSERT SQL generation with empty data."""
        schema = SmartsheetSchema(
            id=123,
            name='Test',
            columns=[],
            source_type='test'
        )
        
        sql = self.generator.generate_insert_sql_batch_from_dict([], schema, 'test_table')
        assert sql == ""


class TestGenerateMySQLScript:
    """Test the main generate_mysql_script function."""
    
    def test_generate_complete_script(self):
        """Test generating a complete MySQL script."""
        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test schema file
            schema_file = temp_path / 'test_schema.json'
            schema_data = {
                'id': 123456789,
                'name': 'Test Schema',
                'source_type': 'test',
                'total_row_count': 2,
                'created_at': '2023-01-01T12:00:00+00:00',
                'modified_at': '2023-01-01T12:00:00+00:00',
                'columns': [
                    {
                        'id': 1,
                        'title': 'Name',
                        'type': 'TEXT_NUMBER',
                        'index': 0,
                        'primary': False,
                        'hidden': False
                    },
                    {
                        'id': 2,
                        'title': 'Date',
                        'type': 'DATE',
                        'index': 1,
                        'primary': False,
                        'hidden': False
                    }
                ]
            }
            
            import json
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f)
            
            # Create test data file
            data_file = temp_path / 'test_data.json'
            data_data = {
                'metadata': schema_data,
                'rows': [
                    {
                        'smartsheet_row_id': 1001,
                        'smartsheet_row_number': 1,
                        'created_at': '2023-01-01 12:00:00',
                        'modified_at': '2023-01-01 12:00:00',
                        'Name': 'Test User',
                        'Date': '2023-01-15'
                    },
                    {
                        'smartsheet_row_id': 1002,
                        'smartsheet_row_number': 2,
                        'created_at': '2023-01-02 12:00:00',
                        'modified_at': '2023-01-02 12:00:00',
                        'Name': 'Another User',
                        'Date': 'X'  # Invalid date
                    }
                ]
            }
            
            with open(data_file, 'w') as f:
                json.dump(data_data, f)
            
            # Generate SQL
            output_file = temp_path / 'output.sql'
            config = {
                'schema_name': 'test_schema',
                'table_prefix': 'test_',
                'create_indexes': True,
                'include_metadata_columns': True,
                'use_json': True,
                'engine': 'InnoDB',
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'batch_size': 1000
            }
            
            result = generate_mysql_script(
                data_file=data_file,
                schema_file=schema_file,
                output_file=output_file,
                config=config,
                table_name='custom_table'
            )
            
            # Check result
            assert result['file_path'] == str(output_file)
            assert result['file_size'] > 0
            assert result['lines'] > 0
            assert result['insert_statements'] == 1
            assert result['elapsed_time'] >= 0
            
            # Check generated SQL file
            assert output_file.exists()
            sql_content = output_file.read_text()
            
            # Check structure
            assert '-- MySQL import script generated by ss2db' in sql_content
            assert 'DROP TABLE IF EXISTS' in sql_content
            assert 'CREATE TABLE' in sql_content
            assert 'CREATE INDEX' in sql_content
            assert 'INSERT INTO' in sql_content
            assert 'ENGINE=InnoDB' in sql_content
            assert 'DEFAULT CHARSET=utf8mb4' in sql_content
            
            # Check data
            assert "'Test User'" in sql_content
            assert "'Another User'" in sql_content
            assert "'2023-01-15'" in sql_content
            assert 'NULL' in sql_content  # Invalid date converted to NULL
    
    def test_generate_script_with_errors(self):
        """Test error handling in script generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test with non-existent files
            data_file = temp_path / 'nonexistent_data.json'
            schema_file = temp_path / 'nonexistent_schema.json'
            output_file = temp_path / 'output.sql'
            
            with pytest.raises(FileNotFoundError):
                generate_mysql_script(
                    data_file=data_file,
                    schema_file=schema_file,
                    output_file=output_file
                )
    
    def test_generator_error_handling(self):
        """Test MySQL generator error handling."""
        generator = MySQLGenerator({})
        
        # Test handling of unsupported column type
        column = SmartsheetColumn(
            id=1, title="test", type="UNKNOWN_TYPE", index=0
        )
        mysql_type = generator.convert_column_type(column)
        assert mysql_type == "TEXT"  # Should default to TEXT
        
        # Test handling of non-serializable value for JSON
        column = SmartsheetColumn(
            id=1, title="json", type=ColumnType.CONTACT_LIST, index=0
        )
        
        class NonSerializable:
            pass
        
        result = generator.convert_value(NonSerializable(), column)
        # Should convert to JSON string representation since json.dumps uses default=str
        assert "'" in result
    
    def test_generate_script_minimal_config(self):
        """Test script generation with minimal configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test schema file
            schema_file = temp_path / 'test_schema.json'
            schema_data = {
                'id': 123,
                'name': 'Test Schema',
                'source_type': 'test',
                'total_row_count': 1,
                'created_at': '2023-01-01T12:00:00+00:00',
                'modified_at': '2023-01-01T12:00:00+00:00',
                'columns': [
                    {
                        'id': 1,
                        'title': 'Name',
                        'type': 'TEXT_NUMBER',
                        'index': 0,
                        'primary': False,
                        'hidden': False
                    }
                ]
            }
            
            import json
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f)
            
            # Create test data file
            data_file = temp_path / 'test_data.json'
            data_data = {
                'metadata': schema_data,
                'rows': [
                    {
                        'smartsheet_row_id': 1001,
                        'smartsheet_row_number': 1,
                        'created_at': '2023-01-01 12:00:00',
                        'modified_at': '2023-01-01 12:00:00',
                        'Name': 'Test User'
                    }
                ]
            }
            
            with open(data_file, 'w') as f:
                json.dump(data_data, f)
            
            # Test with minimal config (no schema, no indexes, no JSON)
            output_file = temp_path / 'minimal.sql'
            config = {
                'schema_name': 'minimal_db',
                'create_indexes': False,
                'include_metadata_columns': False,
                'use_json': False,
                'quote_identifiers': False,
                'engine': 'MyISAM',
                'charset': 'latin1',
                'batch_size': 1
            }
            
            result = generate_mysql_script(
                data_file=data_file,
                schema_file=schema_file,
                output_file=output_file,
                config=config
            )
            
            # Check result
            assert result['file_path'] == str(output_file)
            assert result['file_size'] > 0
            assert result['insert_statements'] == 1
            
            # Check generated SQL file
            assert output_file.exists()
            sql_content = output_file.read_text()
            
            # Should have custom settings
            assert 'DROP TABLE IF EXISTS minimal_db.test_123' in sql_content
            assert 'CREATE TABLE minimal_db.test_123' in sql_content
            assert 'ENGINE=MyISAM' in sql_content
            assert 'DEFAULT CHARSET=latin1' in sql_content
            
            # Should not have indexes
            assert 'CREATE INDEX' not in sql_content
            
            # Should not have metadata columns
            assert 'smartsheet_row_id' not in sql_content