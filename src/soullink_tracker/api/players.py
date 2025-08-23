"""Player management API endpoints."""

from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run, Player
from ..auth.dependencies import get_current_player
from .middleware import ProblemDetailsException
from .schemas import PlayerResponse, PlayerListResponse, ProblemDetails

router = APIRouter(tags=["players"])


@router.post(
    "/v1/players/{player_id}/rotate-token",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Token rotated successfully"},
        401: {"model": ProblemDetails, "description": "Authentication required"},
        403: {
            "model": ProblemDetails,
            "description": "Not authorized to rotate this player's token",
        },
        404: {"model": ProblemDetails, "description": "Player not found"},
    },
)
def rotate_player_token(
    player_id: UUID,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Rotate (regenerate) a player's bearer token.

    This endpoint allows a player to generate a new token, invalidating the old one.
    **IMPORTANT: The new token is only shown once and cannot be retrieved again.**
    All existing connections using the old token will be immediately invalidated.

    Players can only rotate their own tokens. The current token must be valid
    to authorize this operation.
    """
    # Verify the target player exists
    target_player = db.query(Player).filter(Player.id == player_id).first()
    if not target_player:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Player Not Found",
            detail=f"Player with ID {player_id} does not exist",
        )

    # Verify authorization - players can only rotate their own tokens
    if current_player.id != target_player.id:
        raise ProblemDetailsException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="You can only rotate your own token",
        )

    try:
        # Generate new token and update player
        new_token = target_player.rotate_token()

        db.commit()

        return {
            "message": "Token rotated successfully",
            "player_id": str(target_player.id),
            "player_name": target_player.name,
            "new_token": new_token,
            "warning": "This token will only be displayed once. Store it securely.",
        }

    except Exception as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Failed to rotate token: {str(e)}",
        )


@router.get(
    "/v1/runs/{run_id}/players",
    response_model=PlayerListResponse,
    responses={
        200: {"description": "Players retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        422: {"model": ProblemDetails, "description": "Invalid run ID format"},
    },
)
def get_players_in_run(
    run_id: UUID, db: Session = Depends(get_db)
) -> PlayerListResponse:
    """
    Get all players in a SoulLink run.

    Returns a list of all players participating in the specified run.
    Player tokens are NOT included in the response for security reasons.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run not found",
            detail="The specified run does not exist",
        )

    # Get players
    players = (
        db.query(Player)
        .filter(Player.run_id == run_id)
        .order_by(Player.created_at.asc())
        .all()
    )

    return PlayerListResponse(
        players=[PlayerResponse.model_validate(player) for player in players]
    )
