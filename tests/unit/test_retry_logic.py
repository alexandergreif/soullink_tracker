"""Tests for retry logic and exponential backoff."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import json

from watcher.src.soullink_watcher.retry import compute_backoff, parse_retry_after
from watcher.src.soullink_watcher.http_client import EventSender, EventSendResult
from watcher.src.soullink_watcher.spool import SpoolRecord
from watcher.src.soullink_watcher.config import WatcherConfig


class TestComputeBackoff:
    """Test exponential backoff computation."""

    def test_first_attempt_base_delay(self):
        """Test that first attempt uses base delay."""
        delay = compute_backoff(attempt=0, base=1.0, max_delay=60.0, jitter_ratio=0.0)
        assert delay == 1.0

    def test_exponential_growth(self):
        """Test exponential growth of delay."""
        base = 2.0
        delays = []
        for attempt in range(5):
            delay = compute_backoff(attempt=attempt, base=base, max_delay=100.0, jitter_ratio=0.0)
            delays.append(delay)
        
        # Should be 2, 4, 8, 16, 32
        expected = [2.0, 4.0, 8.0, 16.0, 32.0]
        assert delays == expected

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        delay = compute_backoff(attempt=10, base=1.0, max_delay=5.0, jitter_ratio=0.0)
        assert delay == 5.0

    def test_minimum_delay(self):
        """Test that delay has minimum value."""
        # Even with negative jitter, delay should be at least 0.1s
        delay = compute_backoff(attempt=0, base=0.05, max_delay=60.0, jitter_ratio=1.0)
        assert delay >= 0.1

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delay."""
        delays = []
        for _ in range(10):
            delay = compute_backoff(attempt=2, base=1.0, max_delay=60.0, jitter_ratio=0.5)
            delays.append(delay)
        
        # With jitter, delays should be different
        assert len(set(delays)) > 1  # Should have different values
        
        # All delays should be within reasonable bounds (4 ± 2 for jitter_ratio=0.5)
        for delay in delays:
            assert 2.0 <= delay <= 6.0

    def test_zero_jitter_consistent(self):
        """Test that zero jitter produces consistent results."""
        delays = []
        for _ in range(5):
            delay = compute_backoff(attempt=3, base=1.0, max_delay=60.0, jitter_ratio=0.0)
            delays.append(delay)
        
        # Without jitter, all delays should be identical
        assert all(delay == delays[0] for delay in delays)


class TestParseRetryAfter:
    """Test parsing of HTTP Retry-After header."""

    def test_parse_seconds_format(self):
        """Test parsing Retry-After header in seconds format."""
        now = datetime.now(timezone.utc)
        result = parse_retry_after("30", now)
        
        expected = now + timedelta(seconds=30)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_negative_seconds_returns_none(self):
        """Test that negative seconds returns None."""
        now = datetime.now(timezone.utc)
        result = parse_retry_after("-10", now)
        assert result is None

    def test_parse_http_date_format(self):
        """Test parsing Retry-After header in HTTP-date format."""
        now = datetime.now(timezone.utc)
        # Format: Thu, 01 Dec 1994 16:00:00 GMT
        retry_date = now + timedelta(minutes=5)
        http_date = retry_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        result = parse_retry_after(http_date, now)
        
        # Should be close to the expected time (within a few seconds)
        assert abs((result - retry_date).total_seconds()) < 5

    def test_parse_invalid_format_returns_none(self):
        """Test that invalid format returns None."""
        now = datetime.now(timezone.utc)
        result = parse_retry_after("invalid-format", now)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        """Test that empty string returns None."""
        now = datetime.now(timezone.utc)
        result = parse_retry_after("", now)
        assert result is None

    def test_parse_future_date_too_far_returns_none(self):
        """Test that date too far in future returns None."""
        now = datetime.now(timezone.utc)
        far_future = now + timedelta(days=2)
        http_date = far_future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        result = parse_retry_after(http_date, now)
        assert result is None


