"""File operation utilities for ss2db."""

import json
import gzip
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from ss2db.utils.logging import get_logger


class FileManager:
    """Manages file operations with backup, compression, and validation."""
    
    def __init__(self, backup_existing: bool = True, compression: bool = False):
        self.backup_existing = backup_existing
        self.compression = compression
        self.logger = get_logger(__name__)
    
    def ensure_directory(self, path: Path) -> None:
        """Ensure directory exists, creating it if necessary."""
        path.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Directory ensured: {path}")
    
    def backup_file(self, file_path: Path) -> Optional[Path]:
        """Backup existing file with timestamp."""
        if not file_path.exists():
            return None
        
        if not self.backup_existing:
            return None
        
        timestamp = int(time.time())
        backup_path = file_path.with_suffix(f'.backup.{timestamp}{file_path.suffix}')
        
        try:
            shutil.copy2(file_path, backup_path)
            self.logger.info(f"Backed up {file_path} to {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.warning(f"Failed to backup {file_path}: {e}")
            return None
    
    def write_json(self, data: Any, file_path: Path, indent: int = 2) -> Dict[str, Any]:
        """Write data to JSON file with optional compression."""
        self.ensure_directory(file_path.parent)
        self.backup_file(file_path)
        
        start_time = time.time()
        
        if self.compression and not file_path.suffix.endswith('.gz'):
            file_path = file_path.with_suffix(f'{file_path.suffix}.gz')
        
        try:
            if self.compression:
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
            
            elapsed_time = time.time() - start_time
            file_size = file_path.stat().st_size
            
            self.logger.info(f"JSON written: {file_path} ({file_size:,} bytes, {elapsed_time:.2f}s)")
            
            return {
                'file_path': str(file_path),
                'file_size': file_size,
                'elapsed_time': elapsed_time,
                'compression': self.compression
            }
            
        except Exception as e:
            self.logger.error(f"Failed to write JSON to {file_path}: {e}")
            raise
    
    def read_json(self, file_path: Path) -> Any:
        """Read data from JSON file with automatic compression detection."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            if file_path.suffix.endswith('.gz'):
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            self.logger.debug(f"JSON read: {file_path}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to read JSON from {file_path}: {e}")
            raise
    
    def write_text(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Write text content to file."""
        self.ensure_directory(file_path.parent)
        self.backup_file(file_path)
        
        start_time = time.time()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            elapsed_time = time.time() - start_time
            file_size = file_path.stat().st_size
            
            self.logger.info(f"Text written: {file_path} ({file_size:,} bytes, {elapsed_time:.2f}s)")
            
            return {
                'file_path': str(file_path),
                'file_size': file_size,
                'elapsed_time': elapsed_time
            }
            
        except Exception as e:
            self.logger.error(f"Failed to write text to {file_path}: {e}")
            raise
    
    def validate_json_file(self, file_path: Path) -> bool:
        """Validate that a JSON file is readable and well-formed."""
        try:
            self.read_json(file_path)
            return True
        except Exception as e:
            self.logger.error(f"JSON validation failed for {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get file information including size, timestamps, etc."""
        if not file_path.exists():
            return {'exists': False}
        
        stat = file_path.stat()
        
        return {
            'exists': True,
            'size': stat.st_size,
            'size_mb': stat.st_size / (1024 * 1024),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_compressed': file_path.suffix.endswith('.gz')
        }


class OutputManager:
    """Manages output directory structure and file naming."""
    
    def __init__(self, base_dir: str = "./exports", timestamp_format: str = "%Y%m%d_%H%M%S"):
        self.base_dir = Path(base_dir)
        self.timestamp_format = timestamp_format
        self.logger = get_logger(__name__)
    
    def create_output_directory(self, resource_id: str) -> Path:
        """Create output directory for a specific resource."""
        output_dir = self.base_dir / resource_id
        output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Output directory: {output_dir}")
        return output_dir
    
    def generate_filenames(self, resource_id: str, timestamp: Optional[str] = None) -> Dict[str, Path]:
        """Generate standard filenames for export outputs."""
        if not timestamp:
            timestamp = datetime.now().strftime(self.timestamp_format)
        
        output_dir = self.create_output_directory(resource_id)
        
        return {
            'data': output_dir / f"{timestamp}_data.json",
            'schema': output_dir / f"{timestamp}_schema.json", 
            'sql': output_dir / f"{timestamp}_import.sql",
            'log': output_dir / f"{timestamp}_log.txt",
            'config': output_dir / "config_used.yaml",
            'directory': output_dir
        }
    
    def save_config_snapshot(self, config_dict: Dict[str, Any], file_path: Path) -> None:
        """Save configuration snapshot for reproducibility."""
        try:
            import yaml
            
            with open(file_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            
            self.logger.info(f"Configuration snapshot saved: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save configuration snapshot: {e}")


def get_file_manager(config: Optional[Dict[str, Any]] = None) -> FileManager:
    """Get configured file manager instance."""
    config = config or {}
    return FileManager(
        backup_existing=config.get('backup_existing', True),
        compression=config.get('compression', False)
    )


def get_output_manager(config: Optional[Dict[str, Any]] = None) -> OutputManager:
    """Get configured output manager instance."""
    config = config or {}
    return OutputManager(
        base_dir=config.get('directory', './exports'),
        timestamp_format=config.get('timestamp_format', '%Y%m%d_%H%M%S')
    )