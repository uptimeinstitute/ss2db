-- MySQL initialization script for ss2db testing
-- This script sets up the initial database structure and permissions

-- Ensure we're using the correct database
USE ss2db_test;

-- Set proper character set and collation
ALTER DATABASE ss2db_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create metadata tables for tracking Smartsheet exports
CREATE TABLE IF NOT EXISTS export_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sheet_id BIGINT,
    report_id BIGINT,
    export_type ENUM('sheet', 'report'),
    table_name VARCHAR(255) NOT NULL,
    rows_exported INT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    error_message TEXT,
    config_snapshot JSON,
    INDEX idx_sheet_id (sheet_id),
    INDEX idx_report_id (report_id),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS column_mappings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sheet_id BIGINT,
    report_id BIGINT,
    column_id BIGINT NOT NULL,
    column_title VARCHAR(255) NOT NULL,
    smartsheet_type VARCHAR(50) NOT NULL,
    mysql_type VARCHAR(50) NOT NULL,
    column_index INT NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_sheet_column (sheet_id, column_id),
    UNIQUE KEY unique_report_column (report_id, column_id),
    INDEX idx_sheet_id (sheet_id),
    INDEX idx_report_id (report_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a test table to verify JSON functionality
CREATE TABLE IF NOT EXISTS test_json (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contact_data JSON,
    multi_select_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Grant all privileges to the ss2db_user on the test database
GRANT ALL PRIVILEGES ON ss2db_test.* TO 'ss2db_user'@'%';
FLUSH PRIVILEGES;

-- Log the initialization
INSERT INTO export_logs (
    sheet_id, export_type, table_name, rows_exported, 
    completed_at, status, error_message
) VALUES (
    0, 'sheet', 'initialization', 0, 
    NOW(), 'completed', 'MySQL database initialized successfully'
);

-- Display confirmation
SELECT 'MySQL database initialized successfully for ss2db testing' as message;
SELECT 'Database: ss2db_test' as database_info;
SELECT 'User: ss2db_user' as user_info;
SELECT 'Tables: export_logs, column_mappings, test_json' as tables_info;