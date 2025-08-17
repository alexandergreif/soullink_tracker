"""Admin endpoints for v3 event store management and secure token system."""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Dict, Any

from fastapi import APIRouter, Depends, status, Request, HTTPException
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run, Player
from ..store.event_store import EventStore, EventStoreError
from ..store.projections import ProjectionEngine, ProjectionError
from ..config import get_config
from .middleware import ProblemDetailsException
from .schemas import (
    ProblemDetails,
    RunCreate,
    RunResponse,
    PlayerCreate,
    PlayerWithTokenResponse,
)
from typing import List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin", tags=["admin"])


def require_localhost(request: Request):
    """Dependency to restrict admin endpoints to localhost only."""
    client_host = request.client.host if request.client else None
    
    # Check both IPv4 and IPv6 localhost addresses
    localhost_ips = {"127.0.0.1", "::1"}
    
    if client_host not in localhost_ips:
        logger.warning(f"Admin API access denied from {client_host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API only available from localhost"
        )
    return True


@router.get(
    "/runs",
    response_model=List[RunResponse],
    responses={
        200: {"description": "List of all runs"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
    },
)
def list_runs(
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> List[RunResponse]:
    """
    List all SoulLink runs.

    This is an admin-only endpoint that returns all runs in the system.
    """
    try:
        runs = db.query(Run).order_by(Run.created_at.desc()).all()
        return [RunResponse.model_validate(run) for run in runs]

    except Exception as e:
        logger.error(f"Failed to list runs: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to retrieve runs. Please check server logs for details.",
        )


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Run created successfully"},
        400: {"model": ProblemDetails, "description": "Invalid request"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def create_run(
    run_data: RunCreate,
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> RunResponse:
    """
    Create a new SoulLink run.

    This is an admin-only endpoint that creates a new run which can then
    have players added to it via the player creation endpoint.
    """
    try:
        # Hash the password if provided
        password_salt = None
        password_hash = None
        if hasattr(run_data, 'password') and run_data.password:
            from ..auth.security import hash_password
            password_salt, password_hash = hash_password(run_data.password)
        
        # Create new run
        new_run = Run(
            name=run_data.name,
            rules_json=run_data.rules_json,
            password_salt=password_salt,
            password_hash=password_hash
        )

        db.add(new_run)
        db.commit()
        db.refresh(new_run)

        return RunResponse.model_validate(new_run)

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create run: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to create run. Please check server logs for details.",
        )


@router.post(
    "/runs/{run_id}/players",
    response_model=PlayerWithTokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Player created successfully with token"},
        400: {"model": ProblemDetails, "description": "Invalid request"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        409: {
            "model": ProblemDetails,
            "description": "Player name already exists in run",
        },
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def create_player(
    run_id: UUID,
    player_data: PlayerCreate,
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> PlayerWithTokenResponse:
    """
    Create a new player in a run with secure token generation.

    This endpoint creates a player and returns their bearer token.
    **IMPORTANT: The token is only shown once and cannot be retrieved again.**
    Store the token securely as it will be needed for all API calls.

    The token is stored as a SHA-256 hash in the database for security.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run Not Found",
            detail=f"Run with ID {run_id} does not exist",
        )

    # Check if player name already exists in this run
    existing_player = (
        db.query(Player)
        .filter(Player.run_id == run_id, Player.name == player_data.name)
        .first()
    )

    if existing_player:
        raise ProblemDetailsException(
            status_code=status.HTTP_409_CONFLICT,
            title="Player Already Exists",
            detail=f"Player with name '{player_data.name}' already exists in this run",
        )

    try:
        # Generate secure token
        token, token_hash = Player.generate_token()

        # Use the create_with_token method from the model
        new_player, token = Player.create_with_token(
            db, run_id, player_data.name, player_data.game, player_data.region
        )

        # Return player data with the one-time token
        response_data = {
            "id": new_player.id,
            "run_id": new_player.run_id,
            "name": new_player.name,
            "game": new_player.game,
            "region": new_player.region,
            "created_at": new_player.created_at,
            "new_token": token,  # Include the plain token
        }

        return PlayerWithTokenResponse(**response_data)

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create player: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to create player. Please check server logs for details.",
        )


@router.post(
    "/players/{player_id}/token",
    responses={
        200: {"description": "Token generated successfully"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
        404: {"model": ProblemDetails, "description": "Player not found"},
    },
)
def generate_player_token(
    player_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> Dict[str, Any]:
    """
    Generate a new token for an existing player.

    This is an admin-only endpoint that generates a new token for a player.
    **IMPORTANT: The token is only shown once and cannot be retrieved again.**
    """
    # Verify the player exists
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Player Not Found",
            detail=f"Player with ID {player_id} does not exist",
        )

    try:
        # Generate new token and update player
        new_token = player.rotate_token()
        db.commit()

        return {
            "message": "Token generated successfully",
            "player_id": str(player.id),
            "player_name": player.name,
            "bearer_token": new_token,
            "warning": "This token will only be displayed once. Store it securely.",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate token: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to generate token. Please check server logs for details.",
        )


@router.post(
    "/rebuild/{run_id}",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Projection rebuild initiated successfully"},
        400: {"model": ProblemDetails, "description": "Invalid request"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        503: {"model": ProblemDetails, "description": "v3 event store not enabled"},
    },
)
def rebuild_projections(run_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Rebuild all projections for a run from event store.

    This endpoint is for admin/development use only. It:
    1. Clears all projection tables for the specified run
    2. Replays all events from the event store in sequence
    3. Rebuilds projections deterministically

    **Requires v3 event store to be enabled via FEATURE_V3_EVENTSTORE=1**
    """
    # Check if v3 event store is enabled
    config = get_config()
    if not config.app.feature_v3_eventstore:
        raise ProblemDetailsException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Feature Not Available",
            detail="v3 event store is not enabled. Set FEATURE_V3_EVENTSTORE=1 to use this endpoint.",
        )

    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run Not Found",
            detail=f"Run with ID {run_id} does not exist",
        )

    try:
        # Initialize components
        event_store = EventStore(db)
        projection_engine = ProjectionEngine(db)

        # Get all events for this run
        events = event_store.get_events(run_id)

        if not events:
            return {
                "message": "No events found to replay",
                "run_id": str(run_id),
                "events_processed": 0,
            }

        # Rebuild projections
        projection_engine.rebuild_all_projections(run_id, events)

        # Commit the changes
        db.commit()

        return {
            "message": "Projections rebuilt successfully",
            "run_id": str(run_id),
            "events_processed": len(events),
            "last_sequence": events[-1].sequence_number if events else 0,
        }

    except EventStoreError as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Event Store Error",
            detail=f"Failed to access event store: {e}",
        )
    except ProjectionError as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Projection Error",
            detail=f"Failed to rebuild projections: {e}",
        )
    except Exception as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Unexpected error during projection rebuild: {e}",
        )


@router.get(
    "/players/stats",
    responses={
        200: {"description": "Player statistics across all runs"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
    },
)
def get_player_statistics(
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> Dict[str, Any]:
    """
    Get player statistics across all runs.

    This admin endpoint returns summary statistics about all players
    in the system including total count, active players, and last activity.
    """
    try:
        from sqlalchemy import func
        from ..db.models import PlayerSession

        # Get total player count
        total_players = db.query(func.count(Player.id)).scalar()

        # Get active players (those with sessions in last 5 minutes)
        five_minutes_ago = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=5)
        active_players = db.query(func.count(func.distinct(PlayerSession.player_id))).filter(
            PlayerSession.last_seen_at >= five_minutes_ago
        ).scalar()

        # Get latest activity timestamp
        latest_activity = db.query(func.max(PlayerSession.last_seen_at)).scalar()

        return {
            "total": total_players or 0,
            "active": active_players or 0,
            "last_activity": latest_activity.isoformat() if latest_activity else None,
        }

    except Exception as e:
        logger.error(f"Failed to get player statistics: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to retrieve player statistics. Please check server logs for details.",
        )


@router.get(
    "/players/global",
    responses={
        200: {"description": "List of all players across all runs"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
    },
)
def get_global_players(
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
) -> List[Dict[str, Any]]:
    """
    Get all players across all runs with their associated run information.

    This admin endpoint returns all players in the system along with their
    run details, activity status, and other metadata useful for administration.
    """
    try:
        from sqlalchemy import func
        from ..db.models import PlayerSession

        # Query players with their run information and latest session data
        query = db.query(
            Player.id,
            Player.run_id,
            Player.name,
            Player.game,
            Player.region,
            Player.created_at,
            Run.name.label("run_name"),
            func.max(PlayerSession.last_seen_at).label("last_seen")
        ).join(
            Run, Player.run_id == Run.id
        ).outerjoin(
            PlayerSession, Player.id == PlayerSession.player_id
        ).group_by(
            Player.id,
            Player.run_id,
            Player.name,
            Player.game,
            Player.region,
            Player.created_at,
            Run.name
        ).order_by(
            Player.created_at.desc()
        )

        players = query.all()

        # Convert to list of dictionaries
        result = []
        for player in players:
            result.append({
                "id": str(player.id),
                "run_id": str(player.run_id),
                "name": player.name,
                "game": player.game,
                "region": player.region,
                "created_at": player.created_at.isoformat(),
                "run_name": player.run_name,
                "last_seen": player.last_seen.isoformat() if player.last_seen else None,
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get global players: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to retrieve global players. Please check server logs for details.",
        )


@router.get(
    "/status/{run_id}",
    responses={
        200: {"description": "Event store status for run"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        503: {"model": ProblemDetails, "description": "v3 event store not enabled"},
    },
)
def get_event_store_status(
    run_id: UUID, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get event store status and statistics for a run.

    **Requires v3 event store to be enabled via FEATURE_V3_EVENTSTORE=1**
    """
    # Check if v3 event store is enabled
    config = get_config()
    if not config.app.feature_v3_eventstore:
        raise ProblemDetailsException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Feature Not Available",
            detail="v3 event store is not enabled. Set FEATURE_V3_EVENTSTORE=1 to use this endpoint.",
        )

    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run Not Found",
            detail=f"Run with ID {run_id} does not exist",
        )

    try:
        event_store = EventStore(db)

        # Get latest sequence number
        latest_sequence = event_store.get_latest_sequence(run_id)

        # Get event type distribution
        events = event_store.get_events(run_id)
        event_types = {}
        for event in events:
            event_type = event.event.event_type
            event_types[event_type] = event_types.get(event_type, 0) + 1

        return {
            "run_id": str(run_id),
            "run_name": run.name,
            "latest_sequence": latest_sequence,
            "total_events": len(events),
            "event_types": event_types,
            "v3_enabled": True,
        }

    except EventStoreError as e:
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Event Store Error",
            detail=f"Failed to access event store: {e}",
        )


@router.delete(
    "/players/{player_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Player deleted successfully"},
        403: {"model": ProblemDetails, "description": "Admin API only available on localhost"},
        404: {"model": ProblemDetails, "description": "Player not found"},
    },
)
def delete_player(
    player_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _localhost: bool = Depends(require_localhost)
):
    """
    Delete a player from the system.
    
    This is an admin-only endpoint that removes a player and all associated data
    including their sessions, encounters, and other related records.
    
    **WARNING: This action cannot be undone!**
    """
    # Verify the player exists
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Player Not Found",
            detail=f"Player with ID {player_id} does not exist",
        )
    
    try:
        # Delete the player (CASCADE should handle related records)
        db.delete(player)
        db.commit()
        
        logger.info(f"Player {player.name} (ID: {player_id}) deleted by admin")
        
        # Return 204 No Content
        return None
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete player: {str(e)}")
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Unable to delete player. Please check server logs for details.",
        )
