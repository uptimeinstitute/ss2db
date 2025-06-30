-- PostgreSQL initialization script for ss2db testing
-- This script sets up the initial database structure and permissions

-- Ensure the database exists (should already be created by Docker)
SELECT 'CREATE DATABASE ss2db_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ss2db_test');

-- Connect to the test database
\c ss2db_test;

-- Create extension for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a schema for smartsheet data
CREATE SCHEMA IF NOT EXISTS smartsheet;

-- Grant permissions to the ss2db_user
GRANT ALL PRIVILEGES ON SCHEMA smartsheet TO ss2db_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO ss2db_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA smartsheet GRANT ALL ON TABLES TO ss2db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA smartsheet GRANT ALL ON SEQUENCES TO ss2db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA smartsheet GRANT ALL ON FUNCTIONS TO ss2db_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ss2db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ss2db_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO ss2db_user;

-- Create metadata tables for tracking Smartsheet exports
CREATE TABLE IF NOT EXISTS smartsheet.export_logs (
    id SERIAL PRIMARY KEY,
    sheet_id BIGINT,
    report_id BIGINT,
    export_type VARCHAR(10) CHECK (export_type IN ('sheet', 'report')),
    table_name VARCHAR(255) NOT NULL,
    rows_exported INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    error_message TEXT,
    config_snapshot JSONB
);

CREATE TABLE IF NOT EXISTS smartsheet.column_mappings (
    id SERIAL PRIMARY KEY,
    sheet_id BIGINT,
    report_id BIGINT,
    column_id BIGINT NOT NULL,
    column_title VARCHAR(255) NOT NULL,
    smartsheet_type VARCHAR(50) NOT NULL,
    postgres_type VARCHAR(50) NOT NULL,
    column_index INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_sheet_column UNIQUE (sheet_id, column_id),
    CONSTRAINT unique_report_column UNIQUE (report_id, column_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_export_logs_sheet_id ON smartsheet.export_logs (sheet_id);
CREATE INDEX IF NOT EXISTS idx_export_logs_report_id ON smartsheet.export_logs (report_id);
CREATE INDEX IF NOT EXISTS idx_export_logs_status ON smartsheet.export_logs (status);
CREATE INDEX IF NOT EXISTS idx_export_logs_started_at ON smartsheet.export_logs (started_at);

CREATE INDEX IF NOT EXISTS idx_column_mappings_sheet_id ON smartsheet.column_mappings (sheet_id);
CREATE INDEX IF NOT EXISTS idx_column_mappings_report_id ON smartsheet.column_mappings (report_id);

-- Grant permissions on the new tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA smartsheet TO ss2db_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA smartsheet TO ss2db_user;

-- Create a test table to verify JSONB functionality
CREATE TABLE IF NOT EXISTS smartsheet.test_jsonb (
    id SERIAL PRIMARY KEY,
    contact_data JSONB,
    multi_select_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON smartsheet.test_jsonb TO ss2db_user;

-- Log the initialization
INSERT INTO smartsheet.export_logs (
    sheet_id, export_type, table_name, rows_exported, 
    completed_at, status, error_message
) VALUES (
    0, 'sheet', 'initialization', 0, 
    NOW(), 'completed', 'PostgreSQL database initialized successfully'
);

-- Display confirmation
\echo 'PostgreSQL database initialized successfully for ss2db testing'
\echo 'Database: ss2db_test'
\echo 'User: ss2db_user'
\echo 'Schema: smartsheet (for metadata), public (for data tables)'