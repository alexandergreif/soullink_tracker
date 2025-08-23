"""Rate limiting for authentication endpoints to prevent brute force attacks."""

import time
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
from collections import defaultdict, deque
from dataclasses import dataclass
import logging

from fastapi import Request, HTTPException, status  # type: ignore
from ..utils.logging_config import get_logger

logger = get_logger('auth')


@dataclass
class RateLimitTier:
    """Configuration for a specific rate limiting tier."""

    max_requests: int
    window_seconds: int
    description: str = ""


@dataclass
class RateLimitConfig:
    """Global rate limiting configuration."""

    # Global settings
    failure_penalty_minutes: int = 15
    max_failures_before_block: int = 5
    enable_user_limits: bool = True
    enable_ip_bypass: bool = True
    admin_bypass_ips: Optional[set] = None

    # Built-in tiers - use default_factory for mutable defaults
    auth_strict: Optional[RateLimitTier] = None
    api_moderate: Optional[RateLimitTier] = None
    websocket_lenient: Optional[RateLimitTier] = None

    def __post_init__(self):
        if self.admin_bypass_ips is None:
            self.admin_bypass_ips = {"127.0.0.1", "::1"}  # localhost by default

        if self.auth_strict is None:
            self.auth_strict = RateLimitTier(10, 60, "Authentication endpoints")

        if self.api_moderate is None:
            self.api_moderate = RateLimitTier(60, 60, "API endpoints")

        if self.websocket_lenient is None:
            self.websocket_lenient = RateLimitTier(120, 60, "WebSocket connections")


