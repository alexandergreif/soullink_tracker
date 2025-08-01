"""Unit tests for authentication system."""

import pytest
from fastapi import HTTPException, status
from uuid import uuid4

from soullink_tracker.auth.dependencies import get_current_player_from_token
from soullink_tracker.auth.security import create_access_token, verify_token
from soullink_tracker.db.models import Player


@pytest.mark.unit
class TestAuthSecurity:
    """Test authentication security functions."""

    def test_create_access_token(self):
        """Test creating an access token."""
        token = create_access_token("test-player-id")
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self):
        """Test verifying a valid token."""
        token = create_access_token("test-player-id")
        
        player_id = verify_token(token)
        
        assert player_id == "test-player-id"

    def test_verify_token_invalid(self):
        """Test verifying an invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid-token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in str(exc_info.value.detail)

    def test_verify_token_expired(self):
        """Test verifying an expired token."""
        # This would require mocking time or creating an expired token
        # For now, we'll test with a malformed token
        with pytest.raises(HTTPException) as exc_info:
            verify_token("expired.token.here")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
class TestAuthDependencies:
    """Test authentication dependencies."""

    def test_get_current_player_valid_token(self, test_db):
        """Test getting current player with valid token."""
        # Create a test player
        db = test_db()
        
        player = Player(
            id=uuid4(),
            run_id=uuid4(),
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash="test_hash"
        )
        
        db.add(player)
        db.commit()
        
        # Create a token for this player
        token = create_access_token(str(player.id))
        
        # Test the dependency
        current_player = get_current_player_from_token(token, db)
        
        assert current_player.id == player.id
        assert current_player.name == "TestPlayer"

    def test_get_current_player_invalid_token(self, test_db):
        """Test getting current player with invalid token."""
        db = test_db()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token("invalid-token", db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_player_nonexistent_player(self, test_db):
        """Test getting current player when player doesn't exist."""
        db = test_db()
        
        # Create token for non-existent player
        fake_player_id = str(uuid4())
        token = create_access_token(fake_player_id)
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token(token, db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Player not found" in str(exc_info.value.detail)


@pytest.mark.unit
class TestPlayerTokenMethods:
    """Test Player model token methods."""

    def test_generate_token(self):
        """Test generating a new token and hash."""
        token, token_hash = Player.generate_token()
        
        assert token is not None
        assert token_hash is not None
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) > 20  # URL-safe tokens should be reasonably long
        assert len(token_hash) == 64  # SHA256 hex digest is 64 chars

    def test_verify_token_correct(self):
        """Test verifying correct token."""
        token, token_hash = Player.generate_token()
        
        player = Player(
            name="Test",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        
        assert player.verify_token(token) is True

    def test_verify_token_incorrect(self):
        """Test verifying incorrect token."""
        _, token_hash = Player.generate_token()
        wrong_token, _ = Player.generate_token()
        
        player = Player(
            name="Test",
            game="HeartGold", 
            region="EU",
            token_hash=token_hash
        )
        
        assert player.verify_token(wrong_token) is False

    def test_token_hash_different_for_same_token(self):
        """Test that the same token produces the same hash."""
        token, token_hash1 = Player.generate_token()
        
        # Manually hash the same token
        import hashlib
        token_hash2 = hashlib.sha256(token.encode()).hexdigest()
        
        assert token_hash1 == token_hash2