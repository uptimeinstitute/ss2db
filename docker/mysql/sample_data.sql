-- Sample data for MySQL testing
-- This script creates sample tables and data that simulate Smartsheet exports

USE ss2db_test;

-- Create a sample table that represents a typical Smartsheet export
CREATE TABLE IF NOT EXISTS smartsheet_123456789 (
    smartsheet_row_id BIGINT PRIMARY KEY,
    task_name TEXT,
    assigned_to JSON,
    status VARCHAR(255),
    start_date DATE,
    end_date DATE,
    duration TIME,
    complete BOOLEAN,
    priority VARCHAR(255),
    comments TEXT,
    attachments JSON,
    multiple_contacts JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Insert sample data
INSERT INTO smartsheet_123456789 (
    smartsheet_row_id, task_name, assigned_to, status, 
    start_date, end_date, duration, complete, 
    priority, comments, attachments, multiple_contacts
) VALUES 
(
    1001, 
    'Setup Development Environment',
    JSON_OBJECT('email', 'john.doe@example.com', 'displayValue', 'John Doe'),
    'In Progress',
    '2024-01-15',
    '2024-01-20',
    '120:00:00',
    false,
    'High',
    'Need to configure all development tools',
    JSON_ARRAY(),
    JSON_ARRAY(
        JSON_OBJECT('email', 'john.doe@example.com', 'displayValue', 'John Doe'),
        JSON_OBJECT('email', 'jane.smith@example.com', 'displayValue', 'Jane Smith')
    )
),
(
    1002,
    'Database Design',
    JSON_OBJECT('email', 'jane.smith@example.com', 'displayValue', 'Jane Smith'),
    'Not Started',
    '2024-01-21',
    '2024-01-25',
    '96:00:00',
    false,
    'High',
    'Design the database schema for the application',
    JSON_ARRAY(
        JSON_OBJECT('name', 'schema.png', 'url', 'https://example.com/files/schema.png')
    ),
    JSON_ARRAY(
        JSON_OBJECT('email', 'jane.smith@example.com', 'displayValue', 'Jane Smith')
    )
),
(
    1003,
    'API Implementation',
    JSON_OBJECT('email', 'bob.wilson@example.com', 'displayValue', 'Bob Wilson'),
    'Completed',
    '2024-01-10',
    '2024-01-14',
    '96:00:00',
    true,
    'Medium',
    'REST API endpoints implemented and tested',
    JSON_ARRAY(),
    JSON_ARRAY(
        JSON_OBJECT('email', 'bob.wilson@example.com', 'displayValue', 'Bob Wilson'),
        JSON_OBJECT('email', 'alice.jones@example.com', 'displayValue', 'Alice Jones')
    )
),
(
    1004,
    'Frontend Development',
    JSON_OBJECT('email', 'alice.jones@example.com', 'displayValue', 'Alice Jones'),
    'In Progress',
    '2024-01-16',
    '2024-01-30',
    '336:00:00',
    false,
    'Medium',
    'Building the user interface components',
    JSON_ARRAY(
        JSON_OBJECT('name', 'mockup.pdf', 'url', 'https://example.com/files/mockup.pdf')
    ),
    JSON_ARRAY(
        JSON_OBJECT('email', 'alice.jones@example.com', 'displayValue', 'Alice Jones')
    )
),
(
    1005,
    'Testing and QA',
    JSON_OBJECT('email', 'charlie.brown@example.com', 'displayValue', 'Charlie Brown'),
    'Not Started',
    '2024-02-01',
    '2024-02-10',
    '216:00:00',
    false,
    'Low',
    'Comprehensive testing of all features',
    JSON_ARRAY(),
    JSON_ARRAY(
        JSON_OBJECT('email', 'charlie.brown@example.com', 'displayValue', 'Charlie Brown'),
        JSON_OBJECT('email', 'john.doe@example.com', 'displayValue', 'John Doe')
    )
);

-- Record this sample data in the metadata
INSERT INTO column_mappings (
    sheet_id, column_id, column_title, smartsheet_type, mysql_type, column_index
) VALUES 
(123456789, 1, 'Task Name', 'TEXT_NUMBER', 'TEXT', 1),
(123456789, 2, 'Assigned To', 'CONTACT_LIST', 'JSON', 2),
(123456789, 3, 'Status', 'PICKLIST', 'VARCHAR(255)', 3),
(123456789, 4, 'Start Date', 'DATE', 'DATE', 4),
(123456789, 5, 'End Date', 'DATE', 'DATE', 5),
(123456789, 6, 'Duration', 'DURATION', 'TIME', 6),
(123456789, 7, 'Complete', 'CHECKBOX', 'BOOLEAN', 7),
(123456789, 8, 'Priority', 'PICKLIST', 'VARCHAR(255)', 8),
(123456789, 9, 'Comments', 'TEXT_NUMBER', 'TEXT', 9),
(123456789, 10, 'Attachments', 'MULTI_CONTACT_LIST', 'JSON', 10),
(123456789, 11, 'Multiple Contacts', 'MULTI_CONTACT_LIST', 'JSON', 11);

-- Record the sample export
INSERT INTO export_logs (
    sheet_id, export_type, table_name, rows_exported, 
    completed_at, status, config_snapshot
) VALUES (
    123456789, 'sheet', 'smartsheet_123456789', 5,
    NOW(), 'completed', 
    JSON_OBJECT('database', JSON_OBJECT('type', 'mysql'), 'output', JSON_OBJECT('directory', './sample_exports'))
);

-- Create a second sample table for reports
CREATE TABLE IF NOT EXISTS smartsheet_report_987654321 (
    smartsheet_row_id BIGINT PRIMARY KEY,
    project TEXT,
    owner JSON,
    budget DECIMAL(10,2),
    spent DECIMAL(10,2),
    remaining DECIMAL(10,2),
    health VARCHAR(50),
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Insert report sample data
INSERT INTO smartsheet_report_987654321 (
    smartsheet_row_id, project, owner, budget, spent, 
    remaining, health, last_updated
) VALUES 
(
    2001, 'Website Redesign', 
    JSON_OBJECT('email', 'pm1@example.com', 'displayValue', 'Project Manager 1'),
    50000.00, 32000.00, 18000.00, 'Green', '2024-01-20 10:30:00'
),
(
    2002, 'Mobile App Development',
    JSON_OBJECT('email', 'pm2@example.com', 'displayValue', 'Project Manager 2'), 
    75000.00, 45000.00, 30000.00, 'Yellow', '2024-01-19 15:45:00'
),
(
    2003, 'Database Migration',
    JSON_OBJECT('email', 'pm3@example.com', 'displayValue', 'Project Manager 3'),
    25000.00, 28000.00, -3000.00, 'Red', '2024-01-18 09:15:00'
);

SELECT 'Sample data loaded successfully into MySQL' as message;
SELECT 'Tables created:' as info;
SELECT '  - smartsheet_123456789 (5 rows)' as table1;
SELECT '  - smartsheet_report_987654321 (3 rows)' as table2;