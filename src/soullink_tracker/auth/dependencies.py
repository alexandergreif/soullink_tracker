"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from .security import validate_bearer_token_format, verify_bearer_token
from ..db.database import get_db
from ..db.models import Player

# Security scheme for Bearer token
security = HTTPBearer()


def get_current_player(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Player:
    """
    Get the current authenticated player from the Bearer token.

    This dependency can be used in route handlers to require authentication
    and get the current player object.
    """
    token = credentials.credentials

    # Validate token format
    validate_bearer_token_format(token)

    # Find player by token hash
    player = db.query(Player).filter(Player.token_hash.isnot(None)).all()

    # Verify token against each player (secure but inefficient for large scale)
    # For production with many users, consider indexing by token prefix
    authenticated_player = None
    for candidate in player:
        if verify_bearer_token(token, candidate.token_hash):
            authenticated_player = candidate
            break

    if not authenticated_player:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authenticated_player


def get_current_player_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[Player]:
    """
    Get the current authenticated player, returning None if not authenticated.

    This dependency can be used for optional authentication.
    """
    if not credentials:
        return None

    try:
        return get_current_player(credentials, db)
    except HTTPException:
        return None


# Alternative dependency that takes token directly (for testing)
def get_current_player_from_token(token: str, db: Session) -> Player:
    """Get current player directly from token string (for testing)."""
    # Validate token format
    validate_bearer_token_format(token)

    # Find player by token verification
    players = db.query(Player).filter(Player.token_hash.isnot(None)).all()

    authenticated_player = None
    for candidate in players:
        if verify_bearer_token(token, candidate.token_hash):
            authenticated_player = candidate
            break

    if not authenticated_player:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authenticated_player
