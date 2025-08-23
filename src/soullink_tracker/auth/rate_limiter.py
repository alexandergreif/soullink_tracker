"""Rate limiting for authentication endpoints to prevent brute force attacks."""

import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple
from collections import defaultdict, deque
import logging

from fastapi import HTTPException, status, Request

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints."""
    
    def __init__(self):
        """Initialize rate limiter with sliding window counters."""
        # Store request timestamps for each IP/endpoint combination
        # Format: {(ip, endpoint): deque of timestamps}
        self._requests: Dict[Tuple[str, str], deque] = defaultdict(deque)
        
        # Store failed authentication attempts
        # Format: {ip: deque of failure timestamps}
        self._failures: Dict[str, deque] = defaultdict(deque)
        
        # Configuration
        self.window_seconds = 60  # 1 minute sliding window
        self.max_requests_per_window = 10  # Max requests per IP per endpoint
        self.max_failures_per_window = 5   # Max failed auth attempts per IP
        self.failure_penalty_minutes = 15  # Block IP after max failures
        
        # Track blocked IPs
        # Format: {ip: block_until_timestamp}
        self._blocked_ips: Dict[str, float] = {}
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_requests(self, ip: str, endpoint: str, now: float) -> None:
        """Remove old requests outside the sliding window."""
        key = (ip, endpoint)
        cutoff = now - self.window_seconds
        
        # Remove old requests
        while self._requests[key] and self._requests[key][0] < cutoff:
            self._requests[key].popleft()
    
    def _cleanup_old_failures(self, ip: str, now: float) -> None:
        """Remove old failure records outside the sliding window."""
        cutoff = now - self.window_seconds
        
        while self._failures[ip] and self._failures[ip][0] < cutoff:
            self._failures[ip].popleft()
    
    def _cleanup_expired_blocks(self, now: float) -> None:
        """Remove expired IP blocks."""
        expired_ips = [ip for ip, block_until in self._blocked_ips.items() if now > block_until]
        for ip in expired_ips:
            del self._blocked_ips[ip]
            logger.info(f"Unblocked IP {ip} after penalty period")
    
    def check_rate_limit(self, request: Request, endpoint: str) -> None:
        """
        Check if request should be rate limited.
        
        Args:
            request: FastAPI request object
            endpoint: Endpoint identifier (e.g., "login", "refresh")
            
        Raises:
            HTTPException: If rate limit exceeded (429 Too Many Requests)
        """
        ip = self._get_client_ip(request)
        now = time.time()
        
        # Cleanup expired blocks
        self._cleanup_expired_blocks(now)
        
        # Check if IP is currently blocked
        if ip in self._blocked_ips:
            block_until = datetime.fromtimestamp(self._blocked_ips[ip], tz=timezone.utc)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"IP blocked due to too many failed authentication attempts. Try again after {block_until.isoformat()}",
                headers={"Retry-After": str(int(self._blocked_ips[ip] - now))}
            )
        
        # Cleanup old requests and failures
        self._cleanup_old_requests(ip, endpoint, now)
        self._cleanup_old_failures(ip, now)
        
        # Check request rate limit
        key = (ip, endpoint)
        current_requests = len(self._requests[key])
        
        if current_requests >= self.max_requests_per_window:
            logger.warning(f"Rate limit exceeded for IP {ip} on endpoint {endpoint}: {current_requests} requests in window")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Maximum {self.max_requests_per_window} requests per {self.window_seconds} seconds allowed",
                headers={"Retry-After": str(self.window_seconds)}
            )
        
        # Record this request
        self._requests[key].append(now)
        logger.debug(f"Rate limit check passed for IP {ip} on endpoint {endpoint}: {current_requests + 1}/{self.max_requests_per_window}")
    
    def record_auth_failure(self, request: Request) -> None:
        """
        Record a failed authentication attempt.
        
        Args:
            request: FastAPI request object
        """
        ip = self._get_client_ip(request)
        now = time.time()
        
        # Cleanup old failures
        self._cleanup_old_failures(ip, now)
        
        # Record this failure
        self._failures[ip].append(now)
        failure_count = len(self._failures[ip])
        
        logger.warning(f"Authentication failure for IP {ip}: {failure_count}/{self.max_failures_per_window} in window")
        
        # Check if IP should be blocked
        if failure_count >= self.max_failures_per_window:
            block_until = now + (self.failure_penalty_minutes * 60)
            self._blocked_ips[ip] = block_until
            
            block_until_dt = datetime.fromtimestamp(block_until, tz=timezone.utc)
            logger.error(f"Blocked IP {ip} until {block_until_dt.isoformat()} due to {failure_count} failed auth attempts")
    
    def record_auth_success(self, request: Request) -> None:
        """
        Record a successful authentication (clears failure count).
        
        Args:
            request: FastAPI request object
        """
        ip = self._get_client_ip(request)
        
        # Clear failure history for this IP on successful auth
        if ip in self._failures:
            del self._failures[ip]
            logger.debug(f"Cleared failure history for IP {ip} after successful authentication")
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        now = time.time()
        active_blocks = sum(1 for block_until in self._blocked_ips.values() if now < block_until)
        
        return {
            "window_seconds": self.window_seconds,
            "max_requests_per_window": self.max_requests_per_window,
            "max_failures_per_window": self.max_failures_per_window,
            "failure_penalty_minutes": self.failure_penalty_minutes,
            "tracked_ips": len(self._requests),
            "active_blocks": active_blocks,
            "total_blocked_ips": len(self._blocked_ips)
        }


# Global rate limiter instance
rate_limiter = RateLimiter()