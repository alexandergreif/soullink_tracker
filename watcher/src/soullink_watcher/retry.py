"""Retry policy implementation with exponential backoff and jitter."""

import random
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional


def compute_backoff(
    attempt: int, 
    base: float, 
    max_delay: float, 
    jitter_ratio: float
) -> float:
    """
    Compute exponential backoff delay with jitter.
    
    Args:
        attempt: Attempt number (0-based)
        base: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter_ratio: Jitter ratio (0.0 to 1.0)
    
    Returns:
        Delay in seconds (minimum 0.1s)
    """
    # Exponential backoff: base * 2^attempt
    delay = min(max_delay, base * (2 ** attempt))
    
    # Add jitter: ±jitter_ratio of the delay
    jitter = random.uniform(-jitter_ratio, jitter_ratio) * delay
    
    # Ensure minimum delay
    return max(0.1, delay + jitter)


def parse_retry_after(value: str, now: datetime) -> Optional[datetime]:
    """
    Parse HTTP Retry-After header value.
    
    Args:
        value: Retry-After header value (seconds or HTTP-date)
        now: Current datetime (used for delta calculations)
    
    Returns:
        Datetime when retry should be attempted, or None if invalid
    """
    if not value:
        return None
    
    value = value.strip()
    
    # Try parsing as seconds (integer)
    try:
        seconds = int(value)
        if seconds >= 0:
            return now + timedelta(seconds=seconds)
    except ValueError:
        pass
    
    # Try parsing as HTTP-date
    try:
        # parsedate_to_datetime returns naive datetime in local timezone
        # We need to convert to UTC for consistency
        retry_time = parsedate_to_datetime(value)
        
        # If the parsed time is naive, assume UTC
        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=timezone.utc)
        
        # Convert to UTC if not already
        if retry_time.tzinfo != timezone.utc:
            retry_time = retry_time.astimezone(timezone.utc)
        
        # Only return if it's a reasonable future time (not past, not too far future)
        if now <= retry_time <= now + timedelta(hours=24):
            return retry_time
            
    except (ValueError, TypeError, OverflowError):
        pass
    
    return None