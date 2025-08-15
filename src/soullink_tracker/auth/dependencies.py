"""Authentication dependencies for FastAPI."""

from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import Optional

from .security import (
    validate_bearer_token_format,
    verify_bearer_token,
    validate_session_token_format,
    verify_password
)
from ..config import get_config
from ..db.database import get_db
from ..db.models import Player, PlayerSession, Run

# Security scheme for Bearer token
security = HTTPBearer()


def get_current_player(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Player:
    """
    Get the current authenticated player from Bearer token.

    Tries session token authentication first, falls back to legacy Bearer
    token if AUTH_ALLOW_LEGACY_BEARER=True.

    This dependency can be used in route handlers to require authentication
    and get the current player object.
    """
    token = credentials.credentials
    config = get_config()

    # Try session token authentication first
    try:
        validate_session_token_format(token)
        return get_current_player_from_session_token(token, db)
    except HTTPException:
        # Session token failed, try legacy Bearer if allowed
        if config.app.auth_allow_legacy_bearer:
            try:
                validate_bearer_token_format(token)
                # Find player by token hash
                players = db.query(Player).filter(Player.token_hash.isnot(None)).all()
                
                # Verify token against each player
                for candidate in players:
                    if verify_bearer_token(token, candidate.token_hash):
                        return candidate
                        
                # Legacy Bearer token not found
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except HTTPException:
                pass
    
    # Both authentication methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


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


def get_current_player_from_session_token(token: str, db: Session) -> Player:
    """
    Get current player from session token.
    
    Args:
        token: The session token to authenticate with
        db: Database session
        
    Returns:
        Player: The authenticated player
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    import hashlib
    
    # Hash the token to find the session
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    
    # Find session by token hash with player joined
    session = (
        db.query(PlayerSession)
        .join(Player)
        .filter(PlayerSession.token_hash == token_hash)
        .filter(PlayerSession.expires_at > now)
        .first()
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last seen time
    session.last_seen_at = now
    db.commit()
    
    return session.player


def authenticate_with_credentials(
    run_id: Optional[UUID],
    run_name: Optional[str],
    player_name: str,
    password: str,
    db: Session
) -> tuple[Player, Run]:
    """
    Authenticate player with run credentials (run ID/name + player name + password).
    
    Args:
        run_id: Optional run UUID
        run_name: Optional run name (used if run_id not provided)
        player_name: Player name for authentication
        password: Run password
        db: Database session
        
    Returns:
        tuple[Player, Run]: The authenticated player and run
        
    Raises:
        HTTPException: If authentication fails
    """
    # Resolve run by ID or name
    if run_id:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found"
            )
    elif run_name:
        runs = db.query(Run).filter(func.lower(Run.name) == run_name.lower()).all()
        if not runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found"
            )
        if len(runs) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple runs found with that name, please use run ID"
            )
        run = runs[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either run_id or run_name must be provided"
        )
    
    # Verify password
    if not run.password_hash or not run.password_salt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Run does not require password authentication"
        )
    
    if not verify_password(password, run.password_salt, run.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Find player by name (case-insensitive)
    player = (
        db.query(Player)
        .filter(Player.run_id == run.id)
        .filter(func.lower(Player.name) == player_name.lower())
        .first()
    )
    
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found in this run"
        )
    
    return player, run


# Alternative dependency that takes token directly (for testing)
def get_current_player_from_token(token: str, db: Session) -> Player:
    """Get current player directly from token string (for testing)."""
    # Try session token first
    try:
        validate_session_token_format(token)
        return get_current_player_from_session_token(token, db)
    except HTTPException:
        # Fall back to legacy Bearer token
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