class GlobalRateLimiter:
    """Enhanced rate limiter with tiered limits and global middleware support."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter with sliding window counters."""
        self.config = config or RateLimitConfig()

        # Store request timestamps for each (key, tier) combination
        # Key can be IP or user_id, tier is the rate limit category
        # Format: {(key, tier): deque of timestamps}
        self._requests: Dict[Tuple[str, str], deque] = defaultdict(deque)

        # Store failed authentication attempts (IP-based only)
        # Format: {ip: deque of failure timestamps}
        self._failures: Dict[str, deque] = defaultdict(deque)

        # Track blocked IPs
        # Format: {ip: block_until_timestamp}
        self._blocked_ips: Dict[str, float] = {}

        # Tier mapping for endpoints
        self._endpoint_tiers = {
            "/auth/": "auth_strict",
            "/v1/events": "api_moderate",
            "/v1/runs": "api_moderate",
            "/v1/data": "api_moderate",
            "/v1/admin": "api_moderate",
            "/v1/ws": "websocket_lenient",
        }

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

    def _get_tier_for_endpoint(self, endpoint_path: str) -> str:
        """Determine the rate limit tier for an endpoint."""
        for path_prefix, tier in self._endpoint_tiers.items():
            if endpoint_path.startswith(path_prefix):
                return tier
        # Default to moderate API limits for unmatched endpoints
        return "api_moderate"

    def _get_tier_config(self, tier: str) -> RateLimitTier:
        """Get the configuration for a specific tier."""
        tier_config = getattr(self.config, tier, self.config.api_moderate)
        if tier_config is None:
            # Fallback to a default tier if none configured
            return RateLimitTier(60, 60, "Default API tier")
        return tier_config

    def _should_bypass_limits(self, ip: str, user_id: Optional[str] = None) -> bool:
        """Check if the request should bypass rate limiting."""
        if not self.config.enable_ip_bypass:
            return False

        # Check if IP is in admin bypass list
        if self.config.admin_bypass_ips and ip in self.config.admin_bypass_ips:
            logger.debug(f"Bypassing rate limits for admin IP: {ip}")
            return True

        return False

    def _cleanup_old_requests(
        self, key: Tuple[str, str], now: float, window_seconds: int
    ) -> None:
        """Remove old requests outside the sliding window."""
        cutoff = now - window_seconds

        # Remove old requests
        while self._requests[key] and self._requests[key][0] < cutoff:
            self._requests[key].popleft()

    def _cleanup_old_failures(self, ip: str, now: float) -> None:
        """Remove old failure records outside the sliding window."""
        assert self.config.auth_strict is not None
        cutoff = now - self.config.auth_strict.window_seconds

        while self._failures[ip] and self._failures[ip][0] < cutoff:
            self._failures[ip].popleft()

    def _cleanup_expired_blocks(self, now: float) -> None:
        """Remove expired IP blocks."""
        expired_ips = [
            ip for ip, block_until in self._blocked_ips.items() if now > block_until
        ]
        for ip in expired_ips:
            del self._blocked_ips[ip]
            logger.info(f"Unblocked IP {ip} after penalty period")

    def check_global_rate_limit(
        self, request: Request, endpoint_path: str, user_id: Optional[str] = None
    ) -> None:
        """
        Check global rate limits for any endpoint.

        Args:
            request: FastAPI request object
            endpoint_path: Full endpoint path (e.g., "/v1/events", "/auth/login")
            user_id: Optional authenticated user ID for user-based rate limiting

        Raises:
            HTTPException: If rate limit exceeded (429 Too Many Requests)
        """
        ip = self._get_client_ip(request)
        now = time.time()

        # Check for bypass conditions
        if self._should_bypass_limits(ip, user_id):
            return

        # Cleanup expired blocks
        self._cleanup_expired_blocks(now)

        # Check if IP is currently blocked (from auth failures)
        if ip in self._blocked_ips:
            block_until = datetime.fromtimestamp(self._blocked_ips[ip], tz=timezone.utc)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"IP blocked due to too many failed authentication attempts. Try again after {block_until.isoformat()}",
                headers={"Retry-After": str(int(self._blocked_ips[ip] - now))},
            )

        # Determine tier and configuration
        tier = self._get_tier_for_endpoint(endpoint_path)
        tier_config = self._get_tier_config(tier)

        # Check IP-based rate limit
        ip_key = (ip, tier)
        self._cleanup_old_requests(ip_key, now, tier_config.window_seconds)
        current_ip_requests = len(self._requests[ip_key])

        if current_ip_requests >= tier_config.max_requests:
            logger.warning(
                f"IP rate limit exceeded for {ip} on {endpoint_path} ({tier}): {current_ip_requests} requests in window"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests from your IP. Maximum {tier_config.max_requests} requests per {tier_config.window_seconds} seconds allowed for {tier_config.description.lower()}",
                headers={"Retry-After": str(tier_config.window_seconds)},
            )

        # Check user-based rate limit if enabled and user is authenticated
        if self.config.enable_user_limits and user_id:
            user_key = (user_id, tier)
            self._cleanup_old_requests(user_key, now, tier_config.window_seconds)
            current_user_requests = len(self._requests[user_key])

            if current_user_requests >= tier_config.max_requests:
                logger.warning(
                    f"User rate limit exceeded for {user_id} on {endpoint_path} ({tier}): {current_user_requests} requests in window"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests for your account. Maximum {tier_config.max_requests} requests per {tier_config.window_seconds} seconds allowed for {tier_config.description.lower()}",
                    headers={"Retry-After": str(tier_config.window_seconds)},
                )

            # Record user request
            self._requests[user_key].append(now)

        # Record IP request
        self._requests[ip_key].append(now)
        logger.debug(
            f"Global rate limit check passed for IP {ip} on {endpoint_path} ({tier}): {current_ip_requests + 1}/{tier_config.max_requests}"
        )

    def check_rate_limit(self, request: Request, endpoint: str) -> None:
        """
        Legacy rate limit check for authentication endpoints (backward compatibility).

        Args:
            request: FastAPI request object
            endpoint: Endpoint identifier (e.g., "login", "refresh")

        Raises:
            HTTPException: If rate limit exceeded (429 Too Many Requests)
        """
        # Map legacy endpoint names to paths for tier determination
        endpoint_mapping = {
            "login": "/auth/login",
            "jwt-login": "/auth/jwt-login",
            "refresh": "/auth/refresh",
        }

        endpoint_path = endpoint_mapping.get(endpoint, f"/auth/{endpoint}")
        self.check_global_rate_limit(request, endpoint_path)

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

        logger.warning(
            f"Authentication failure for IP {ip}: {failure_count}/{self.config.max_failures_before_block} in window"
        )

        # Check if IP should be blocked
        if failure_count >= self.config.max_failures_before_block:
            block_until = now + (self.config.failure_penalty_minutes * 60)
            self._blocked_ips[ip] = block_until

            block_until_dt = datetime.fromtimestamp(block_until, tz=timezone.utc)
            logger.error(
                f"Blocked IP {ip} until {block_until_dt.isoformat()} due to {failure_count} failed auth attempts"
            )

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
            logger.debug(
                f"Cleared failure history for IP {ip} after successful authentication"
            )

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        now = time.time()
        active_blocks = sum(
            1 for block_until in self._blocked_ips.values() if now < block_until
        )

        # Count unique keys being tracked
        unique_keys = set()
        for key, tier in self._requests.keys():
            unique_keys.add(key)

        # Ensure all tiers are initialized (they should be via __post_init__)
        assert self.config.auth_strict is not None
        assert self.config.api_moderate is not None
        assert self.config.websocket_lenient is not None

        return {
            "tiers": {
                "auth_strict": {
                    "max_requests": self.config.auth_strict.max_requests,
                    "window_seconds": self.config.auth_strict.window_seconds,
                    "description": self.config.auth_strict.description,
                },
                "api_moderate": {
                    "max_requests": self.config.api_moderate.max_requests,
                    "window_seconds": self.config.api_moderate.window_seconds,
                    "description": self.config.api_moderate.description,
                },
                "websocket_lenient": {
                    "max_requests": self.config.websocket_lenient.max_requests,
                    "window_seconds": self.config.websocket_lenient.window_seconds,
                    "description": self.config.websocket_lenient.description,
                },
            },
            "settings": {
                "max_failures_before_block": self.config.max_failures_before_block,
                "failure_penalty_minutes": self.config.failure_penalty_minutes,
                "enable_user_limits": self.config.enable_user_limits,
                "enable_ip_bypass": self.config.enable_ip_bypass,
                "admin_bypass_ips": list(self.config.admin_bypass_ips)
                if self.config.admin_bypass_ips
                else [],
            },
            "stats": {
                "tracked_keys": len(unique_keys),
                "total_request_buckets": len(self._requests),
                "active_blocks": active_blocks,
                "total_blocked_ips": len(self._blocked_ips),
            },
        }


# Keep legacy RateLimiter class for backward compatibility
class RateLimiter(GlobalRateLimiter):
    """Legacy rate limiter class for backward compatibility."""

    pass


# Global rate limiter instance
rate_limiter = GlobalRateLimiter()
