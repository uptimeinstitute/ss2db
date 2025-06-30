"""Configuration management for ss2db."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class SmartsheetConfig(BaseModel):
    """Smartsheet API configuration."""
    
    api_base_url: str = "https://api.smartsheet.com/2.0"
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    rate_limit_buffer: int = 5


class OutputConfig(BaseModel):
    """Output file configuration."""
    
    directory: str = "./exports"
    file_prefix: str = "smartsheet"
    backup_existing: bool = True
    compression: bool = False
    timestamp_format: str = "%Y%m%d_%H%M%S"


class PostgreSQLConfig(BaseModel):
    """PostgreSQL-specific configuration."""
    
    schema_name: str = "public"
    table_prefix: str = "smartsheet_"
    create_indexes: bool = True
    include_metadata_columns: bool = True
    batch_size: int = 1000
    quote_identifiers: bool = True
    use_jsonb: bool = True


class MySQLConfig(BaseModel):
    """MySQL-specific configuration."""
    
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


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    type: str = "postgresql"
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)
    
    @validator("type")
    def validate_type(cls, v):
        if v not in ["postgresql", "mysql"]:
            raise ValueError("database type must be 'postgresql' or 'mysql'")
        return v


class ProcessingConfig(BaseModel):
    """Data processing configuration."""
    
    validate_data: bool = True
    skip_empty_rows: bool = True
    handle_duplicates: str = "error"
    date_format: str = "iso"
    timezone: str = "UTC"
    max_field_length: int = 65535
    null_values: list[str] = ["", "NULL", "null", "None"]
    
    @validator("handle_duplicates")
    def validate_handle_duplicates(cls, v):
        if v not in ["error", "skip", "overwrite"]:
            raise ValueError("handle_duplicates must be 'error', 'skip', or 'overwrite'")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = "INFO"
    format: str = "detailed"
    file_rotation: bool = True
    max_file_size: str = "10MB"
    backup_count: int = 5
    
    @validator("level")
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}")
        return v.upper()


class AdvancedConfig(BaseModel):
    """Advanced configuration options."""
    
    memory_limit_mb: int = 1024
    chunk_size: int = 10000
    parallel_processing: bool = False
    cache_responses: bool = True
    cache_ttl_hours: int = 24


class Config(BaseModel):
    """Main configuration class."""
    
    smartsheet: SmartsheetConfig = Field(default_factory=SmartsheetConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


class ConfigManager:
    """Manages configuration loading and environment variables."""
    
    def __init__(self, config_path: Optional[str] = None, env_file: Optional[str] = None):
        self.config_path = Path(config_path or "config.yaml")
        self.env_file = Path(env_file or ".env")
        self._config: Optional[Config] = None
        self._env_vars: Dict[str, str] = {}
        
    def load(self) -> Config:
        """Load configuration from files and environment."""
        # Load environment variables
        self._load_environment()
        
        # Load YAML config
        config_data = self._load_yaml_config()
        
        # Create config object
        self._config = Config(**config_data)
        
        return self._config
    
    def _load_environment(self) -> None:
        """Load environment variables from .env file and system."""
        # Load from .env file if it exists
        if self.env_file.exists():
            load_dotenv(self.env_file)
        
        # Store relevant environment variables
        env_keys = [
            "SMARTSHEET_API_TOKEN", "SS_API_TOKEN",
            "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB",
            "POSTGRES_USER", "POSTGRES_PASSWORD", 
            "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DB",
            "MYSQL_USER", "MYSQL_PASSWORD",
            "DATABASE_URL"
        ]
        
        for key in env_keys:
            value = os.getenv(key)
            if value:
                self._env_vars[key] = value
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file {self.config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file {self.config_path}: {e}")
    
    def get_api_token(self) -> str:
        """Get Smartsheet API token from environment."""
        token = (
            self._env_vars.get("SMARTSHEET_API_TOKEN") or
            self._env_vars.get("SS_API_TOKEN")
        )
        
        if not token:
            raise ValueError(
                "Smartsheet API token not found. Set SMARTSHEET_API_TOKEN "
                "or SS_API_TOKEN environment variable."
            )
        
        return token
    
    def get_database_config(self, db_type: str = "postgresql") -> Optional[Dict[str, str]]:
        """Get database configuration from environment."""
        # Check for DATABASE_URL first
        database_url = self._env_vars.get("DATABASE_URL")
        if database_url:
            return {"database_url": database_url}
        
        # Check for individual components based on database type
        if db_type == "mysql":
            prefix_keys = ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DB", 
                          "MYSQL_USER", "MYSQL_PASSWORD"]
            prefix = "mysql_"
        else:  # postgresql
            prefix_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", 
                          "POSTGRES_USER", "POSTGRES_PASSWORD"]
            prefix = "postgres_"
        
        db_config = {}
        for key in prefix_keys:
            value = self._env_vars.get(key)
            if value:
                db_config[key.lower().replace(prefix, "")] = value
        
        return db_config if db_config else None
    
    @property
    def config(self) -> Config:
        """Get the loaded configuration."""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config


def load_config(config_path: Optional[str] = None, 
               env_file: Optional[str] = None) -> tuple[Config, ConfigManager]:
    """Load configuration and return config object and manager."""
    manager = ConfigManager(config_path, env_file)
    config = manager.load()
    return config, manager