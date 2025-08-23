"""Tests for circuit breaker implementation."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import time

from watcher.src.soullink_watcher.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerHTTPClient
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_success_in_closed_state(self):
        """Test successful calls in CLOSED state."""
        cb = CircuitBreaker()
        mock_func = Mock(return_value="success")
        
        result = cb.call(mock_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        mock_func.assert_called_once()

    def test_failure_in_closed_state(self):
        """Test failure handling in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(side_effect=Exception("test error"))
        
        # First two failures should keep circuit closed
        for i in range(2):
            with pytest.raises(Exception, match="test error"):
                cb.call(mock_func)
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == i + 1
        
        # Third failure should open circuit
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_circuit_open_fails_fast(self):
        """Test that OPEN circuit fails fast without calling function."""
        cb = CircuitBreaker(failure_threshold=1)
        mock_func = Mock(side_effect=Exception("test error"))
        
        # Trigger circuit opening
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        assert cb.state == CircuitState.OPEN
        
        # Next call should fail fast
        mock_func.reset_mock()
        with pytest.raises(CircuitOpenError, match="Circuit breaker is open"):
            cb.call(mock_func)
        mock_func.assert_not_called()

    def test_transition_to_half_open(self):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1)
        mock_func = Mock(side_effect=Exception("test error"))
        
        # Open the circuit
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout (simulate time passage)
        with patch('watcher.src.soullink_watcher.circuit_breaker.datetime') as mock_datetime:
            # Set initial time
            initial_time = datetime.now(timezone.utc)
            mock_datetime.now.return_value = initial_time
            cb._update_state(initial_time)
            assert cb.state == CircuitState.OPEN
            
            # Advance time past timeout
            future_time = initial_time + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            cb._update_state(future_time)
            assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """Test that successes in HALF_OPEN close the circuit."""
        cb = CircuitBreaker(failure_threshold=1, success_threshold=2)
        
        # Manually set to half-open state
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        
        mock_func = Mock(return_value="success")
        
        # First success
        result = cb.call(mock_func)
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.success_count == 1
        
        # Second success should close circuit
        result = cb.call(mock_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.success_count == 0
        assert cb.failure_count == 0

    def test_half_open_failure_opens_circuit(self):
        """Test that failure in HALF_OPEN opens the circuit."""
        cb = CircuitBreaker()
        
        # Manually set to half-open state
        cb.state = CircuitState.HALF_OPEN
        mock_func = Mock(side_effect=Exception("test error"))
        
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count > 0

    def test_reset_circuit_breaker(self):
        """Test manual reset of circuit breaker."""
        cb = CircuitBreaker(failure_threshold=1)
        mock_func = Mock(side_effect=Exception("test error"))
        
        # Open the circuit
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        assert cb.state == CircuitState.OPEN
        
        # Reset the circuit
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_force_open_circuit_breaker(self):
        """Test manually forcing circuit breaker open."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        
        cb.force_open()
        assert cb.state == CircuitState.OPEN

    def test_get_stats(self):
        """Test getting circuit breaker statistics."""
        cb = CircuitBreaker(failure_threshold=5, success_threshold=3)
        cb.failure_count = 2
        
        stats = cb.get_stats()
        
        assert stats['state'] == 'closed'
        assert stats['failure_count'] == 2
        assert stats['success_count'] == 0
        assert stats['failure_threshold'] == 5
        assert stats['success_threshold'] == 3
        assert 'last_failure_time' in stats
        assert 'last_request_time' in stats

    def test_failure_count_reset_after_timeout(self):
        """Test that failure count resets after reset timeout."""
        cb = CircuitBreaker(failure_threshold=5, reset_timeout_seconds=1)
        
        # Record a failure
        mock_func = Mock(side_effect=Exception("test error"))
        with pytest.raises(Exception, match="test error"):
            cb.call(mock_func)
        assert cb.failure_count == 1
        
        # Simulate time passage
        with patch('watcher.src.soullink_watcher.circuit_breaker.datetime') as mock_datetime:
            initial_time = datetime.now(timezone.utc)
            cb.last_failure_time = initial_time
            
            # Advance time past reset timeout
            future_time = initial_time + timedelta(seconds=2)
            cb._update_state(future_time)
            
            assert cb.failure_count == 0


class TestCircuitBreakerHTTPClient:
    """Test circuit breaker HTTP client wrapper."""

    def test_successful_request(self):
        """Test successful HTTP request through circuit breaker."""
        mock_client = Mock()
        mock_response = Mock()
        mock_client.request.return_value = mock_response
        
        cb_client = CircuitBreakerHTTPClient(mock_client)
        
        result = cb_client.request('GET', 'http://example.com')
        
        assert result == mock_response
        mock_client.request.assert_called_once_with('GET', 'http://example.com')

    def test_failed_request_opens_circuit(self):
        """Test that failed requests open circuit breaker."""
        mock_client = Mock()
        mock_client.request.side_effect = Exception("Connection error")
        
        cb_client = CircuitBreakerHTTPClient(mock_client, failure_threshold=2)
        
        # First failure
        with pytest.raises(Exception, match="Connection error"):
            cb_client.request('GET', 'http://example.com')
        
        stats = cb_client.get_stats()
        assert stats['failure_count'] == 1
        assert stats['state'] == 'closed'
        
        # Second failure should open circuit
        with pytest.raises(Exception, match="Connection error"):
            cb_client.request('GET', 'http://example.com')
        
        stats = cb_client.get_stats()
        assert stats['failure_count'] == 2
        assert stats['state'] == 'open'

    def test_open_circuit_fails_fast(self):
        """Test that open circuit fails fast without calling client."""
        mock_client = Mock()
        cb_client = CircuitBreakerHTTPClient(mock_client, failure_threshold=1)
        
        # Force circuit open
        cb_client.force_open()
        
        with pytest.raises(CircuitOpenError):
            cb_client.request('GET', 'http://example.com')
        
        mock_client.request.assert_not_called()

    def test_reset_and_force_open(self):
        """Test reset and force open functionality."""
        mock_client = Mock()
        cb_client = CircuitBreakerHTTPClient(mock_client)
        
        # Force open
        cb_client.force_open()
        assert cb_client.get_stats()['state'] == 'open'
        
        # Reset
        cb_client.reset()
        assert cb_client.get_stats()['state'] == 'closed'


@pytest.fixture
def mock_datetime():
    """Fixture for mocking datetime."""
    with patch('watcher.src.soullink_watcher.circuit_breaker.datetime') as mock:
        mock.now.return_value = datetime.now(timezone.utc)
        yield mock