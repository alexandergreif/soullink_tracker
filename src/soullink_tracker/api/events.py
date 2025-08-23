"""Event ingestion API endpoints with v3 event store integration."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Union
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..db.database import get_db
from ..db.models import Run, Player, Species, IdempotencyKey, Encounter
from ..core.enums import EncounterStatus
from ..auth.dependencies import get_current_player
from ..utils.logging_config import get_logger, log_exception

# v3 event store imports (used when feature flag is enabled)
from ..domain.events import EncounterEvent, CatchResultEvent, FaintEvent
from ..store.event_store import EventStore, EventStoreError
from ..store.projections import ProjectionEngine

# WebSocket broadcasting for real-time updates
from ..events.websocket_manager import websocket_manager
from .middleware import ProblemDetailsException
from .schemas import (
    EventEncounter,
    EventCatchResult,
    EventFaint,
    EventResponse,
    ProblemDetails,
    EventCatchUpResponse,
)

router = APIRouter(prefix="/v1/events", tags=["events"])
logger = get_logger('events')


def _check_idempotency(
    db: Session, idempotency_key: str, run_id: UUID, player_id: UUID, request_data: dict
) -> Union[dict, None]:
    """Check if request was already processed using idempotency key."""
    if not idempotency_key:
        return None
    
    logger.debug(f"Checking idempotency key: {idempotency_key} for player {player_id}")

    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode()
    ).hexdigest()

    existing = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.key == idempotency_key,
            IdempotencyKey.run_id == run_id,
            IdempotencyKey.player_id == player_id,
            IdempotencyKey.request_hash == request_hash,
        )
        .first()
    )

    if existing:
        return existing.response_json

    return None


def _store_idempotency(
    db: Session,
    idempotency_key: str,
    run_id: UUID,
    player_id: UUID,
    request_data: dict,
    response_data: dict,
):
    """Store idempotency key and response for future duplicate requests."""
    if not idempotency_key:
        return

    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode()
    ).hexdigest()

    idempotency_record = IdempotencyKey(
        key=idempotency_key,
        run_id=run_id,
        player_id=player_id,
        request_hash=request_hash,
        response_json=response_data,
        created_at=datetime.now(timezone.utc),
    )

    db.add(idempotency_record)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Event processed successfully"},
        400: {"model": ProblemDetails, "description": "Invalid request format"},
        401: {"model": ProblemDetails, "description": "Authentication required"},
        403: {"model": ProblemDetails, "description": "Not authorized for this player"},
        404: {
            "model": ProblemDetails,
            "description": "Run or related entity not found",
        },
        413: {"model": ProblemDetails, "description": "Request entity too large"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
async def process_event(
    event: Union[EventEncounter, EventCatchResult, EventFaint],
    request: Request,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> EventResponse:
    """
    Process a game event (encounter, catch result, or faint).

    Supports v2 legacy tables, v3 event store, and optional dual-write when the
    feature flag `feature_v3_dualwrite` is enabled.

    Requires Idempotency-Key header (UUID v4) to prevent duplicate processing.

    For encounter events, returns event_id and sequence number.
    For catch_result events, requires valid encounter_id reference.
    """
    logger.info(f"Processing {event.type} event for player {event.player_id} in run {event.run_id}")
    
    # Verify player authorization
    if str(current_player.id) != str(event.player_id):
        raise ProblemDetailsException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="Not authorized to submit events for this player",
        )

    # Verify run exists and player belongs to it
    run = db.query(Run).filter(Run.id == event.run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run Not Found",
            detail=f"Run with ID {event.run_id} not found",
        )

    if current_player.run_id != event.run_id:
        raise ProblemDetailsException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="Player does not belong to this run",
        )

    # Process event atomically with idempotency protection
    idempotency_key = request.headers.get("idempotency-key")
    request_data = event.model_dump(mode="json")

    return await _process_event_atomic(db, event, idempotency_key, request_data)


@router.get(
    "",
    response_model=EventCatchUpResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Events retrieved successfully"},
        400: {"model": ProblemDetails, "description": "Invalid parameters"},
        401: {"model": ProblemDetails, "description": "Authentication required"},
        403: {"model": ProblemDetails, "description": "Not authorized for this run"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        501: {"model": ProblemDetails, "description": "v3 Event Store not enabled"},
    },
)
def get_events_catchup(
    run_id: UUID = Query(description="Run ID to get events for"),
    since_seq: int = Query(
        default=0, ge=0, description="Get events after this sequence number"
    ),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum events to return"
    ),
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> EventCatchUpResponse:
    """
    Catch-up REST endpoint for WebSocket clients to retrieve missed events.

    This endpoint allows WebSocket clients to retrieve events they may have missed
    while disconnected, using sequence numbers for efficient synchronization.

    Query Parameters:
    - run_id: Run ID to get events for (required)
    - since_seq: Get events after this sequence number (optional, default=0)
    - limit: Maximum events to return (optional, default=100, max=1000)

    Returns events in chronological order with sequence numbers and timestamps.
    """
    # Verify run exists and player belongs to it
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ProblemDetailsException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Run Not Found",
            detail=f"Run with ID {run_id} not found",
        )

    if current_player.run_id != run_id:
        raise ProblemDetailsException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="Player does not belong to this run",
        )

    try:
        # Initialize event store
        event_store = EventStore(db)

        # Get events since the specified sequence number
        event_envelopes = event_store.get_events(
            run_id=run_id, since_seq=since_seq, limit=limit
        )

        # Get the latest sequence number for this run
        latest_seq = event_store.get_latest_sequence(run_id)

        # Convert to response format
        events = []
        for envelope in event_envelopes:
            # Extract event data from the domain event
            event_data = envelope.event.model_dump(
                mode="json", exclude={"event_id", "timestamp"}
            )

            events.append(
                {
                    "event_id": envelope.event.event_id,
                    "seq": envelope.sequence_number,
                    "type": envelope.event.event_type,
                    "timestamp": envelope.event.timestamp,
                    "player_id": envelope.event.player_id,
                    "data": event_data,
                }
            )

        # Determine if there are more events beyond the limit
        has_more = len(event_envelopes) >= limit

        return EventCatchUpResponse(
            events=events, total=len(events), latest_seq=latest_seq, has_more=has_more
        )

    except EventStoreError as e:
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Event Store Error",
            detail=f"Failed to retrieve events: {e}",
        )
    except Exception as e:
        log_exception('events', e, {'run_id': str(run_id), 'since_seq': since_seq})
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Unexpected error retrieving events: {e}",
        )


# Legacy v2 processing functions removed in v3-only architecture


async def _broadcast_event_update(
    event: Union["EncounterEvent", "CatchResultEvent", "FaintEvent"],
    sequence_number: int,
):
    """Broadcast event update to WebSocket clients with sequence number.

    Args:
        event: Domain event (not API schema event)
        sequence_number: Event sequence number for ordering
    """
    logger.debug(f"Broadcasting {event.event_type} event with sequence {sequence_number}")
    try:
        # Import WebSocket message schemas locally to avoid circular imports
        from ..events.schemas import (
            EncounterEventMessage,
            CatchResultEventMessage,
            FaintEventMessage,
        )

        # Create appropriate WebSocket message based on event type
        if event.event_type == "encounter":
            # Convert enum values to their enum objects for WebSocket message
            from ..core.enums import EncounterMethod, EncounterStatus

            # Handle encounter method conversion
            if isinstance(event.encounter_method, str):
                method_enum = EncounterMethod(event.encounter_method)
            else:
                method_enum = event.encounter_method

            # Handle status conversion
            if isinstance(event.status, str):
                status_enum = EncounterStatus(event.status)
            else:
                status_enum = event.status

            # Handle rod kind conversion
            rod_kind_str = None
            if event.rod_kind:
                if isinstance(event.rod_kind, str):
                    rod_kind_str = event.rod_kind
                else:
                    rod_kind_str = (
                        event.rod_kind.value
                        if hasattr(event.rod_kind, "value")
                        else str(event.rod_kind)
                    )

            message = EncounterEventMessage(
                run_id=event.run_id,
                player_id=event.player_id,
                route_id=event.route_id,
                species_id=event.species_id,
                family_id=event.family_id,
                level=event.level,
                shiny=event.shiny,
                method=method_enum,
                status=status_enum,
                rod_kind=rod_kind_str,
            )
        elif event.event_type == "catch_result":
            # For now, keep using encounter_ref format until WebSocket schema is updated
            encounter_ref = {
                "route_id": getattr(event, "route_id", None),
                "species_id": getattr(event, "species_id", None),
            }

            # Convert result enum to string
            result_str = (
                event.result.value
                if hasattr(event.result, "value")
                else str(event.result)
            )

            message = CatchResultEventMessage(
                run_id=event.run_id,
                player_id=event.player_id,
                encounter_ref=encounter_ref,
                status=result_str,  # Keep as 'status' for now until schema is updated
            )
        elif event.event_type == "faint":
            message = FaintEventMessage(
                run_id=event.run_id,
                player_id=event.player_id,
                pokemon_key=event.pokemon_key,
                party_index=event.party_index,
            )
        else:
            # Unknown event type, skip broadcasting
            return

        # Broadcast to all connections in the run with sequence number
        await websocket_manager.broadcast_to_run(
            run_id=event.run_id, message=message, sequence_number=sequence_number
        )

    except Exception as e:
        # Log error but don't fail the event processing
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"Failed to broadcast WebSocket update for {event.type} event: {e}"
        )


async def _process_event_v3(
    db: Session,
    event: Union[EventEncounter, EventCatchResult, EventFaint],
    applied_rules: list,
) -> tuple[UUID, int]:
    """Process an event using v3 event store + projections."""
    try:
        # Initialize v3 components
        event_store = EventStore(db)
        projection_engine = ProjectionEngine(db)

        # Convert API event to domain event
        domain_event = _convert_to_domain_event(db, event)

        # Store in event store
        envelope = event_store.append(domain_event)
        applied_rules.append("event_stored_v3")

        # Update projections
        projection_engine.apply_event(envelope)
        applied_rules.append("projections_updated")

        # Broadcast to WebSocket clients with sequence number
        await _broadcast_event_update(domain_event, envelope.sequence_number)
        applied_rules.append("websocket_broadcast")

        return domain_event.event_id, envelope.sequence_number

    except EventStoreError as e:
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Event Store Error",
            detail=f"Failed to store event: {e}",
        )
    except Exception as e:
        raise ProblemDetailsException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"Unexpected error in v3 event processing: {e}",
        )


def _convert_to_domain_event(
    db: Session, event: Union[EventEncounter, EventCatchResult, EventFaint]
):
    """Convert API event schema to domain event."""
    if event.type == "encounter":
        # Resolve family_id from Species table
        species = db.query(Species).filter(Species.id == event.species_id).first()
        if not species:
            raise ProblemDetailsException(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Species Not Found",
                detail=f"Species with ID {event.species_id} not found",
            )

        return EncounterEvent(
            event_id=uuid4(),
            run_id=event.run_id,
            player_id=event.player_id,
            timestamp=event.time,
            route_id=event.route_id,
            species_id=event.species_id,
            family_id=species.family_id,  # Now properly resolved from DB
            level=event.level,
            shiny=event.shiny,
            encounter_method=event.method,
            rod_kind=event.rod_kind,
            status=EncounterStatus.FIRST_ENCOUNTER,  # Would be determined by rules
            dupes_skip=False,
            fe_finalized=False,
        )
    elif event.type == "catch_result":
        # Handle both V3 encounter_id and V2 legacy encounter_ref formats
        if event.encounter_id:
            # V3 format - direct encounter reference
            encounter_id = event.encounter_id
        elif event.encounter_ref:
            # V2 legacy format - lookup encounter by route/species
            encounter = (
                db.query(Encounter)
                .filter(
                    Encounter.run_id == event.run_id,
                    Encounter.player_id == event.player_id,
                    Encounter.route_id == event.encounter_ref["route_id"],
                    Encounter.species_id == event.encounter_ref["species_id"],
                )
                .order_by(Encounter.time.desc())
                .first()
            )
            if not encounter:
                raise ProblemDetailsException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    title="Encounter Not Found",
                    detail=f"No encounter found for route {event.encounter_ref['route_id']} species {event.encounter_ref['species_id']}",
                )
            encounter_id = encounter.id
        else:
            raise ProblemDetailsException(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Invalid Catch Result",
                detail="Either encounter_id or encounter_ref must be provided",
            )

        return CatchResultEvent(
            event_id=uuid4(),
            run_id=event.run_id,
            player_id=event.player_id,
            timestamp=event.time,
            encounter_id=encounter_id,
            result=event.result,
        )
    elif event.type == "faint":
        return FaintEvent(
            event_id=uuid4(),
            run_id=event.run_id,
            player_id=event.player_id,
            timestamp=event.time,
            pokemon_key=event.pokemon_key,
            party_index=getattr(event, "party_index", None),
        )
    else:
        raise ValueError(f"Unknown event type: {event.type}")


async def _process_event_atomic(
    db: Session,
    event: Union[EventEncounter, EventCatchResult, EventFaint],
    idempotency_key: str,
    request_data: dict,
) -> EventResponse:
    """Process event atomically with idempotency protection using database constraints.

    This implementation prevents race conditions by:
    1. Using a database transaction to make idempotency check and event processing atomic
    2. Leveraging database unique constraints on idempotency keys
    3. Handling constraint violations to detect duplicate processing attempts
    """
    if not idempotency_key:
        raise ProblemDetailsException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Missing Idempotency Key",
            detail="Idempotency-Key header is required for event processing",
        )

    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode()
    ).hexdigest()

    try:
        # Check if transaction is already started
        if not db.in_transaction():
            db.begin()

        # First, try to create the idempotency record immediately
        # This acts as a lock and prevents duplicate processing
        idempotency_record = IdempotencyKey(
            key=idempotency_key,
            run_id=event.run_id,
            player_id=event.player_id,
            request_hash=request_hash,
            response_json={},  # Will be updated after successful processing
            created_at=datetime.now(timezone.utc),
        )

        db.add(idempotency_record)

        try:
            # Flush to trigger constraint check without committing
            db.flush()
        except IntegrityError:
            # Constraint violation means this request was already processed
            db.rollback()

            # Retrieve the existing response
            existing = (
                db.query(IdempotencyKey)
                .filter(
                    IdempotencyKey.key == idempotency_key,
                    IdempotencyKey.run_id == event.run_id,
                    IdempotencyKey.player_id == event.player_id,
                    IdempotencyKey.request_hash == request_hash,
                )
                .first()
            )

            if existing and existing.response_json:
                return EventResponse(**existing.response_json)
            else:
                # Edge case: record exists but no response stored yet
                # This could happen if another thread is still processing
                raise ProblemDetailsException(
                    status_code=status.HTTP_409_CONFLICT,
                    title="Request In Progress",
                    detail="This request is currently being processed by another thread",
                )

        # If we reach here, the idempotency record was successfully created
        # Now process the event
        applied_rules: list[str] = []

        try:
            # Process using v3 event store (only supported architecture)
            event_id, sequence_number = await _process_event_v3(
                db, event, applied_rules
            )

            # Prepare response
            response_data: dict = {
                "message": "Event processed successfully",
                "event_id": str(event_id) if event_id else None,
                "applied_rules": applied_rules,
            }

            # Add sequence number for encounter events
            if event.type == "encounter" and sequence_number is not None:
                response_data["seq"] = sequence_number

            # Update the idempotency record with the successful response
            idempotency_record.response_json = response_data

            # Commit the entire transaction atomically
            db.commit()
            return EventResponse(**response_data)

        except Exception as e:
            # Event processing failed, rollback everything including idempotency record
            db.rollback()

            # Re-raise the exception (it should already be a ProblemDetailsException)
            if not isinstance(e, ProblemDetailsException):
                raise ProblemDetailsException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    title="Processing Error",
                    detail=f"An error occurred while processing the event: {str(e)}",
                )
            raise

    except IntegrityError:
        # This shouldn't happen since we handle it above, but just in case
        db.rollback()
        raise ProblemDetailsException(
            status_code=status.HTTP_409_CONFLICT,
            title="Duplicate Request",
            detail="This request has already been processed",
        )
    except Exception as e:
        # Unexpected error, rollback and re-raise
        db.rollback()
        if not isinstance(e, ProblemDetailsException):
            raise ProblemDetailsException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                title="Internal Server Error",
                detail=f"Unexpected error during atomic processing: {str(e)}",
            )
        raise
