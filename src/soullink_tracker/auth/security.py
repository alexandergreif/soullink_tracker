"""Security utilities for authentication."""

import hashlib
import secrets
from typing import Tuple

from fastapi import HTTPException, status


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
