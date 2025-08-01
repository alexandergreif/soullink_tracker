"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from .security import verify_token
from ..db.database import get_db
from ..db.models import Player

# Security scheme for Bearer token
security = HTTPBearer()


def get_current_player(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Player:
    """
    Get the current authenticated player from the JWT token.
    
    This dependency can be used in route handlers to require authentication
    and get the current player object.
    """
    try:
        # Verify the JWT token and get player ID
        player_id_str = verify_token(credentials.credentials)
        player_id = UUID(player_id_str)
        
        # Look up the player in the database
        player = db.query(Player).filter(Player.id == player_id).first()
        
        if not player:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Player not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return player
        
    except ValueError as e:
        # Invalid UUID format
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid player ID format: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_player_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Player]:
    """
    Get the current authenticated player, returning None if not authenticated.
    
    This dependency can be used for optional authentication.
    """
    try:
        return get_current_player(credentials, db)
    except HTTPException:
        return None


# Alternative dependency that takes token directly (for testing)
def get_current_player_from_token(token: str, db: Session) -> Player:
    """Get current player directly from token string (for testing)."""
    try:
        player_id_str = verify_token(token)
        player_id = UUID(player_id_str)
        
        player = db.query(Player).filter(Player.id == player_id).first()
        
        if not player:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Player not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return player
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid player ID format: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )