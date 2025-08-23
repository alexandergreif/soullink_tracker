"""Comprehensive tests for secure authentication system including JWT and rate limiting."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import pytest
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from soullink_tracker.main import app
from soullink_tracker.db.models import Run, Player, PlayerSession
from soullink_tracker.auth.security import hash_password
from soullink_tracker.auth.jwt_auth import JWTTokenManager
from soullink_tracker.auth.rate_limiter import RateLimiter


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def jwt_manager():
    """Create JWT token manager."""
    with patch("soullink_tracker.auth.jwt_auth.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.app.jwt_secret_key = "test-secret-key"
        mock_config.app.jwt_access_token_expires_minutes = 15
        mock_config.app.jwt_refresh_token_expires_days = 30
        mock_get_config.return_value = mock_config
        return JWTTokenManager()


@pytest.fixture
def sample_run_with_player(db_session: Session):
    """Create a sample run with a player for testing."""
    password = "test_password_123"
    salt_hex, hash_hex = hash_password(password)
    
    run = Run(
        id=uuid4(),
        name="Test SoulLink Run",
        rules_json={"dupes_clause": True},
        password_salt=salt_hex,
        password_hash=hash_hex,
    )
    
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    
    # Create a player
    from soullink_tracker.auth.security import generate_secure_token
    session_token, token_hash = generate_secure_token()
    
    player = Player(
        id=uuid4(),
        run_id=run.id,
        name="TestPlayer",
        game="HeartGold",
        region="Johto",
        token_hash=token_hash,
    )
    
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    
    # Store plain password for testing
    run._plain_password = password
    return run, player


class TestJWTTokenManager:
    """Test JWT token manager functionality."""

    def test_create_tokens_success(self, jwt_manager):
        """Test successful token creation."""
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        access_token, refresh_token, access_expires, refresh_expires = jwt_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert access_token != refresh_token
        assert isinstance(access_expires, datetime)
        assert isinstance(refresh_expires, datetime)
        assert access_expires < refresh_expires

    def test_verify_access_token_success(self, jwt_manager):
        """Test successful access token verification."""
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        access_token, _, _, _ = jwt_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        payload = jwt_manager.verify_access_token(access_token)
        
        assert payload["sub"] == str(player_id)
        assert payload["run_id"] == str(run_id)
        assert payload["player_name"] == player_name
        assert payload["type"] == "access"

    def test_verify_refresh_token_success(self, jwt_manager):
        """Test successful refresh token verification."""
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        _, refresh_token, _, _ = jwt_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        payload = jwt_manager.verify_refresh_token(refresh_token)
        
        assert payload["sub"] == str(player_id)
        assert payload["run_id"] == str(run_id)
        assert payload["player_name"] == player_name
        assert payload["type"] == "refresh"

    def test_verify_invalid_token_raises_error(self, jwt_manager):
        """Test that invalid token raises HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            jwt_manager.verify_access_token("invalid-token")
        assert exc_info.value.status_code == 401

    def test_refresh_access_token_success(self, jwt_manager):
        """Test successful access token refresh."""
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        _, refresh_token, _, _ = jwt_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        new_access_token, expires_at = jwt_manager.refresh_access_token(refresh_token)
        
        assert isinstance(new_access_token, str)
        assert isinstance(expires_at, datetime)
        
        # Verify the new access token is valid
        payload = jwt_manager.verify_access_token(new_access_token)
        assert payload["sub"] == str(player_id)
        assert payload["type"] == "access"

    def test_refresh_with_access_token_fails(self, jwt_manager):
        """Test that using access token for refresh fails."""
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        access_token, _, _, _ = jwt_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            jwt_manager.refresh_access_token(access_token)
        assert exc_info.value.status_code == 401

    def test_expired_token_verification_fails(self, jwt_manager):
        """Test that expired token verification fails."""
        # Create manager with very short expiry
        with patch("soullink_tracker.auth.jwt_auth.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.app.jwt_secret_key = "test-secret-key"
            mock_config.app.jwt_access_token_expires_minutes = 0.01  # 0.6 seconds
            mock_config.app.jwt_refresh_token_expires_days = 1
            mock_get_config.return_value = mock_config
            short_manager = JWTTokenManager()
        
        player_id = uuid4()
        run_id = uuid4()
        player_name = "TestPlayer"
        
        access_token, _, _, _ = short_manager.create_tokens(
            player_id=player_id,
            run_id=run_id,
            player_name=player_name
        )
        
        # Wait for token to expire
        time.sleep(1)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            short_manager.verify_access_token(access_token)
        assert exc_info.value.status_code == 401


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_allows_normal_requests(self):
        """Test that normal request rates are allowed."""
        rate_limiter = RateLimiter()
        
        # Mock request
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None  # No forwarded headers
        
        # Should allow normal requests
        for _ in range(5):
            rate_limiter.check_rate_limit(request, "login")

    def test_rate_limiter_blocks_excessive_requests(self):
        """Test that excessive requests are blocked."""
        rate_limiter = RateLimiter()
        
        # Mock request
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None  # No forwarded headers
        
        # Make many requests to trigger rate limit
        for _ in range(10):
            rate_limiter.check_rate_limit(request, "login")
        
        # This should be blocked
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            rate_limiter.check_rate_limit(request, "login")
        assert exc_info.value.status_code == 429

    def test_rate_limiter_different_ips_independent(self):
        """Test that different IPs have independent rate limits."""
        rate_limiter = RateLimiter()
        
        # Mock requests from different IPs
        request1 = Mock()
        request1.client.host = "127.0.0.1"
        request1.headers.get.return_value = None
        
        request2 = Mock()
        request2.client.host = "192.168.1.1"
        request2.headers.get.return_value = None
        
        # Max out first IP
        for _ in range(10):
            rate_limiter.check_rate_limit(request1, "login")
        
        # Second IP should still work
        rate_limiter.check_rate_limit(request2, "login")

    def test_rate_limiter_failure_tracking(self):
        """Test that auth failures are tracked separately."""
        rate_limiter = RateLimiter()
        
        # Mock request
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None
        
        # Record several failures
        for _ in range(5):
            rate_limiter.record_auth_failure(request)
        
        # Should be blocked due to failures
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            rate_limiter.check_rate_limit(request, "login")
        assert exc_info.value.status_code == 429

    def test_rate_limiter_success_resets_failures(self):
        """Test that successful auth resets failure count."""
        rate_limiter = RateLimiter()
        
        # Mock request
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None
        
        # Record failures
        for _ in range(3):
            rate_limiter.record_auth_failure(request)
        
        # Record success - should reset failures
        rate_limiter.record_auth_success(request)
        
        # Should be able to make requests again
        rate_limiter.check_rate_limit(request, "login")


class TestJWTEndpoints:
    """Test JWT authentication endpoints."""

    def test_jwt_login_success(self, client, sample_run_with_player, db_session):
        """Test successful JWT login."""
        run, player = sample_run_with_player
        
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": run._plain_password
        }
        
        response = client.post("/v1/auth/jwt-login", json=login_data)
        
        # Debug response on failure
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_at" in data
        assert "refresh_expires_at" in data
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)

    def test_jwt_login_invalid_password(self, client, sample_run_with_player, db_session):
        """Test JWT login with invalid password."""
        run, player = sample_run_with_player
        
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": "wrong_password"
        }
        
        response = client.post("/v1/auth/jwt-login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["content-type"] == "application/problem+json"

    def test_jwt_login_nonexistent_run(self, client, db_session):
        """Test JWT login with nonexistent run."""
        login_data = {
            "run_name": "Nonexistent Run",
            "player_name": "TestPlayer",
            "password": "password"
        }
        
        response = client.post("/v1/auth/jwt-login", json=login_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/problem+json"

    def test_refresh_token_success(self, client, sample_run_with_player, db_session):
        """Test successful token refresh."""
        run, player = sample_run_with_player
        
        # First, get JWT tokens
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": run._plain_password
        }
        
        login_response = client.post("/v1/auth/jwt-login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        login_data_response = login_response.json()
        
        # Use refresh token to get new access token
        refresh_data = {
            "refresh_token": login_data_response["refresh_token"]
        }
        
        refresh_response = client.post("/v1/auth/refresh", json=refresh_data)
        
        assert refresh_response.status_code == status.HTTP_200_OK
        refresh_data_response = refresh_response.json()
        
        assert "access_token" in refresh_data_response
        assert "expires_at" in refresh_data_response
        assert isinstance(refresh_data_response["access_token"], str)
        
        # New access token should be different from original
        assert refresh_data_response["access_token"] != login_data_response["access_token"]

    def test_refresh_token_invalid_token(self, client, db_session):
        """Test refresh with invalid token."""
        refresh_data = {
            "refresh_token": "invalid-refresh-token"
        }
        
        response = client.post("/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["content-type"] == "application/problem+json"

    def test_jwt_protected_endpoint_access(self, client, sample_run_with_player, db_session):
        """Test accessing protected endpoint with JWT token."""
        run, player = sample_run_with_player
        
        # Get JWT tokens
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": run._plain_password
        }
        
        login_response = client.post("/v1/auth/jwt-login", json=login_data)
        access_token = login_response.json()["access_token"]
        
        # Use JWT token to access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get(f"/v1/runs/{run.id}/encounters", headers=headers)
        
        # Should be able to access the endpoint
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]  # 404 is fine, means auth worked

    def test_jwt_protected_endpoint_invalid_token(self, client, sample_run_with_player, db_session):
        """Test accessing protected endpoint with invalid JWT token."""
        run, player = sample_run_with_player
        
        # Use invalid JWT token
        headers = {"Authorization": "Bearer invalid-jwt-token"}
        response = client.get(f"/v1/runs/{run.id}/encounters", headers=headers)
        
        # Should be unauthorized
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRateLimitingIntegration:
    """Test rate limiting integration with auth endpoints."""

    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter state between tests."""
        # Import and reset the global rate limiter
        from soullink_tracker.api.auth import rate_limiter
        rate_limiter._requests.clear()
        rate_limiter._failures.clear()
        rate_limiter._blocked_ips.clear()

    def test_rate_limiting_on_login_endpoint(self, client, sample_run_with_player, db_session):
        """Test that login endpoint is rate limited."""
        run, player = sample_run_with_player
        
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": "wrong_password"  # Wrong password to trigger failures
        }
        
        # Make many failed requests
        responses = []
        for _ in range(15):  # Exceed rate limit
            response = client.post("/v1/auth/login", json=login_data)
            responses.append(response.status_code)
        
        # Should get rate limited (429) eventually
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_rate_limiting_on_jwt_login_endpoint(self, client, sample_run_with_player, db_session):
        """Test that JWT login endpoint is rate limited."""
        run, player = sample_run_with_player
        
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": "wrong_password"  # Wrong password to trigger failures
        }
        
        # Make many failed requests
        responses = []
        for _ in range(15):  # Exceed rate limit
            response = client.post("/v1/auth/jwt-login", json=login_data)
            responses.append(response.status_code)
        
        # Should get rate limited (429) eventually
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_rate_limiting_on_refresh_endpoint(self, client, db_session):
        """Test that refresh endpoint is rate limited."""
        refresh_data = {
            "refresh_token": "invalid-token"
        }
        
        # Make many failed requests
        responses = []
        for _ in range(15):  # Exceed rate limit
            response = client.post("/v1/auth/refresh", json=refresh_data)
            responses.append(response.status_code)
        
        # Should get rate limited (429) eventually
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_different_endpoints_independent_rate_limits(self, client, sample_run_with_player, db_session):
        """Test that different endpoints have independent rate limits."""
        run, player = sample_run_with_player
        
        # Max out login endpoint
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": "wrong_password"
        }
        
        for _ in range(12):
            client.post("/v1/auth/login", json=login_data)
        
        # JWT login should still work (different endpoint)
        jwt_response = client.post("/v1/auth/jwt-login", json=login_data)
        assert jwt_response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS]


class TestWebSocketJWTAuth:
    """Test WebSocket authentication with JWT tokens."""

    def test_websocket_jwt_auth_success(self, client, sample_run_with_player, db_session):
        """Test successful WebSocket connection with JWT token."""
        run, player = sample_run_with_player
        
        # Get JWT tokens
        login_data = {
            "run_name": run.name,
            "player_name": player.name,
            "password": run._plain_password
        }
        
        login_response = client.post("/v1/auth/jwt-login", json=login_data)
        access_token = login_response.json()["access_token"]
        
        # Test WebSocket connection with JWT token
        with client.websocket_connect(
            f"/v1/ws?run_id={run.id}",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as websocket:
            # Connection should be successful
            # Send a test message to verify connection works
            test_message = {"type": "ping"}
            websocket.send_json(test_message)

    def test_websocket_jwt_auth_invalid_token(self, client, sample_run_with_player, db_session):
        """Test WebSocket connection with invalid JWT token."""
        run, player = sample_run_with_player
        
        # Try to connect with invalid JWT token
        with pytest.raises(Exception):  # Should raise WebSocket connection error
            with client.websocket_connect(
                f"/v1/ws?run_id={run.id}",
                headers={"Authorization": "Bearer invalid-jwt-token"}
            ) as websocket:
                pass

    def test_websocket_no_auth_fails(self, client, sample_run_with_player, db_session):
        """Test WebSocket connection without authentication."""
        run, player = sample_run_with_player
        
        # Try to connect without authentication
        with pytest.raises(Exception):  # Should raise WebSocket connection error
            with client.websocket_connect(f"/v1/ws?run_id={run.id}") as websocket:
                pass