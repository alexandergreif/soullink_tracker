"""Data retrieval API endpoints."""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..db.database import get_db
from ..db.models import (
    Run, Player, Species, Route, Encounter, Link, LinkMember, 
    Blocklist, PartyStatus
)
from ..core.enums import EncounterStatus
from .schemas import (
    EncounterFilter, EncounterListResponse, EncounterResponse,
    BlocklistResponse, BlocklistEntry,
    LinkListResponse, LinkResponse, LinkMemberResponse,
    RouteStatusResponse, RouteStatusEntry,
    ProblemDetails
)

router = APIRouter(tags=["data"])


@router.get(
    "/v1/runs/{run_id}/encounters",
    response_model=EncounterListResponse,
    responses={
        200: {"description": "Encounters retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        422: {"model": ProblemDetails, "description": "Invalid parameters"}
    }
)
def get_encounters(
    run_id: UUID,
    player_id: Optional[UUID] = Query(None, description="Filter by player ID"),
    route_id: Optional[int] = Query(None, description="Filter by route ID"),
    species_id: Optional[int] = Query(None, description="Filter by species ID"),
    family_id: Optional[int] = Query(None, description="Filter by evolution family ID"),
    status: Optional[EncounterStatus] = Query(None, description="Filter by encounter status"),
    method: Optional[str] = Query(None, description="Filter by encounter method"),
    shiny: Optional[bool] = Query(None, description="Filter by shiny status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
) -> EncounterListResponse:
    """
    Get encounters for a run with optional filtering and pagination.
    
    Returns detailed encounter information including related entity names
    (player name, route label, species name) for easy display.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Build query with joins for related data
    query = db.query(Encounter).filter(Encounter.run_id == run_id)
    query = query.join(Player).join(Route).join(Species)
    
    # Apply filters
    if player_id:
        query = query.filter(Encounter.player_id == player_id)
    if route_id:
        query = query.filter(Encounter.route_id == route_id)
    if species_id:
        query = query.filter(Encounter.species_id == species_id)
    if family_id:
        query = query.filter(Encounter.family_id == family_id)
    if status:
        query = query.filter(Encounter.status == status)
    if method:
        query = query.filter(Encounter.method == method)
    if shiny is not None:
        query = query.filter(Encounter.shiny == shiny)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    encounters = query.order_by(Encounter.time.desc()).offset(offset).limit(limit).all()
    
    # Build response
    encounter_responses = []
    for encounter in encounters:
        # Create base encounter data
        encounter_dict = {
            "id": encounter.id,
            "run_id": encounter.run_id,
            "player_id": encounter.player_id,
            "route_id": encounter.route_id,
            "species_id": encounter.species_id,
            "family_id": encounter.family_id,
            "level": encounter.level,
            "shiny": encounter.shiny,
            "method": encounter.method,
            "rod_kind": encounter.rod_kind,
            "time": encounter.time,
            "status": encounter.status,
            "dupes_skip": encounter.dupes_skip,
            "fe_finalized": encounter.fe_finalized,
            "player_name": encounter.player.name,
            "route_label": encounter.route.label,
            "species_name": encounter.species.name
        }
        encounter_responses.append(EncounterResponse.model_validate(encounter_dict))
    
    return EncounterListResponse(
        encounters=encounter_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get(
    "/v1/runs/{run_id}/blocklist",
    response_model=BlocklistResponse,
    responses={
        200: {"description": "Blocklist retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"}
    }
)
def get_blocklist(
    run_id: UUID,
    db: Session = Depends(get_db)
) -> BlocklistResponse:
    """
    Get the global blocklist for a run.
    
    Returns all evolution families that are blocked (already encountered/caught)
    along with the species names in each family.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Get blocklist entries with species names
    blocklist_entries = db.query(Blocklist).filter(
        Blocklist.run_id == run_id
    ).order_by(Blocklist.created_at.desc()).all()
    
    blocked_families = []
    for entry in blocklist_entries:
        # Get all species in this family
        species_in_family = db.query(Species).filter(
            Species.family_id == entry.family_id
        ).all()
        
        species_names = [species.name for species in species_in_family]
        
        blocked_entry = BlocklistEntry(
            family_id=entry.family_id,
            origin=entry.origin,
            created_at=entry.created_at,
            species_names=species_names
        )
        blocked_families.append(blocked_entry)
    
    return BlocklistResponse(blocked_families=blocked_families)


@router.get(
    "/v1/runs/{run_id}/links",
    response_model=LinkListResponse,
    responses={
        200: {"description": "Soul links retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"}
    }
)
def get_links(
    run_id: UUID,
    db: Session = Depends(get_db)
) -> LinkListResponse:
    """
    Get all soul links for a run.
    
    Returns groups of Pokemon that are soul-linked (caught on the same route
    by different players). If one Pokemon in a soul link faints, all linked
    Pokemon are considered dead.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Get links with members
    links = db.query(Link).filter(Link.run_id == run_id).options(
        joinedload(Link.members).joinedload(LinkMember.player),
        joinedload(Link.members).joinedload(LinkMember.encounter).joinedload(Encounter.species),
        joinedload(Link.route)
    ).all()
    
    link_responses = []
    for link in links:
        # Build member responses
        member_responses = []
        for member in link.members:
            member_data = LinkMemberResponse(
                player_id=member.player_id,
                player_name=member.player.name,
                encounter_id=member.encounter_id,
                species_id=member.encounter.species_id,
                species_name=member.encounter.species.name,
                level=member.encounter.level,
                shiny=member.encounter.shiny,
                status=member.encounter.status
            )
            member_responses.append(member_data)
        
        link_data = LinkResponse(
            id=link.id,
            route_id=link.route_id,
            route_label=link.route.label,
            members=member_responses
        )
        link_responses.append(link_data)
    
    return LinkListResponse(links=link_responses)


@router.get(
    "/v1/runs/{run_id}/routes/status",
    response_model=RouteStatusResponse,
    responses={
        200: {"description": "Route status matrix retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"}
    }
)
def get_route_status(
    run_id: UUID,
    db: Session = Depends(get_db)
) -> RouteStatusResponse:
    """
    Get the route status matrix for a run.
    
    Returns a matrix showing which routes each player has encountered/caught
    Pokemon on. This gives a quick overview of run progress.
    """
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    # Get all players in the run
    players = db.query(Player).filter(Player.run_id == run_id).all()
    player_names = {player.id: player.name for player in players}
    
    # Get all routes that have encounters in this run
    routes_with_encounters = db.query(Route).join(Encounter).filter(
        Encounter.run_id == run_id
    ).distinct().all()
    
    route_statuses = []
    for route in routes_with_encounters:
        players_status = {}
        
        # Initialize all players with None (no encounter)
        for player in players:
            players_status[player.name] = None
        
        # Get encounters for this route
        encounters = db.query(Encounter).filter(
            Encounter.run_id == run_id,
            Encounter.route_id == route.id,
            Encounter.status == EncounterStatus.CAUGHT
        ).join(Species).join(Player).all()
        
        # Update status for players who caught something
        for encounter in encounters:
            player_name = encounter.player.name
            species_name = encounter.species.name
            players_status[player_name] = species_name
        
        route_entry = RouteStatusEntry(
            route_id=route.id,
            route_label=route.label,
            players_status=players_status
        )
        route_statuses.append(route_entry)
    
    # Sort routes by ID for consistent ordering
    route_statuses.sort(key=lambda x: x.route_id)
    
    return RouteStatusResponse(routes=route_statuses)