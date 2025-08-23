"""HTTP client for sending events to the SoulLink API."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from .config import WatcherConfig
from .retry import parse_retry_after
from .spool import SpoolRecord
from .circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


@dataclass
class EventSendResult:
    """Result of attempting to send an event to the API."""
    
    success: bool
    status_code: Optional[int]
    response_json: Optional[Dict[str, Any]]
    retriable: bool
    retry_after: Optional[datetime]
    message: Optional[str]


class EventSender:
    """HTTP client for sending events to the SoulLink API."""
    
    def __init__(self, timeout_secs: float = 10.0, circuit_breaker_enabled: bool = True):
        """
        Initialize the event sender.

        Args:
            timeout_secs: HTTP request timeout in seconds
            circuit_breaker_enabled: Whether to enable circuit breaker protection
        """
        self.timeout_secs = timeout_secs
        self.session = requests.Session()
        
        # Set user agent
        self.session.headers.update({
            'User-Agent': 'SoulLink-Watcher/1.0.0'
        })
        
        # Initialize circuit breaker
        self.circuit_breaker_enabled = circuit_breaker_enabled
        if circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60,
                reset_timeout_seconds=300  # 5 minutes
            )
        else:
            self.circuit_breaker = None
    
    def send_event(self, cfg: WatcherConfig, record: SpoolRecord) -> EventSendResult:
        """
        Send a single event to the API.
        
        Args:
            cfg: Watcher configuration
            record: Spool record containing the event data
        
        Returns:
            EventSendResult with the outcome
        """
        # Construct URL
        url = cfg.base_url.rstrip('/') + record.endpoint_path
        
        # Prepare headers
        headers = record.headers.copy()
        headers.update({
            'Authorization': f'Bearer {cfg.token}',
            'Content-Type': 'application/json',
            'Idempotency-Key': record.idempotency_key
        })
        
        # Check request size (align with server limit of 16KB)
        try:
            request_body = json.dumps(record.request_json, separators=(',', ':'))
            if len(request_body.encode('utf-8')) > 16 * 1024:  # 16KB
                return EventSendResult(
                    success=False,
                    status_code=413,
                    response_json=None,
                    retriable=False,  # Non-retryable: request too large
                    retry_after=None,
                    message="Request body too large (>16KB)"
                )
        except Exception as e:
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=False,  # Non-retryable: malformed JSON
                retry_after=None,
                message=f"Failed to serialize request JSON: {e}"
            )
        
        # Send the request with circuit breaker protection
        try:
            logger.debug(f"Sending {record.method} {url} with {len(request_body)} bytes")
            
            def make_request():
                return self.session.request(
                    method=record.method,
                    url=url,
                    headers=headers,
                    data=request_body,
                    timeout=self.timeout_secs
                )
            
            # Use circuit breaker if enabled
            if self.circuit_breaker_enabled and self.circuit_breaker:
                response = self.circuit_breaker.call(make_request)
            else:
                response = make_request()
            
            # Parse response JSON if possible
            response_json = None
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_json = response.json()
            except Exception:
                pass  # Ignore JSON parsing errors
            
            # Classify the response
            return self._classify_response(response, response_json, record)
            
        except CircuitOpenError:
            logger.warning(f"Circuit breaker is open for {url} - failing fast")
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=True,  # Circuit breaker failures are retryable
                retry_after=None,
                message="Circuit breaker is open - failing fast"
            )
            
        except Timeout:
            logger.warning(f"Request timeout for {url}")
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=True,  # Timeouts are retryable
                retry_after=None,
                message="Request timeout"
            )
            
        except ConnectionError as e:
            logger.warning(f"Connection error for {url}: {e}")
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=True,  # Connection errors are retryable
                retry_after=None,
                message=f"Connection error: {e}"
            )
            
        except RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=True,  # Other request errors are generally retryable
                retry_after=None,
                message=f"Request error: {e}"
            )
            
        except Exception as e:
            logger.error(f"Unexpected error sending event: {e}")
            return EventSendResult(
                success=False,
                status_code=None,
                response_json=None,
                retriable=True,  # Unknown errors are retryable
                retry_after=None,
                message=f"Unexpected error: {e}"
            )
    
    def _classify_response(
        self, 
        response: requests.Response, 
        response_json: Optional[Dict[str, Any]], 
        record: SpoolRecord
    ) -> EventSendResult:
        """
        Classify HTTP response and determine retry policy.
        
        Args:
            response: HTTP response object
            response_json: Parsed response JSON (if any)
            record: Original spool record
        
        Returns:
            EventSendResult with classification
        """
        status_code = response.status_code
        now = datetime.now(timezone.utc)
        
        # Parse Retry-After header if present
        retry_after = None
        if 'retry-after' in response.headers:
            retry_after = parse_retry_after(response.headers['retry-after'], now)
        
        # Success case
        if status_code == 202:
            logger.info(f"Event sent successfully: {record.idempotency_key}")
            return EventSendResult(
                success=True,
                status_code=status_code,
                response_json=response_json,
                retriable=False,
                retry_after=None,
                message="Event processed successfully"
            )
        
        # Client errors (4xx)
        if 400 <= status_code < 500:
            # Determine if retryable
            if status_code in (400, 404, 413, 422):
                # Bad request, not found, payload too large, validation error
                # These are non-retryable client errors
                logger.warning(f"Non-retryable client error {status_code} for {record.idempotency_key}")
                return EventSendResult(
                    success=False,
                    status_code=status_code,
                    response_json=response_json,
                    retriable=False,
                    retry_after=None,
                    message=f"Client error {status_code}: {self._extract_error_message(response_json)}"
                )
            
            elif status_code in (401, 403):
                # Unauthorized, forbidden - could be token issues
                logger.error(f"Authentication/authorization error {status_code} for {record.idempotency_key}")
                return EventSendResult(
                    success=False,
                    status_code=status_code,
                    response_json=response_json,
                    retriable=False,  # Don't retry auth errors
                    retry_after=None,
                    message=f"Authentication error {status_code}: {self._extract_error_message(response_json)}"
                )
            
            elif status_code in (409, 429):
                # Conflict, too many requests - retryable
                logger.info(f"Retryable client error {status_code} for {record.idempotency_key}")
                return EventSendResult(
                    success=False,
                    status_code=status_code,
                    response_json=response_json,
                    retriable=True,
                    retry_after=retry_after,
                    message=f"Retryable error {status_code}: {self._extract_error_message(response_json)}"
                )
            
            else:
                # Other 4xx errors - assume non-retryable
                logger.warning(f"Client error {status_code} for {record.idempotency_key}")
                return EventSendResult(
                    success=False,
                    status_code=status_code,
                    response_json=response_json,
                    retriable=False,
                    retry_after=None,
                    message=f"Client error {status_code}: {self._extract_error_message(response_json)}"
                )
        
        # Server errors (5xx) - all retryable
        if 500 <= status_code < 600:
            logger.warning(f"Server error {status_code} for {record.idempotency_key}")
            return EventSendResult(
                success=False,
                status_code=status_code,
                response_json=response_json,
                retriable=True,
                retry_after=retry_after,
                message=f"Server error {status_code}: {self._extract_error_message(response_json)}"
            )
        
        # Other status codes - assume non-retryable
        logger.warning(f"Unexpected status code {status_code} for {record.idempotency_key}")
        return EventSendResult(
            success=False,
            status_code=status_code,
            response_json=response_json,
            retriable=False,
            retry_after=None,
            message=f"Unexpected status code {status_code}"
        )
    
    def _extract_error_message(self, response_json: Optional[Dict[str, Any]]) -> str:
        """Extract error message from response JSON."""
        if not response_json:
            return "No error details"
        
        # Try RFC 9457 Problem Details format
        if 'detail' in response_json:
            return response_json['detail']
        
        # Try common error formats
        if 'message' in response_json:
            return response_json['message']
        
        if 'error' in response_json:
            return str(response_json['error'])
        
        return "Unknown error"
    
    def get_circuit_breaker_stats(self) -> Optional[dict]:
        """Get circuit breaker statistics."""
        if self.circuit_breaker_enabled and self.circuit_breaker:
            return self.circuit_breaker.get_stats()
        return None
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker to closed state."""
        if self.circuit_breaker_enabled and self.circuit_breaker:
            self.circuit_breaker.reset()
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()