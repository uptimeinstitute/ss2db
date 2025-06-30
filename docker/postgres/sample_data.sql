-- Sample data for PostgreSQL testing
-- This script creates sample tables and data that simulate Smartsheet exports

\c ss2db_test;

-- Create a sample table that represents a typical Smartsheet export
CREATE TABLE IF NOT EXISTS public.smartsheet_123456789 (
    smartsheet_row_id BIGINT PRIMARY KEY,
    "Task Name" TEXT,
    "Assigned To" JSONB,
    "Status" VARCHAR(255),
    "Start Date" DATE,
    "End Date" DATE,
    "Duration" INTERVAL,
    "Complete" BOOLEAN,
    "Priority" VARCHAR(255),
    "Comments" TEXT,
    "Attachments" JSONB,
    "Multiple Contacts" JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    modified_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert sample data
INSERT INTO public.smartsheet_123456789 (
    smartsheet_row_id, "Task Name", "Assigned To", "Status", 
    "Start Date", "End Date", "Duration", "Complete", 
    "Priority", "Comments", "Attachments", "Multiple Contacts"
) VALUES 
(
    1001, 
    'Setup Development Environment',
    '{"email": "john.doe@example.com", "displayValue": "John Doe"}',
    'In Progress',
    '2024-01-15',
    '2024-01-20',
    '5 days',
    false,
    'High',
    'Need to configure all development tools',
    '[]',
    '[{"email": "john.doe@example.com", "displayValue": "John Doe"}, {"email": "jane.smith@example.com", "displayValue": "Jane Smith"}]'
),
(
    1002,
    'Database Design',
    '{"email": "jane.smith@example.com", "displayValue": "Jane Smith"}',
    'Not Started',
    '2024-01-21',
    '2024-01-25',
    '4 days',
    false,
    'High',
    'Design the database schema for the application',
    '[{"name": "schema.png", "url": "https://example.com/files/schema.png"}]',
    '[{"email": "jane.smith@example.com", "displayValue": "Jane Smith"}]'
),
(
    1003,
    'API Implementation',
    '{"email": "bob.wilson@example.com", "displayValue": "Bob Wilson"}',
    'Completed',
    '2024-01-10',
    '2024-01-14',
    '4 days',
    true,
    'Medium',
    'REST API endpoints implemented and tested',
    '[]',
    '[{"email": "bob.wilson@example.com", "displayValue": "Bob Wilson"}, {"email": "alice.jones@example.com", "displayValue": "Alice Jones"}]'
),
(
    1004,
    'Frontend Development',
    '{"email": "alice.jones@example.com", "displayValue": "Alice Jones"}',
    'In Progress',
    '2024-01-16',
    '2024-01-30',
    '14 days',
    false,
    'Medium',
    'Building the user interface components',
    '[{"name": "mockup.pdf", "url": "https://example.com/files/mockup.pdf"}]',
    '[{"email": "alice.jones@example.com", "displayValue": "Alice Jones"}]'
),
(
    1005,
    'Testing and QA',
    '{"email": "charlie.brown@example.com", "displayValue": "Charlie Brown"}',
    'Not Started',
    '2024-02-01',
    '2024-02-10',
    '9 days',
    false,
    'Low',
    'Comprehensive testing of all features',
    '[]',
    '[{"email": "charlie.brown@example.com", "displayValue": "Charlie Brown"}, {"email": "john.doe@example.com", "displayValue": "John Doe"}]'
);

-- Record this sample data in the metadata
INSERT INTO smartsheet.column_mappings (
    sheet_id, column_id, column_title, smartsheet_type, postgres_type, column_index
) VALUES 
(123456789, 1, 'Task Name', 'TEXT_NUMBER', 'TEXT', 1),
(123456789, 2, 'Assigned To', 'CONTACT_LIST', 'JSONB', 2),
(123456789, 3, 'Status', 'PICKLIST', 'VARCHAR(255)', 3),
(123456789, 4, 'Start Date', 'DATE', 'DATE', 4),
(123456789, 5, 'End Date', 'DATE', 'DATE', 5),
(123456789, 6, 'Duration', 'DURATION', 'INTERVAL', 6),
(123456789, 7, 'Complete', 'CHECKBOX', 'BOOLEAN', 7),
(123456789, 8, 'Priority', 'PICKLIST', 'VARCHAR(255)', 8),
(123456789, 9, 'Comments', 'TEXT_NUMBER', 'TEXT', 9),
(123456789, 10, 'Attachments', 'MULTI_CONTACT_LIST', 'JSONB', 10),
(123456789, 11, 'Multiple Contacts', 'MULTI_CONTACT_LIST', 'JSONB', 11);

-- Record the sample export
INSERT INTO smartsheet.export_logs (
    sheet_id, export_type, table_name, rows_exported, 
    completed_at, status, config_snapshot
) VALUES (
    123456789, 'sheet', 'smartsheet_123456789', 5,
    NOW(), 'completed', 
    '{"database": {"type": "postgresql"}, "output": {"directory": "./sample_exports"}}'
);

-- Create a second sample table for reports
CREATE TABLE IF NOT EXISTS public.smartsheet_report_987654321 (
    smartsheet_row_id BIGINT PRIMARY KEY,
    "Project" TEXT,
    "Owner" JSONB,
    "Budget" DECIMAL(10,2),
    "Spent" DECIMAL(10,2),
    "Remaining" DECIMAL(10,2),
    "Health" VARCHAR(50),
    "Last Updated" TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert report sample data
INSERT INTO public.smartsheet_report_987654321 (
    smartsheet_row_id, "Project", "Owner", "Budget", "Spent", 
    "Remaining", "Health", "Last Updated"
) VALUES 
(
    2001, 'Website Redesign', 
    '{"email": "pm1@example.com", "displayValue": "Project Manager 1"}',
    50000.00, 32000.00, 18000.00, 'Green', '2024-01-20 10:30:00+00'
),
(
    2002, 'Mobile App Development',
    '{"email": "pm2@example.com", "displayValue": "Project Manager 2"}', 
    75000.00, 45000.00, 30000.00, 'Yellow', '2024-01-19 15:45:00+00'
),
(
    2003, 'Database Migration',
    '{"email": "pm3@example.com", "displayValue": "Project Manager 3"}',
    25000.00, 28000.00, -3000.00, 'Red', '2024-01-18 09:15:00+00'
);

-- Grant permissions on sample tables
GRANT ALL PRIVILEGES ON public.smartsheet_123456789 TO ss2db_user;
GRANT ALL PRIVILEGES ON public.smartsheet_report_987654321 TO ss2db_user;

\echo 'Sample data loaded successfully into PostgreSQL'
\echo 'Tables created:'
\echo '  - public.smartsheet_123456789 (5 rows)'
\echo '  - public.smartsheet_report_987654321 (3 rows)'