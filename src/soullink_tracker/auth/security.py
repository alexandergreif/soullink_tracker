"""Security utilities for authentication."""

import hashlib
import hmac
import secrets
from typing import Tuple, Optional

from fastapi import HTTPException, status


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Args:
        password: The plain text password to hash
        salt: Optional salt bytes. If None, generates a secure random salt.

    Returns:
        tuple[str, str]: (salt_hex, hash_hex) for storage in database
    """
    if salt is None:
        salt = secrets.token_bytes(32)  # 256-bit salt

    # Use configurable iterations (default 120,000)
    from ..config import get_config

    config = get_config()
    iterations = config.app.password_hash_iterations

    # Generate PBKDF2-HMAC-SHA256 hash
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )

    return salt.hex(), password_hash.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """
    Verify a password against stored salt and hash.

    Args:
        password: The plain text password to verify
        salt_hex: The hex-encoded salt from database
        hash_hex: The hex-encoded hash from database

    Returns:
        bool: True if password is valid, False otherwise
    """
    if not password or not salt_hex or not hash_hex:
        return False

    try:
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)

        # Use same iterations as hash_password
        from ..config import get_config

        config = get_config()
        iterations = config.app.password_hash_iterations

        # Generate hash with provided salt
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_hash, stored_hash)

    except (ValueError, TypeError):
        # Invalid hex encoding or other format errors
        return False


def generate_session_token() -> tuple[str, str]:
    """
    Generate a secure session token and its SHA-256 hash.

    Returns:
        tuple[str, str]: (token, token_hash) where token is the plain token
        and token_hash is the SHA-256 hex digest for storage.
    """
    # Generate cryptographically secure token (~32 chars URL-safe)
    token = secrets.token_urlsafe(24)  # 24 bytes -> ~32 chars

    # Create SHA-256 hash for storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    return token, token_hash


def validate_session_token_format(token: str) -> None:
    """
    Validate that a session token has the expected format.

    Args:
        token: The token to validate

    Raises:
        HTTPException: If token format is invalid (401 Unauthorized)
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token cannot be empty",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check length (token_urlsafe(24) produces ~32 character tokens)
    if len(token) < 20 or len(token) > 50:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check for URL-safe characters only (base64url alphabet)
    import string

    valid_chars = string.ascii_letters + string.digits + "-_"
    if not all(c in valid_chars for c in token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_secure_token() -> Tuple[str, str]:
    """
    Generate a secure bearer token and its SHA-256 hash.

    Returns:
        Tuple[str, str]: (token, token_hash) where token is the plain token
        and token_hash is the SHA-256 hex digest for storage.
    """
    # Generate cryptographically secure token
    token = secrets.token_urlsafe(32)

    # Create SHA-256 hash for storage (no salt needed for local security per spec)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    return token, token_hash


def verify_bearer_token(token: str, stored_token_hash: str) -> bool:
    """
    Verify a bearer token against a stored hash.

    Args:
        token: The plain token to verify
        stored_token_hash: The SHA-256 hash stored in the database

    Returns:
        bool: True if token is valid, False otherwise
    """
    if not token or not stored_token_hash:
        return False

    # Hash the provided token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Use secure comparison to prevent timing attacks
    return secrets.compare_digest(token_hash, stored_token_hash)


def validate_bearer_token_format(token: str) -> None:
    """
    Validate that a token has the expected format.

    Args:
        token: The token to validate

    Raises:
        HTTPException: If token format is invalid
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token cannot be empty",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Basic length check (token_urlsafe(32) produces ~43 character tokens)
    if len(token) < 20:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(player_id: str) -> str:
    """
    Create an access token for testing purposes.
    
    This is a simplified token generation function primarily for tests.
    In production, use the proper Player.generate_token() method.
    
    Args:
        player_id: The player ID to create a token for
        
    Returns:
        str: A simple token string for testing
    """
    # Generate a secure token using the same method as the main system
    token, _ = generate_secure_token()
    return token
