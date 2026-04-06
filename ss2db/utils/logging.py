"""Logging utilities for ss2db."""

import logging
import logging.handlers
import sys
import threading
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


class ThreadNumberFilter(logging.Filter):
    """Logging filter that assigns a sequential 0-based number to each thread.

    The first thread to log gets number 0, the next gets 1, etc.
    The number is added to each log record as ``thread_num``.
    """

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._map: dict[int, int] = {}
        self._next = 0

    def filter(self, record: logging.LogRecord) -> bool:
        tid = record.thread
        with self._lock:
            if tid not in self._map:
                self._map[tid] = self._next
                self._next += 1
            record.thread_num = self._map[tid]
        return True


def setup_logging(
    level: str = "INFO",
    format_type: str = "detailed",
    log_file: Optional[str] = None,
    file_rotation: bool = True,
    max_file_size: str = "10MB",
    backup_count: int = 5,
    quiet: bool = False,
    verbose: bool = False
) -> logging.Logger:
    """Set up logging configuration."""
    
    # Determine log level
    if verbose:
        level = "DEBUG"
    elif quiet:
        level = "WARNING"
    
    log_level = getattr(logging, level.upper())
    
    # Create logger
    logger = logging.getLogger("ss2db")
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()

    # Shared filter that assigns sequential thread numbers
    thread_filter = ThreadNumberFilter()

    # Console handler with Rich formatting
    if not quiet:
        console = Console(stderr=True)
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=format_type == "detailed",
            rich_tracebacks=True,
            tracebacks_show_locals=level == "DEBUG"
        )
        
        if format_type == "simple":
            console_format = "[thread %(thread_num)d] %(message)s"
        else:
            console_format = "[thread %(thread_num)d] %(name)s: %(message)s"
        
        console_handler.setFormatter(logging.Formatter(console_format))
        console_handler.addFilter(thread_filter)
        console_handler.setLevel(log_level)
        logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_rotation:
            # Parse file size
            size_multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}
            size_str = max_file_size.upper()
            
            size_bytes = 10 * 1024 * 1024  # Default 10MB
            for suffix, multiplier in size_multipliers.items():
                if size_str.endswith(suffix):
                    size_bytes = int(size_str[:-len(suffix)]) * multiplier
                    break
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=size_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
        
        # Detailed format for file logging
        file_format = (
            "%(asctime)s - [thread %(thread_num)d] %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(logging.Formatter(file_format))
        file_handler.addFilter(thread_filter)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for files
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "ss2db") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class ProgressLogger:
    """Logger for progress tracking with rich formatting."""
    
    def __init__(self, logger: logging.Logger, total: Optional[int] = None):
        self.logger = logger
        self.total = total
        self.current = 0
        
    def update(self, increment: int = 1, message: str = "") -> None:
        """Update progress and log message."""
        self.current += increment
        
        if self.total:
            percentage = (self.current / self.total) * 100
            progress_msg = f"[{self.current}/{self.total}] ({percentage:.1f}%)"
        else:
            progress_msg = f"[{self.current}]"
        
        if message:
            full_message = f"{progress_msg} {message}"
        else:
            full_message = progress_msg
            
        self.logger.info(full_message)
    
    def complete(self, message: str = "Complete") -> None:
        """Mark progress as complete."""
        if self.total:
            self.current = self.total
        self.logger.info(f"✓ {message}")
    
    def error(self, message: str) -> None:
        """Log an error."""
        self.logger.error(f"✗ {message}")
    
    def warning(self, message: str) -> None:
        """Log a warning."""
        self.logger.warning(f"⚠ {message}")


def log_operation_start(logger: logging.Logger, operation: str, **kwargs) -> None:
    """Log the start of an operation with context."""
    context = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"Starting {operation}" + (f" ({context})" if context else ""))


def log_operation_complete(logger: logging.Logger, operation: str, 
                         duration: Optional[float] = None, **kwargs) -> None:
    """Log the completion of an operation."""
    context = " ".join(f"{k}={v}" for k, v in kwargs.items())
    duration_str = f" in {duration:.2f}s" if duration else ""
    logger.info(f"✓ Completed {operation}{duration_str}" + 
               (f" ({context})" if context else ""))