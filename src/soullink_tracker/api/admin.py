"""Admin endpoints for v3 event store management and secure token system."""

from uuid import UUID
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
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

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Run created successfully"},
        400: {"model": ProblemDetails, "description": "Invalid request"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def create_run(run_data: RunCreate, db: Session = Depends(get_db)) -> RunResponse:
    """
    Create a new SoulLink run.

    This is an admin-only endpoint that creates a new run which can then
    have players added to it via the player creation endpoint.
    """
    try:
        # Create new run
        new_run = Run(name=run_data.name, rules_json=run_data.rules_json)

        db.add(new_run)
        db.commit()
        db.refresh(new_run)

        return RunResponse.model_validate(new_run)

    except Exception as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Failed to create run: {str(e)}",
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
    run_id: UUID, player_data: PlayerCreate, db: Session = Depends(get_db)
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

        # Create new player
        new_player = Player(
            run_id=run_id,
            name=player_data.name,
            game=player_data.game.value
            if hasattr(player_data.game, "value")
            else player_data.game,
            region=player_data.region.value
            if hasattr(player_data.region, "value")
            else player_data.region,
            token_hash=token_hash,
        )

        db.add(new_player)
        db.commit()
        db.refresh(new_player)

        # Return player data with the one-time token
        player_data = {
            "id": new_player.id,
            "run_id": new_player.run_id,
            "name": new_player.name,
            "game": new_player.game,
            "region": new_player.region,
            "created_at": new_player.created_at,
            "player_token": token,  # Include the plain token
        }

        return PlayerWithTokenResponse(**player_data)

    except Exception as e:
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Failed to create player: {str(e)}",
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