class TestEventSenderRetry:
    """Test EventSender retry behavior integration."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return WatcherConfig(
            base_url="http://test-api.com",
            token="test-token",
            run_id="test-run-id",
            player_id="test-player-id",
            spool_dir="/tmp/test-spool"
        )

    @pytest.fixture
    def sample_record(self):
        """Sample spool record for testing."""
        return SpoolRecord(
            record_id="test-record-id",
            created_at=datetime.now(timezone.utc).isoformat(),
            next_attempt_at=datetime.now(timezone.utc).isoformat(),
            attempt=0,
            idempotency_key="test-idempotency-key",
            base_url="http://test-api.com",
            request_json={"type": "encounter", "test": "data"},
            run_id="test-run-id",
            player_id="test-player-id"
        )

    def test_successful_send_no_retry_needed(self, config, sample_record):
        """Test successful send without retry."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.headers = {}
            mock_response.json.return_value = {"status": "accepted"}
            mock_request.return_value = mock_response
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is True
            assert result.status_code == 202
            assert result.retriable is False
            mock_request.assert_called_once()

    def test_server_error_is_retriable(self, config, sample_record):
        """Test that server errors are marked as retriable."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            # Mock server error response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.headers = {}
            mock_response.json.return_value = {"error": "Internal server error"}
            mock_request.return_value = mock_response
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is False
            assert result.status_code == 500
            assert result.retriable is True

    def test_client_error_not_retriable(self, config, sample_record):
        """Test that client errors are not retriable."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            # Mock client error response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.headers = {}
            mock_response.json.return_value = {"error": "Bad request"}
            mock_request.return_value = mock_response
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is False
            assert result.status_code == 400
            assert result.retriable is False

    def test_rate_limit_is_retriable_with_retry_after(self, config, sample_record):
        """Test that rate limiting is retriable with Retry-After header."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            # Mock rate limit response with Retry-After header
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {'retry-after': '60'}
            mock_response.json.return_value = {"error": "Rate limit exceeded"}
            mock_request.return_value = mock_response
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is False
            assert result.status_code == 429
            assert result.retriable is True
            assert result.retry_after is not None

    def test_timeout_is_retriable(self, config, sample_record):
        """Test that timeouts are retriable."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is False
            assert result.status_code is None
            assert result.retriable is True
            assert "timeout" in result.message.lower()

    def test_connection_error_is_retriable(self, config, sample_record):
        """Test that connection errors are retriable."""
        sender = EventSender()
        
        with patch.object(sender.session, 'request') as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            result = sender.send_event(config, sample_record)
            
            assert result.success is False
            assert result.status_code is None
            assert result.retriable is True
            assert "connection error" in result.message.lower()

    def test_request_too_large_not_retriable(self, config):
        """Test that oversized requests are not retriable."""
        sender = EventSender()
        
        # Create a record with very large JSON payload
        large_payload = {"data": "x" * (20 * 1024)}  # 20KB payload
        large_record = SpoolRecord(
            record_id="large-record",
            created_at=datetime.now(timezone.utc).isoformat(),
            next_attempt_at=datetime.now(timezone.utc).isoformat(),
            attempt=0,
            idempotency_key="large-key",
            base_url="http://test-api.com",
            request_json=large_payload,
            run_id="test-run-id",
            player_id="test-player-id"
        )
        
        result = sender.send_event(config, large_record)
        
        assert result.success is False
        assert result.status_code == 413
        assert result.retriable is False
        assert "too large" in result.message.lower()

    def test_circuit_breaker_integration(self, config, sample_record):
        """Test circuit breaker integration with event sender."""
        sender = EventSender(circuit_breaker_enabled=True)
        
        with patch.object(sender.session, 'request') as mock_request:
            # Mock failures to trigger circuit breaker
            mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            # First few failures should go through
            for i in range(5):
                result = sender.send_event(config, sample_record)
                assert result.retriable is True
                assert "connection error" in result.message.lower()
            
            # After threshold, circuit breaker should be open
            result = sender.send_event(config, sample_record)
            assert result.retriable is True
            assert "circuit breaker" in result.message.lower()

    def test_circuit_breaker_disabled(self, config, sample_record):
        """Test that circuit breaker can be disabled."""
        sender = EventSender(circuit_breaker_enabled=False)
        assert sender.circuit_breaker is None
        
        with patch.object(sender.session, 'request') as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            # Should still work normally without circuit breaker
            result = sender.send_event(config, sample_record)
            assert result.retriable is True
            assert "connection error" in result.message.lower()
            assert "circuit breaker" not in result.message.lower()


# Import requests for exceptions
import requests