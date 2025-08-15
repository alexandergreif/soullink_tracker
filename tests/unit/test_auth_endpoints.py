"""Test authentication endpoints."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from soullink_tracker.main import app
from soullink_tracker.db.models import Run, Player, PlayerSession
from soullink_tracker.auth.security import hash_password, generate_session_token


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_run_with_password(db_session: Session):
    """Create a sample run with password authentication."""
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
    
    # Return run with plain password for testing
    run._plain_password = password  # Store for test access
    return run


@pytest.fixture
def sample_run_without_password(db_session: Session):
    """Create a sample run without password authentication."""
    run = Run(
        id=uuid4(),
        name="No Password Run",
        rules_json={"dupes_clause": False},
        # No password fields set
    )
    
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    
    return run


@pytest.fixture
def sample_players(db_session: Session, sample_run_with_password: Run):
    """Create sample players for the test run."""
    players = []
    
    for i, name in enumerate(["Alice", "Bob", "Charlie"]):
        token, token_hash = generate_session_token()
        
        player = Player(
            id=uuid4(),
            run_id=sample_run_with_password.id,
            name=name,
            game="HeartGold" if i % 2 == 0 else "SoulSilver",
            region="EU",
            token_hash=token_hash,
        )
        
        db_session.add(player)
        players.append(player)
    
    db_session.commit()
    for player in players:
        db_session.refresh(player)
    
    return players


class TestLoginEndpoint:
    """Test the /v1/auth/login endpoint."""

    def test_login_success_with_run_id(self, client, sample_run_with_password, sample_players):
        """Test successful login using run_id."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "session_token" in data
        assert data["run_id"] == str(sample_run_with_password.id)
        assert data["player_id"] == str(player.id)
        assert "expires_at" in data
        
        # Verify token format
        assert len(data["session_token"]) >= 20
        assert len(data["session_token"]) <= 50

    def test_login_success_with_run_name(self, client, sample_run_with_password, sample_players):
        """Test successful login using run_name."""
        player = sample_players[1]
        
        response = client.post("/v1/auth/login", json={
            "run_name": sample_run_with_password.name,
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["run_id"] == str(sample_run_with_password.id)
        assert data["player_id"] == str(player.id)

    def test_login_case_insensitive_player_name(self, client, sample_run_with_password, sample_players):
        """Test that player name matching is case-insensitive."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": player.name.upper(),  # Use uppercase
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["player_id"] == str(player.id)

    def test_login_case_insensitive_run_name(self, client, sample_run_with_password, sample_players):
        """Test that run name matching is case-insensitive."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_name": sample_run_with_password.name.upper(),  # Use uppercase
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_200_OK

    def test_login_invalid_password(self, client, sample_run_with_password, sample_players):
        """Test login with invalid password."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": player.name,
            "password": "wrong_password",
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid password" in response.json()["detail"].lower()

    def test_login_run_not_found_by_id(self, client, sample_players):
        """Test login with non-existent run_id."""
        player = sample_players[0]
        fake_run_id = uuid4()
        
        response = client.post("/v1/auth/login", json={
            "run_id": str(fake_run_id),
            "player_name": player.name,
            "password": "any_password",
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "run not found" in response.json()["detail"].lower()

    def test_login_run_not_found_by_name(self, client, sample_players):
        """Test login with non-existent run_name."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_name": "Non-existent Run",
            "player_name": player.name,
            "password": "any_password",
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "run not found" in response.json()["detail"].lower()

    def test_login_player_not_found(self, client, sample_run_with_password):
        """Test login with non-existent player."""
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": "NonExistentPlayer",
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "player not found" in response.json()["detail"].lower()

    def test_login_run_without_password(self, client, sample_run_without_password):
        """Test login attempt on run without password authentication."""
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_without_password.id),
            "player_name": "AnyPlayer",
            "password": "any_password",
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "password authentication" in response.json()["detail"].lower()

    def test_login_missing_run_identifier(self, client, sample_players):
        """Test login without run_id or run_name."""
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "player_name": player.name,
            "password": "any_password",
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_multiple_runs_same_name(self, client, db_session, sample_run_with_password, sample_players):
        """Test login with multiple runs having same name."""
        # Create another run with same name
        password2 = "different_password"
        salt_hex2, hash_hex2 = hash_password(password2)
        
        duplicate_run = Run(
            id=uuid4(),
            name=sample_run_with_password.name,  # Same name!
            rules_json={},
            password_salt=salt_hex2,
            password_hash=hash_hex2,
        )
        
        db_session.add(duplicate_run)
        db_session.commit()
        
        player = sample_players[0]
        
        response = client.post("/v1/auth/login", json={
            "run_name": sample_run_with_password.name,
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "multiple runs" in response.json()["detail"].lower()

    def test_login_validation_errors(self, client):
        """Test various validation errors."""
        # Empty player name
        response = client.post("/v1/auth/login", json={
            "run_id": str(uuid4()),
            "player_name": "",
            "password": "password",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Empty password
        response = client.post("/v1/auth/login", json={
            "run_id": str(uuid4()),
            "player_name": "Player",
            "password": "",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid UUID format
        response = client.post("/v1/auth/login", json={
            "run_id": "not-a-uuid",
            "player_name": "Player",
            "password": "password",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_creates_session_record(self, client, db_session, sample_run_with_password, sample_players):
        """Test that login creates a session record in database."""
        player = sample_players[0]
        
        # Count existing sessions
        initial_count = db_session.query(PlayerSession).count()
        
        response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify session was created
        final_count = db_session.query(PlayerSession).count()
        assert final_count == initial_count + 1
        
        # Find the created session
        session = db_session.query(PlayerSession).filter(
            PlayerSession.player_id == player.id
        ).first()
        
        assert session is not None
        assert session.run_id == sample_run_with_password.id
        assert session.expires_at > datetime.now(timezone.utc)


class TestLogoutEndpoint:
    """Test the /v1/auth/logout endpoint."""

    def test_logout_success(self, client, db_session, sample_players):
        """Test successful logout."""
        player = sample_players[0]
        
        # Create a session for the player
        session_token, token_hash = generate_session_token()
        session = PlayerSession(
            token_hash=token_hash,
            run_id=player.run_id,
            player_id=player.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        
        db_session.add(session)
        db_session.commit()
        
        # Logout
        response = client.post("/v1/auth/logout", headers={
            "Authorization": f"Bearer {session_token}"
        })
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        
        # Verify session was deleted
        remaining_session = db_session.query(PlayerSession).filter(
            PlayerSession.id == session.id
        ).first()
        assert remaining_session is None

    def test_logout_invalid_token(self, client):
        """Test logout with invalid token."""
        response = client.post("/v1/auth/logout", headers={
            "Authorization": "Bearer invalid_token_format"
        })
        
        # Should still return 204 to avoid leaking token validity info
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_missing_authorization_header(self, client):
        """Test logout without Authorization header."""
        response = client.post("/v1/auth/logout")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "authorization header" in response.json()["detail"].lower()

    def test_logout_malformed_authorization_header(self, client):
        """Test logout with malformed Authorization header."""
        # Missing "Bearer " prefix
        response = client.post("/v1/auth/logout", headers={
            "Authorization": "invalid_format_token"
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Empty after "Bearer "
        response = client.post("/v1/auth/logout", headers={
            "Authorization": "Bearer "
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_nonexistent_session(self, client):
        """Test logout with token that has no corresponding session."""
        # Generate a valid format token that doesn't exist in database
        fake_token, _ = generate_session_token()
        
        response = client.post("/v1/auth/logout", headers={
            "Authorization": f"Bearer {fake_token}"
        })
        
        # Should still return 204 to avoid leaking session existence
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_expired_session(self, client, db_session, sample_players):
        """Test logout with expired session."""
        player = sample_players[0]
        
        # Create an expired session
        session_token, token_hash = generate_session_token()
        session = PlayerSession(
            token_hash=token_hash,
            run_id=player.run_id,
            player_id=player.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
        )
        
        db_session.add(session)
        db_session.commit()
        
        # Logout should still work (cleanup expired sessions)
        response = client.post("/v1/auth/logout", headers={
            "Authorization": f"Bearer {session_token}"
        })
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify session was deleted
        remaining_session = db_session.query(PlayerSession).filter(
            PlayerSession.id == session.id
        ).first()
        assert remaining_session is None


class TestAuthenticationFlow:
    """Test the complete authentication flow."""

    def test_login_logout_flow(self, client, db_session, sample_run_with_password, sample_players):
        """Test complete login -> logout flow."""
        player = sample_players[0]
        
        # Step 1: Login
        login_response = client.post("/v1/auth/login", json={
            "run_id": str(sample_run_with_password.id),
            "player_name": player.name,
            "password": sample_run_with_password._plain_password,
        })
        
        assert login_response.status_code == status.HTTP_200_OK
        session_token = login_response.json()["session_token"]
        
        # Verify session exists
        session_count = db_session.query(PlayerSession).filter(
            PlayerSession.player_id == player.id
        ).count()
        assert session_count == 1
        
        # Step 2: Logout
        logout_response = client.post("/v1/auth/logout", headers={
            "Authorization": f"Bearer {session_token}"
        })
        
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify session was deleted
        session_count = db_session.query(PlayerSession).filter(
            PlayerSession.player_id == player.id
        ).count()
        assert session_count == 0

    def test_multiple_sessions_per_player(self, client, sample_run_with_password, sample_players):
        """Test that players can have multiple active sessions."""
        player = sample_players[0]
        
        # Login multiple times (different browsers/devices)
        tokens = []
        for i in range(3):
            response = client.post("/v1/auth/login", json={
                "run_id": str(sample_run_with_password.id),
                "player_name": player.name,
                "password": sample_run_with_password._plain_password,
            })
            
            assert response.status_code == status.HTTP_200_OK
            tokens.append(response.json()["session_token"])
        
        # All tokens should be different
        assert len(set(tokens)) == 3
        
        # Logout with one token shouldn't affect others
        logout_response = client.post("/v1/auth/logout", headers={
            "Authorization": f"Bearer {tokens[0]}"
        })
        
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Other sessions should still exist (test by logging out)
        for token in tokens[1:]:
            logout_response = client.post("/v1/auth/logout", headers={
                "Authorization": f"Bearer {token}"
            })
            assert logout_response.status_code == status.HTTP_204_NO_CONTENT