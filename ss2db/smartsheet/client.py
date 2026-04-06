"""
Smartsheet API client with rate limiting and error handling.
"""

import threading
import time
from typing import Any, Dict, Optional, List
import requests
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field

from ss2db.utils.logging import get_logger


@dataclass
class RateLimiter:
    """Rate limiter for Smartsheet API calls."""
    
    max_requests_per_minute: int = 100
    buffer_requests: int = 5
    request_times: List[float] = field(default_factory=list)
    
    def __post_init__(self):
        self.effective_limit = self.max_requests_per_minute - self.buffer_requests
        self.window_seconds = 60
        self._lock = threading.Lock()

    def wait_if_needed(self) -> float:
        """Wait if necessary to respect rate limits. Returns wait time."""
        # Phase 1: Check if we need to wait (under lock)
        wait_time = 0.0
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.effective_limit:
                wait_until = self.request_times[0] + self.window_seconds
                wait_time = max(0, wait_until - now)

        # Phase 2: Sleep outside the lock to avoid blocking other threads
        if wait_time > 0:
            time.sleep(wait_time)

        # Phase 3: Record this request (under lock)
        with self._lock:
            self.request_times.append(time.time())

        return wait_time

    def get_current_usage(self) -> Dict[str, Any]:
        """Get current rate limit usage stats."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            recent_requests = [t for t in self.request_times if t > cutoff]

            return {
                "requests_in_last_minute": len(recent_requests),
                "effective_limit": self.effective_limit,
                "usage_percentage": (len(recent_requests) / self.effective_limit) * 100 if self.effective_limit > 0 else 0
            }


class SmartsheetAPIError(Exception):
    """Custom exception for Smartsheet API errors."""
    
    def __init__(self, status_code: int, message: str, response_data: Optional[Dict] = None):
        self.status_code = status_code
        self.message = message
        self.response_data = response_data or {}
        super().__init__(f"Smartsheet API Error {status_code}: {message}")


class SmartsheetClient:
    """
    Smartsheet API client with rate limiting, retry logic, and pagination support.
    """
    
    def __init__(self, api_token: str, config: Optional[Dict[str, Any]] = None):
        self.api_token = api_token
        self.base_url = "https://api.smartsheet.com/2.0"
        self.session = requests.Session()
        self.logger = get_logger(__name__)
        
        # Configuration
        config = config or {}
        self.request_timeout = config.get('request_timeout', 30)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 5)
        self.rate_limit_buffer = config.get('rate_limit_buffer', 5)
        
        # Set up session headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'ss2db/1.0.0'
        })
        
        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_requests_per_minute=100,
            buffer_requests=self.rate_limit_buffer
        )
        
        self.logger.info("Smartsheet client initialized")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a rate-limited API request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.retry_attempts):
            try:
                # Apply rate limiting
                wait_time = self.rate_limiter.wait_if_needed()
                if wait_time > 0:
                    self.logger.debug(f"Rate limit wait: {wait_time:.2f}s")
                
                # Log rate limit usage
                usage = self.rate_limiter.get_current_usage()
                self.logger.debug(f"Rate limit usage: {usage['requests_in_last_minute']}/{usage['effective_limit']} "
                                f"({usage['usage_percentage']:.1f}%)")
                
                # Make the request
                self.logger.debug(f"{method} {url}")
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.request_timeout,
                    **kwargs
                )
                
                # Handle different response codes
                if response.status_code == 200:
                    return response
                
                elif response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited. Waiting {retry_after}s before retry {attempt + 1}/{self.retry_attempts}")
                    time.sleep(retry_after)
                    continue
                
                elif response.status_code in [500, 502, 503, 504]:  # Server errors
                    if attempt < self.retry_attempts - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        self.logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s "
                                          f"(attempt {attempt + 1}/{self.retry_attempts})")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise SmartsheetAPIError(response.status_code, "Server error after retries", response.json())
                
                elif response.status_code in [400, 401, 403, 404]:  # Client errors
                    error_data = {}
                    try:
                        error_data = response.json()
                    except:
                        pass
                    
                    error_message = error_data.get('message', response.text)
                    raise SmartsheetAPIError(response.status_code, error_message, error_data)
                
                else:
                    # Other errors
                    raise SmartsheetAPIError(response.status_code, f"Unexpected status code: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Request timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{self.retry_attempts})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise SmartsheetAPIError(408, "Request timeout after retries")
            
            except requests.exceptions.RequestException as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Request error: {e}. Retrying in {wait_time}s (attempt {attempt + 1}/{self.retry_attempts})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise SmartsheetAPIError(0, f"Request failed after retries: {e}")
        
        raise SmartsheetAPIError(0, "All retry attempts exhausted")
    
    def get_user_info(self) -> Dict[str, Any]:
        """Get current user information to test API connectivity."""
        response = self._make_request('GET', '/users/me')
        return response.json()
    
    def get_sheet(self, sheet_id: str, include_all: bool = True, page_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Get sheet data with optional pagination.
        
        Args:
            sheet_id: The sheet ID to retrieve
            include_all: Include all metadata (columnType, format, etc.)
            page_size: For pagination (if supported)
        """
        params = {
            'level': '2',  # Include child objects
            'objectValue': 'true',  # Include object values for complex types
        }
        
        if include_all:
            params['include'] = 'columnType,format,objectValue'
        
        if page_size:
            params['pageSize'] = page_size
        
        response = self._make_request('GET', f'/sheets/{sheet_id}', params=params)
        return response.json()
    
    def get_report(self, report_id: str, include_all: bool = True, page_size: Optional[int] = None, 
                   page: Optional[int] = None) -> Dict[str, Any]:
        """
        Get report data with pagination support.
        
        Args:
            report_id: The report ID to retrieve
            include_all: Include all metadata
            page_size: Number of rows per page (max 10000)
            page: Page number (1-based)
        """
        params = {
            'level': '2',
            'objectValue': 'true',
        }
        
        if include_all:
            params['include'] = 'columnType,format,objectValue'
        
        if page_size:
            params['pageSize'] = min(page_size, 10000)  # Smartsheet max
        
        if page:
            params['page'] = page
        
        response = self._make_request('GET', f'/reports/{report_id}', params=params)
        return response.json()
    
    def get_sheet_columns(self, sheet_id: str) -> List[Dict[str, Any]]:
        """Get only column metadata for a sheet."""
        params = {
            'include': 'columnType,format'
        }
        
        response = self._make_request('GET', f'/sheets/{sheet_id}/columns', params=params)
        return response.json().get('data', [])
    
    def get_report_columns(self, report_id: str) -> List[Dict[str, Any]]:
        """Get column metadata for a report by fetching a small sample."""
        # Reports don't have a dedicated columns endpoint, so get first page with minimal data
        data = self.get_report(report_id, include_all=True, page_size=1, page=1)
        return data.get('columns', [])
    
    def get_workspace(self, workspace_id: str, load_all: bool = True) -> Dict[str, Any]:
        """
        Get workspace contents including sheets and folders.

        Args:
            workspace_id: The workspace ID to retrieve
            load_all: If True, include nested folder contents in a single request
        """
        params = {}
        if load_all:
            params['loadAll'] = 'true'

        response = self._make_request('GET', f'/workspaces/{workspace_id}', params=params)
        return response.json()

    def test_connection(self) -> bool:
        """Test API connection and return success status."""
        try:
            user_info = self.get_user_info()
            self.logger.info(f"API connection successful. User: {user_info.get('email', 'Unknown')}")
            return True
        except SmartsheetAPIError as e:
            self.logger.error(f"API connection failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error testing connection: {e}")
            return False
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return self.rate_limiter.get_current_usage()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.session.close()