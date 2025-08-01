"""Event ingestion API endpoints."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import (
    Run, Player, Encounter, Species, Route, IdempotencyKey,
    Blocklist, PartyStatus, Link, LinkMember
)
from ..core.rules_engine import RulesEngine
from ..core.enums import EncounterStatus, EncounterMethod
from ..auth.dependencies import get_current_player
from ..events.websocket_manager import (
    websocket_manager, broadcast_encounter_event, broadcast_catch_result_event, broadcast_faint_event
)
from .schemas import (
    EventEncounter, EventCatchResult, EventFaint, EventResponse, ProblemDetails
)

router = APIRouter(prefix="/v1/events", tags=["events"])


def _check_idempotency(
    db: Session,
    idempotency_key: str,
    run_id: UUID,
    player_id: UUID,
    request_data: dict
) -> Union[dict, None]:
    """Check if request was already processed using idempotency key."""
    if not idempotency_key:
        return None
    
    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode()
    ).hexdigest()
    
    existing = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == idempotency_key,
        IdempotencyKey.run_id == run_id,
        IdempotencyKey.player_id == player_id,
        IdempotencyKey.request_hash == request_hash
    ).first()
    
    if existing:
        return existing.response_json
    
    return None


def _store_idempotency(
    db: Session,
    idempotency_key: str,
    run_id: UUID,
    player_id: UUID,
    request_data: dict,
    response_data: dict
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
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(idempotency_record)


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Event processed successfully"},
        401: {"model": ProblemDetails, "description": "Authentication required"},
        403: {"model": ProblemDetails, "description": "Not authorized for this player"},
        404: {"model": ProblemDetails, "description": "Run or related entity not found"},
        422: {"model": ProblemDetails, "description": "Validation error"}
    }
)
def process_event(
    event: Union[EventEncounter, EventCatchResult, EventFaint],
    request: Request,
    current_player: Player = Depends(get_current_player),
    db: Session = Depends(get_db)
) -> EventResponse:
    """
    Process a game event (encounter, catch result, or faint).
    
    Events are processed according to SoulLink rules and may trigger
    additional game logic like blocklist updates or soul link creation.
    
    Supports idempotency via the Idempotency-Key header to prevent
    duplicate processing of the same event.
    """
    # Verify player authorization
    if str(current_player.id) != str(event.player_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit events for this player"
        )
    
    # Verify run exists and player belongs to it
    run = db.query(Run).filter(Run.id == event.run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    if current_player.run_id != event.run_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Player does not belong to this run"
        )
    
    # Check idempotency
    idempotency_key = request.headers.get("Idempotency-Key")
    request_data = event.model_dump(mode='json')  # Serialize UUIDs as strings
    
    if idempotency_key:
        cached_response = _check_idempotency(
            db, idempotency_key, event.run_id, event.player_id, request_data
        )
        if cached_response:
            return EventResponse(**cached_response)
    
    # Process event based on type
    applied_rules = []
    event_id = None
    
    if event.type == "encounter":
        event_id = _process_encounter_event(db, event, applied_rules)
    elif event.type == "catch_result":
        event_id = _process_catch_result_event(db, event, applied_rules)
    elif event.type == "faint":
        event_id = _process_faint_event(db, event, applied_rules)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown event type: {event.type}"
        )
    
    # Prepare response
    response_data = {
        "message": "Event processed successfully",
        "event_id": str(event_id) if event_id else None,
        "applied_rules": applied_rules
    }
    
    # Store idempotency record
    if idempotency_key:
        _store_idempotency(
            db, idempotency_key, event.run_id, event.player_id, 
            request_data, response_data
        )
    
    db.commit()
    
    return EventResponse(**response_data)


def _process_encounter_event(db: Session, event: EventEncounter, applied_rules: list) -> UUID:
    """Process an encounter event."""
    rules_engine = RulesEngine()
    
    # Verify species and route exist
    species = db.query(Species).filter(Species.id == event.species_id).first()
    if not species:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Species with ID {event.species_id} not found"
        )
    
    route = db.query(Route).filter(Route.id == event.route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route with ID {event.route_id} not found"
        )
    
    # Get current blocklist and previous encounters
    blocklist = db.query(Blocklist).filter(Blocklist.run_id == event.run_id).all()
    previous_encounters = db.query(Encounter).filter(
        Encounter.run_id == event.run_id
    ).all()
    
    # Determine encounter status using rules engine
    encounter_status = rules_engine.determine_encounter_status(
        run_id=event.run_id,
        route_id=event.route_id,
        family_id=species.family_id,
        player_id=event.player_id,
        blocklist=blocklist,
        previous_encounters=previous_encounters
    )
    
    # Create encounter record
    encounter = Encounter(
        run_id=event.run_id,
        player_id=event.player_id,
        route_id=event.route_id,
        species_id=event.species_id,
        family_id=species.family_id,
        level=event.level,
        shiny=event.shiny,
        method=event.method,
        rod_kind=event.rod_kind,
        time=event.time,
        status=encounter_status,
        dupes_skip=(encounter_status == EncounterStatus.DUPE_SKIP),
        fe_finalized=False
    )
    
    db.add(encounter)
    db.flush()
    
    # Apply rules based on status
    if encounter_status == EncounterStatus.FIRST_ENCOUNTER:
        applied_rules.append("first_encounter_detected")
    elif encounter_status == EncounterStatus.DUPE_SKIP:
        applied_rules.append("dupe_skip_applied")
    
    # TODO: Broadcast encounter event to WebSocket clients
    # Note: WebSocket broadcasting is disabled in sync context for now
    # This would need to be implemented with a background task queue
    # or by making the API endpoints async
    
    return encounter.id


def _process_catch_result_event(db: Session, event: EventCatchResult, applied_rules: list) -> UUID:
    """Process a catch result event."""
    rules_engine = RulesEngine()
    
    # Find the encounter
    encounter = db.query(Encounter).filter(Encounter.id == event.encounter_id).first()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter with ID {event.encounter_id} not found"
        )
    
    # Verify encounter belongs to the same run and player
    if encounter.run_id != event.run_id or encounter.player_id != event.player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Encounter does not belong to this player or run"
        )
    
    # Update encounter status
    encounter.status = event.result
    applied_rules.append("catch_result_recorded")
    
    # If caught, apply additional rules
    if event.result == EncounterStatus.CAUGHT:
        # Add to blocklist if first encounter
        if encounter.status == EncounterStatus.FIRST_ENCOUNTER or not encounter.dupes_skip:
            blocklist_entry = Blocklist(
                run_id=event.run_id,
                family_id=encounter.family_id,
                origin="caught",
                created_at=datetime.now(timezone.utc)
            )
            db.add(blocklist_entry)
            applied_rules.append("family_blocked_caught")
        
        # Check for soul link creation
        route_encounters = db.query(Encounter).filter(
            Encounter.run_id == event.run_id,
            Encounter.route_id == encounter.route_id,
            Encounter.status == EncounterStatus.CAUGHT
        ).all()
        
        if rules_engine.should_create_soul_link(route_encounters, encounter.route_id):
            # Find or create link
            link = db.query(Link).filter(
                Link.run_id == event.run_id,
                Link.route_id == encounter.route_id
            ).first()
            
            if not link:
                link = Link(run_id=event.run_id, route_id=encounter.route_id)
                db.add(link)
                db.flush()
                applied_rules.append("soul_link_created")
            
            # Add link member if not already exists
            existing_member = db.query(LinkMember).filter(
                LinkMember.link_id == link.id,
                LinkMember.player_id == event.player_id
            ).first()
            
            if not existing_member:
                link_member = LinkMember(
                    link_id=link.id,
                    player_id=event.player_id,
                    encounter_id=encounter.id
                )
                db.add(link_member)
                applied_rules.append("soul_link_member_added")
    
    # TODO: Broadcast catch result event to WebSocket clients
    # Note: WebSocket broadcasting is disabled in sync context for now
    
    return encounter.id


def _process_faint_event(db: Session, event: EventFaint, applied_rules: list) -> UUID:
    """Process a faint event."""
    # Update party status
    party_status = db.query(PartyStatus).filter(
        PartyStatus.run_id == event.run_id,
        PartyStatus.player_id == event.player_id,
        PartyStatus.pokemon_key == event.pokemon_key
    ).first()
    
    if not party_status:
        party_status = PartyStatus(
            run_id=event.run_id,
            player_id=event.player_id,
            pokemon_key=event.pokemon_key,
            alive=False,
            last_update=event.time
        )
        db.add(party_status)
    else:
        party_status.alive = False
        party_status.last_update = event.time
    
    applied_rules.append("pokemon_marked_fainted")
    
    # TODO: Broadcast faint event to WebSocket clients
    # Note: WebSocket broadcasting is disabled in sync context for now
    
    # TODO: Implement soul link propagation (mark linked Pokemon as fainted)
    # This would require tracking which Pokemon are linked and updating
    # their party status across all players
    
    return None  # Faint events don't create new entities with IDs