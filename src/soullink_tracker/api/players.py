"""Player management API endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..db.database import get_db
from ..db.models import Run, Player
from .schemas import (
    PlayerCreate, PlayerResponse, PlayerWithTokenResponse, 
    PlayerListResponse, ProblemDetails
)

router = APIRouter(tags=["players"])


@router.post(
    "/v1/runs/{run_id}/players",
    response_model=PlayerWithTokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Player created successfully with token"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        409: {"model": ProblemDetails, "description": "Player name already exists in this run"},
        422: {"model": ProblemDetails, "description": "Validation error"}
    }
)
def create_player(
    run_id: UUID,
    player_data: PlayerCreate,
    db: Session = Depends(get_db)
) -> PlayerWithTokenResponse:
    """
    Create a new player in a SoulLink run.
    
    This endpoint is typically used by administrators to add players to a run.
    Returns a player token that should be securely stored by the client - it will
    not be shown again. The token is used for event authentication.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Generate token
    token, token_hash = Player.generate_token()
    
    # Create player
    player = Player(
        run_id=run_id,
        name=player_data.name,
        game=player_data.game.value,
        region=player_data.region.value,
        token_hash=token_hash
    )
    
    try:
        db.add(player)
        db.commit()
        db.refresh(player)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Player with name '{player_data.name}' already exists in this run"
        )
    
    # Return player data with token
    player_data = PlayerResponse.model_validate(player)
    return PlayerWithTokenResponse(
        **player_data.model_dump(),
        player_token=token
    )


@router.get(
    "/v1/runs/{run_id}/players",
    response_model=PlayerListResponse,
    responses={
        200: {"description": "Players retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        422: {"model": ProblemDetails, "description": "Invalid run ID format"}
    }
)
def get_players_in_run(
    run_id: UUID,
    db: Session = Depends(get_db)
) -> PlayerListResponse:
    """
    Get all players in a SoulLink run.
    
    Returns a list of all players participating in the specified run.
    Player tokens are NOT included in the response for security reasons.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Get players
    players = db.query(Player).filter(
        Player.run_id == run_id
    ).order_by(Player.created_at.asc()).all()
    
    return PlayerListResponse(
        players=[PlayerResponse.model_validate(player) for player in players]
    )