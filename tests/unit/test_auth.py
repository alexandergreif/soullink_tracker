"""Unit tests for secure Bearer token authentication system."""

import pytest
from fastapi import HTTPException, status
from uuid import uuid4

from soullink_tracker.auth.dependencies import get_current_player_from_token
from soullink_tracker.auth.security import (
    generate_secure_token, verify_bearer_token, validate_bearer_token_format
)
from soullink_tracker.db.models import Player


@pytest.mark.unit
class TestAuthSecurity:
    """Test secure Bearer token authentication functions."""

    def test_generate_secure_token(self):
        """Test generating a secure Bearer token."""
        token, token_hash = generate_secure_token()
        
        assert token is not None
        assert token_hash is not None
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) > 20  # URL-safe tokens should be reasonably long
        assert len(token_hash) == 64  # SHA256 hex digest is 64 chars

    def test_verify_bearer_token_valid(self):
        """Test verifying a valid Bearer token."""
        token, token_hash = generate_secure_token()
        
        assert verify_bearer_token(token, token_hash) is True

    def test_verify_bearer_token_invalid(self):
        """Test verifying an invalid Bearer token."""
        _, correct_hash = generate_secure_token()
        wrong_token, _ = generate_secure_token()
        
        assert verify_bearer_token(wrong_token, correct_hash) is False

    def test_verify_bearer_token_empty_inputs(self):
        """Test verifying Bearer token with empty inputs."""
        assert verify_bearer_token("", "hash") is False
        assert verify_bearer_token("token", "") is False
        assert verify_bearer_token("", "") is False

    def test_validate_bearer_token_format_valid(self):
        """Test validating valid token format."""
        token, _ = generate_secure_token()
        
        # Should not raise an exception
        validate_bearer_token_format(token)

    def test_validate_bearer_token_format_empty(self):
        """Test validating empty token."""
        with pytest.raises(HTTPException) as exc_info:
            validate_bearer_token_format("")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token cannot be empty" in str(exc_info.value.detail)

    def test_validate_bearer_token_format_too_short(self):
        """Test validating token that's too short."""
        with pytest.raises(HTTPException) as exc_info:
            validate_bearer_token_format("short")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token format" in str(exc_info.value.detail)


@pytest.mark.unit
class TestAuthDependencies:
    """Test Bearer token authentication dependencies."""

    def test_get_current_player_valid_token(self, test_db):
        """Test getting current player with valid Bearer token."""
        # Create a test player with secure token
        db = test_db()
        
        token, token_hash = generate_secure_token()
        
        player = Player(
            id=uuid4(),
            run_id=uuid4(),
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        
        db.add(player)
        db.commit()
        
        # Test the dependency
        current_player = get_current_player_from_token(token, db)
        
        assert current_player.id == player.id
        assert current_player.name == "TestPlayer"

    def test_get_current_player_invalid_token_format(self, test_db):
        """Test getting current player with invalid token format."""
        db = test_db()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token("short", db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token format" in str(exc_info.value.detail)

    def test_get_current_player_wrong_token(self, test_db):
        """Test getting current player with wrong token."""
        db = test_db()
        
        # Create a player with one token
        correct_token, correct_hash = generate_secure_token()
        wrong_token, _ = generate_secure_token()
        
        player = Player(
            id=uuid4(),
            run_id=uuid4(),
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=correct_hash
        )
        
        db.add(player)
        db.commit()
        
        # Try to authenticate with wrong token
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token(wrong_token, db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in str(exc_info.value.detail)

    def test_get_current_player_no_players(self, test_db):
        """Test getting current player when no players exist."""
        db = test_db()
        
        token, _ = generate_secure_token()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token(token, db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in str(exc_info.value.detail)


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

    def test_rotate_token(self):
        """Test token rotation functionality."""
        # Create player with initial token
        initial_token, initial_hash = Player.generate_token()
        
        player = Player(
            name="Test",
            game="HeartGold",
            region="EU",
            token_hash=initial_hash
        )
        
        # Verify initial token works
        assert player.verify_token(initial_token) is True
        
        # Rotate token
        new_token = player.rotate_token()
        
        # Verify old token no longer works
        assert player.verify_token(initial_token) is False
        
        # Verify new token works
        assert player.verify_token(new_token) is True
        assert isinstance(new_token, str)
        assert len(new_token) > 20

    def test_token_hash_consistency(self):
        """Test that the same token produces the same hash."""
        token, token_hash1 = Player.generate_token()
        
        # Manually hash the same token
        import hashlib
        token_hash2 = hashlib.sha256(token.encode()).hexdigest()
        
        assert token_hash1 == token_hash2


@pytest.mark.unit  
class TestSecureTokenSystemIntegration:
    """Integration tests for the complete secure token system."""
    
    def test_full_token_lifecycle(self, test_db):
        """Test complete token lifecycle: create, use, rotate, use new."""
        db = test_db()
        
        # Create player
        token, token_hash = Player.generate_token()
        player = Player(
            id=uuid4(),
            run_id=uuid4(),
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.commit()
        
        # Verify initial authentication works
        authenticated_player = get_current_player_from_token(token, db)
        assert authenticated_player.id == player.id
        
        # Rotate token
        new_token = player.rotate_token()
        db.commit()
        
        # Verify old token no longer works
        with pytest.raises(HTTPException) as exc_info:
            get_current_player_from_token(token, db)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Verify new token works
        authenticated_player = get_current_player_from_token(new_token, db)
        assert authenticated_player.id == player.id

    def test_multiple_players_with_different_tokens(self, test_db):
        """Test that multiple players can have different tokens."""
        db = test_db()
        
        # Create two players with different tokens
        token1, hash1 = Player.generate_token()
        token2, hash2 = Player.generate_token()
        
        run_id = uuid4()
        
        player1 = Player(
            id=uuid4(),
            run_id=run_id,
            name="Player1",
            game="HeartGold",
            region="EU",
            token_hash=hash1
        )
        
        player2 = Player(
            id=uuid4(),
            run_id=run_id,
            name="Player2",
            game="SoulSilver",
            region="US",
            token_hash=hash2
        )
        
        db.add(player1)
        db.add(player2)
        db.commit()
        
        # Verify each token authenticates the correct player
        auth_player1 = get_current_player_from_token(token1, db)
        auth_player2 = get_current_player_from_token(token2, db)
        
        assert auth_player1.id == player1.id
        assert auth_player1.name == "Player1"
        assert auth_player2.id == player2.id
        assert auth_player2.name == "Player2"
        
        # Verify cross-authentication: token1 should authenticate player1, not player2
        # This should work - token1 authenticates player1
        correct_player = get_current_player_from_token(token1, db)
        assert correct_player.id == player1.id
        assert correct_player.id != player2.id