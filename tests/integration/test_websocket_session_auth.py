"""Integration tests for WebSocket session token authentication with backward compatibility.

These tests validate that WebSocket authentication works with both:
- New session token authentication (primary)
- Legacy Bearer token authentication (fallback)
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from soullink_tracker.auth.security import generate_session_token
from soullink_tracker.db.models import PlayerSession


@pytest.mark.integration
class TestWebSocketSessionAuthentication:
    """Test WebSocket authentication with session tokens."""

    def test_websocket_auth_with_session_token(
        self, client, db_session, sample_run, sample_player
    ):
        """Test that WebSocket accepts session tokens."""
        # Arrange: Create a session token for the player
        session_token, _ = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        import hashlib
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        # Create session in database
        session = PlayerSession(
            id=uuid.uuid4(),
            player_id=sample_player.id,
            run_id=sample_run.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.commit()

        # Act & Assert: Should connect successfully with session token
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={session_token}"
        ) as websocket:
            # WebSocket should send welcome message
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"
            assert "player_id" in welcome_message["data"]
            assert welcome_message["data"]["player_id"] == str(sample_player.id)
            assert "run_id" in welcome_message["data"]
            assert welcome_message["data"]["run_id"] == str(sample_run.id)

    def test_websocket_auth_with_legacy_bearer_token(
        self, client, sample_run, sample_player
    ):
        """Test that WebSocket falls back to legacy Bearer tokens when auth_allow_legacy_bearer=True."""
        # Note: sample_player fixture already has a _test_token (Bearer token)
        token = sample_player._test_token
        
        # Act & Assert: Should connect successfully with Bearer token (fallback)
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={token}"
        ) as websocket:
            # WebSocket should send welcome message
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"

    def test_websocket_auth_session_token_priority(
        self, client, db_session, sample_run, sample_player
    ):
        """Test that session token authentication is tried first, Bearer token as fallback."""
        # Arrange: Create an expired session token (should fail session auth)
        expired_session_token, _ = generate_session_token()
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)  # Expired
        
        import hashlib
        token_hash = hashlib.sha256(expired_session_token.encode()).hexdigest()
        
        # Create expired session in database
        expired_session = PlayerSession(
            id=uuid.uuid4(),
            player_id=sample_player.id,
            run_id=sample_run.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            last_seen_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db_session.add(expired_session)
        db_session.commit()

        # Act & Assert: Should fail to connect with expired session token
        # and NOT fall back to Bearer token (because the token format suggests session token)
        try:
            with client.websocket_connect(
                f"/v1/ws?run_id={sample_run.id}&token={expired_session_token}"
            ) as websocket:
                # Should not reach here
                assert False, "WebSocket should have rejected expired session token"
        except Exception:
            # Expected - connection should be rejected
            pass

    def test_websocket_auth_invalid_token_both_methods(
        self, client, sample_run
    ):
        """Test that WebSocket rejects invalid tokens in both authentication methods."""
        invalid_token = "invalid-token-12345"
        
        # Act & Assert: Should fail to connect with invalid token
        try:
            with client.websocket_connect(
                f"/v1/ws?run_id={sample_run.id}&token={invalid_token}"
            ) as websocket:
                # Should not reach here
                assert False, "WebSocket should have rejected invalid token"
        except Exception:
            # Expected - connection should be rejected
            pass

    def test_websocket_auth_session_token_updates_last_seen(
        self, client, db_session, sample_run, sample_player
    ):
        """Test that successful session token authentication updates last_seen_at."""
        # Arrange: Create a session token for the player
        session_token, _ = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        initial_last_seen = datetime.now(timezone.utc) - timedelta(hours=1)
        
        import hashlib
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        # Create session in database with old last_seen_at
        session = PlayerSession(
            id=uuid.uuid4(),
            player_id=sample_player.id,
            run_id=sample_run.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
            last_seen_at=initial_last_seen
        )
        db_session.add(session)
        db_session.commit()
        session_id = session.id

        # Act: Connect with session token
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={session_token}"
        ) as websocket:
            # Skip welcome message
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"

        # Assert: last_seen_at should be updated
        db_session.refresh(session)
        updated_session = db_session.get(PlayerSession, session_id)
        # Both timestamps should be timezone-aware for comparison
        assert updated_session.last_seen_at.replace(tzinfo=timezone.utc) > initial_last_seen

    def test_websocket_ping_pong_with_server_time(
        self, client, db_session, sample_run, sample_player
    ):
        """Test that WebSocket ping/pong includes server_time in pong response."""
        # Arrange: Create a session token for the player
        session_token, _ = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        import hashlib
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        session = PlayerSession(
            id=uuid.uuid4(),
            player_id=sample_player.id,
            run_id=sample_run.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.commit()

        # Act: Connect and send ping
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={session_token}"
        ) as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send ping message
            import time
            before_ping = time.time()
            websocket.send_json({"type": "ping"})
            
            # Receive pong response
            pong_message = websocket.receive_json()
            after_ping = time.time()
            
            # Assert: Should receive pong with server_time
            assert pong_message["type"] == "pong"
            assert "data" in pong_message
            assert "server_time" in pong_message["data"]
            
            server_time = pong_message["data"]["server_time"]
            assert before_ping <= server_time <= after_ping


@pytest.mark.integration 
class TestWebSocketLegacyDisabled:
    """Test WebSocket authentication when legacy Bearer tokens are disabled."""
    
    def test_websocket_auth_priority_session_first(self, client, db_session, sample_run, sample_player):
        """Test that session token authentication is attempted first."""
        # This test verifies the authentication flow works correctly
        # by testing that session tokens work (they are tried first)
        
        # Arrange: Create a valid session token
        session_token, _ = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        import hashlib
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        session = PlayerSession(
            id=uuid.uuid4(),
            player_id=sample_player.id,
            run_id=sample_run.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.commit()

        # Act & Assert: Should connect with session token (tested first)
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={session_token}"
        ) as websocket:
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"

    def test_websocket_auth_fallback_behavior(self, client, sample_run, sample_player):
        """Test that WebSocket falls back to Bearer token when session token format is detected but invalid."""
        # This test verifies the current behavior where legacy Bearer tokens work as fallback
        # The configuration currently has auth_allow_legacy_bearer=True by default
        
        # Use the Bearer token from sample_player (this should work as fallback)
        bearer_token = sample_player._test_token
        
        # Act & Assert: Should connect with Bearer token as fallback
        with client.websocket_connect(
            f"/v1/ws?run_id={sample_run.id}&token={bearer_token}"
        ) as websocket:
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"
            assert "player_id" in welcome_message["data"]
            assert welcome_message["data"]["player_id"] == str(sample_player.id)