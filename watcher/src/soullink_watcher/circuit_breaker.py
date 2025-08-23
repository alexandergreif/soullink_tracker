"""Circuit breaker pattern implementation for HTTP requests."""

import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation that fails fast when downstream service is unhealthy.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail immediately 
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
        reset_timeout_seconds: int = 60
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes needed to close circuit from half-open
            timeout_seconds: How long to keep circuit open before trying half-open
            reset_timeout_seconds: How long to wait before resetting failure count
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.reset_timeout_seconds = reset_timeout_seconds
        
        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_request_time: Optional[datetime] = None
        
    def call(self, func: Callable[[], Any]) -> Any:
        """
        Call function with circuit breaker protection.
        
        Args:
            func: Function to call
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: If circuit is open
            Exception: Any exception from the function
        """
        now = datetime.now(timezone.utc)
        
        # Update state based on time
        self._update_state(now)
        
        if self.state == CircuitState.OPEN:
            logger.warning("Circuit breaker is OPEN - failing fast")
            raise CircuitOpenError("Circuit breaker is open")
        
        try:
            result = func()
            self._on_success(now)
            return result
            
        except Exception as e:
            self._on_failure(now, e)
            raise
    
    def _update_state(self, now: datetime) -> None:
        """Update circuit breaker state based on current time."""
        if self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if (self.last_failure_time and 
                now - self.last_failure_time >= timedelta(seconds=self.timeout_seconds)):
                logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count if enough time has passed since last failure
            if (self.last_failure_time and
                now - self.last_failure_time >= timedelta(seconds=self.reset_timeout_seconds)):
                if self.failure_count > 0:
                    logger.info(f"Resetting failure count after {self.reset_timeout_seconds}s timeout")
                    self.failure_count = 0
    
    def _on_success(self, now: datetime) -> None:
        """Handle successful request."""
        self.last_request_time = now
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(f"Circuit breaker success in HALF_OPEN: {self.success_count}/{self.success_threshold}")
            
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker transitioning from HALF_OPEN to CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                logger.debug(f"Resetting failure count after successful request")
                self.failure_count = 0
    
    def _on_failure(self, now: datetime, exception: Exception) -> None:
        """Handle failed request."""
        self.last_request_time = now
        self.last_failure_time = now
        
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            logger.warning(f"Circuit breaker failure in HALF_OPEN - returning to OPEN: {exception}")
            self.state = CircuitState.OPEN
            self.failure_count += 1
            
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            logger.warning(f"Circuit breaker failure {self.failure_count}/{self.failure_threshold}: {exception}")
            
            if self.failure_count >= self.failure_threshold:
                logger.error(f"Circuit breaker opening after {self.failure_count} failures")
                self.state = CircuitState.OPEN
    
    def get_stats(self) -> dict:
        """Get current circuit breaker statistics."""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None,
        }
    
    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        logger.info("Manually resetting circuit breaker to CLOSED state")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def force_open(self) -> None:
        """Manually force circuit breaker to open state."""
        logger.warning("Manually forcing circuit breaker to OPEN state")
        self.state = CircuitState.OPEN
        self.last_failure_time = datetime.now(timezone.utc)


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerHTTPClient:
    """HTTP client wrapper with circuit breaker protection."""
    
    def __init__(self, 
                 http_client: Any,
                 failure_threshold: int = 5,
                 timeout_seconds: int = 60):
        """
        Initialize circuit breaker HTTP client.
        
        Args:
            http_client: Underlying HTTP client (requests session, etc.)
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: How long to keep circuit open
        """
        self.http_client = http_client
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds
        )
    
    def request(self, *args, **kwargs) -> Any:
        """Make HTTP request with circuit breaker protection."""
        def make_request():
            return self.http_client.request(*args, **kwargs)
        
        return self.circuit_breaker.call(make_request)
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return self.circuit_breaker.get_stats()
    
    def reset(self) -> None:
        """Reset circuit breaker."""
        self.circuit_breaker.reset()
    
    def force_open(self) -> None:
        """Force circuit breaker open."""
        self.circuit_breaker.force_open()