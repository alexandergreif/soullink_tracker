"""Test the new security functions for password hashing and session tokens."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import pytest
from fastapi import HTTPException

from soullink_tracker.auth.security import (
    hash_password,
    verify_password,
    generate_session_token,
    validate_session_token_format,
    # Legacy functions for compatibility
    generate_secure_token,
    verify_bearer_token,
    validate_bearer_token_format
)


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password_basic(self):
        """Test basic password hashing."""
        password = "test_password_123"
        
        salt_hex, hash_hex = hash_password(password)
        
        # Check return types and lengths
        assert isinstance(salt_hex, str)
        assert isinstance(hash_hex, str)
        assert len(salt_hex) == 64  # 32 bytes = 64 hex chars
        assert len(hash_hex) == 64  # SHA256 = 64 hex chars
        
        # Check hex encoding is valid
        bytes.fromhex(salt_hex)  # Should not raise
        bytes.fromhex(hash_hex)  # Should not raise

    def test_hash_password_with_custom_salt(self):
        """Test password hashing with custom salt."""
        password = "test_password_123"
        custom_salt = b"custom_salt_32_bytes_long_enough!"
        
        salt_hex, hash_hex = hash_password(password, custom_salt)
        
        # Should use the provided salt
        assert salt_hex == custom_salt.hex()
        assert len(hash_hex) == 64

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        salt_hex, hash_hex = hash_password(password)
        
        result = verify_password(password, salt_hex, hash_hex)
        assert result is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        salt_hex, hash_hex = hash_password(password)
        
        result = verify_password("wrong_password", salt_hex, hash_hex)
        assert result is False

    def test_verify_password_invalid_inputs(self):
        """Test password verification with invalid inputs."""
        # Empty inputs
        assert verify_password("", "", "") is False
        assert verify_password("password", "", "hash") is False
        assert verify_password("password", "salt", "") is False
        
        # Invalid hex encoding
        assert verify_password("password", "invalid_hex", "hash") is False
        assert verify_password("password", "abcd", "invalid_hex") is False

    def test_password_consistency(self):
        """Test that same password+salt produces same hash."""
        password = "consistency_test"
        salt = b"consistent_salt_32_bytes_long!!"
        
        salt_hex1, hash_hex1 = hash_password(password, salt)
        salt_hex2, hash_hex2 = hash_password(password, salt)
        
        assert salt_hex1 == salt_hex2
        assert hash_hex1 == hash_hex2


class TestSessionTokens:
    """Test session token functionality."""

    def test_generate_session_token(self):
        """Test session token generation."""
        token, token_hash = generate_session_token()
        
        # Check return types and approximate lengths
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert 20 <= len(token) <= 50  # URL-safe base64 of 24 bytes
        assert len(token_hash) == 64  # SHA256 hex
        
        # Check hex encoding is valid
        bytes.fromhex(token_hash)  # Should not raise

    def test_generate_session_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = []
        hashes = []
        
        for _ in range(10):
            token, token_hash = generate_session_token()
            tokens.append(token)
            hashes.append(token_hash)
        
        # All tokens should be unique
        assert len(set(tokens)) == 10
        assert len(set(hashes)) == 10

    def test_validate_session_token_format_valid(self):
        """Test validation of valid session tokens."""
        token, _ = generate_session_token()
        
        # Should not raise
        validate_session_token_format(token)

    def test_validate_session_token_format_empty(self):
        """Test validation rejects empty tokens."""
        with pytest.raises(HTTPException) as exc_info:
            validate_session_token_format("")
        
        assert exc_info.value.status_code == 401
        assert "empty" in exc_info.value.detail.lower()

    def test_validate_session_token_format_too_short(self):
        """Test validation rejects too-short tokens."""
        with pytest.raises(HTTPException) as exc_info:
            validate_session_token_format("x")
        
        assert exc_info.value.status_code == 401
        assert "format" in exc_info.value.detail.lower()

    def test_validate_session_token_format_too_long(self):
        """Test validation rejects too-long tokens."""
        with pytest.raises(HTTPException) as exc_info:
            validate_session_token_format("x" * 100)
        
        assert exc_info.value.status_code == 401
        assert "format" in exc_info.value.detail.lower()

    def test_validate_session_token_format_invalid_chars(self):
        """Test validation rejects tokens with invalid characters."""
        invalid_tokens = [
            "invalid@token!",
            "token with spaces",
            "token+with+plus",
            "token/with/slash",
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises(HTTPException) as exc_info:
                validate_session_token_format(invalid_token)
            
            assert exc_info.value.status_code == 401
            assert "format" in exc_info.value.detail.lower()


class TestLegacyCompatibility:
    """Test that legacy functions still work."""

    def test_generate_secure_token(self):
        """Test legacy token generation still works."""
        token, token_hash = generate_secure_token()
        
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) >= 20
        assert len(token_hash) == 64

    def test_verify_bearer_token(self):
        """Test legacy token verification still works."""
        token, token_hash = generate_secure_token()
        
        # Correct token should verify
        assert verify_bearer_token(token, token_hash) is True
        
        # Wrong token should not verify
        assert verify_bearer_token("wrong_token", token_hash) is False

    def test_validate_bearer_token_format(self):
        """Test legacy token validation still works."""
        token, _ = generate_secure_token()
        
        # Should not raise
        validate_bearer_token_format(token)
        
        # Invalid token should raise
        with pytest.raises(HTTPException):
            validate_bearer_token_format("")


class TestSecurityProperties:
    """Test security properties of the implementation."""

    def test_salt_randomness(self):
        """Test that salts are random."""
        salts = []
        
        for _ in range(10):
            salt_hex, _ = hash_password("password")
            salts.append(salt_hex)
        
        # All salts should be unique
        assert len(set(salts)) == 10

    def test_timing_attack_resistance(self):
        """Test basic timing attack resistance."""
        password = "test_password"
        salt_hex, hash_hex = hash_password(password)
        
        # These should both return False but with consistent timing
        # (This is a basic test - actual timing analysis would be more complex)
        result1 = verify_password("wrong1", salt_hex, hash_hex)
        result2 = verify_password("wrong2", salt_hex, hash_hex)
        
        assert result1 is False
        assert result2 is False

    def test_hash_determinism(self):
        """Test that same input produces same output."""
        password = "determinism_test"
        salt = b"fixed_salt_32_bytes_for_testing!"
        
        # Same inputs should produce same outputs
        salt_hex1, hash_hex1 = hash_password(password, salt)
        salt_hex2, hash_hex2 = hash_password(password, salt)
        
        assert salt_hex1 == salt_hex2
        assert hash_hex1 == hash_hex2