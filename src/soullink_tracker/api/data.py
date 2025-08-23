"""Data retrieval API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from ..repositories.dependencies import get_repository_container
from ..repositories.interfaces import RepositoryContainer
from ..core.enums import EncounterStatus
from .schemas import (
    EncounterListResponse,
    EncounterResponse,
    BlocklistResponse,
    BlocklistEntry,
    LinkListResponse,
    LinkResponse,
    LinkMemberResponse,
    RouteStatusResponse,
    RouteStatusEntry,
    ProblemDetails,
)

router = APIRouter(tags=["data"])


@router.get(
    "/v1/runs/{run_id}/encounters",
    response_model=EncounterListResponse,
    responses={
        200: {"description": "Encounters retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        422: {"model": ProblemDetails, "description": "Invalid parameters"},
    },
)
async def get_encounters(
    run_id: UUID,
    player_id: Optional[UUID] = Query(None, description="Filter by player ID"),
    route_id: Optional[int] = Query(None, description="Filter by route ID"),
    species_id: Optional[int] = Query(None, description="Filter by species ID"),
    family_id: Optional[int] = Query(None, description="Filter by evolution family ID"),
    status: Optional[EncounterStatus] = Query(
        None, description="Filter by encounter status"
    ),
    method: Optional[str] = Query(None, description="Filter by encounter method"),
    shiny: Optional[bool] = Query(None, description="Filter by shiny status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    repos: RepositoryContainer = Depends(get_repository_container),
) -> EncounterListResponse:
    """
    Get encounters for a run with optional filtering and pagination.

    Returns detailed encounter information including related entity names
    (player name, route label, species name) for easy display.
    """
    # Verify run exists using repository
    run = await repos.run.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Get encounters using repository with filters
    encounters = await repos.encounter.get_by_run_id(
        run_id=run_id,
        player_id=player_id,
        route_id=route_id,
        species_id=species_id,
        family_id=family_id,
        status=status,
        method=method,
        shiny=shiny,
        limit=limit,
        offset=offset,
    )
    
    # For now, we'll approximate total count as len(encounters)
    # TODO: Add proper count method to repository interface
    total = len(encounters)

    # Build response
    encounter_responses = []
    for encounter in encounters:
        # Get related entities for display names
        # Note: The SQLAlchemy implementation should have used joinedload for efficiency
        player = encounter.player if hasattr(encounter, 'player') else await repos.player.get_by_id(encounter.player_id)
        route = encounter.route if hasattr(encounter, 'route') else await repos.route.get_by_id(encounter.route_id)
        species = encounter.species if hasattr(encounter, 'species') else await repos.species.get_by_id(encounter.species_id)
        
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
            "player_name": player.name if player else "Unknown",
            "route_label": route.label if route else "Unknown",
            "species_name": species.name if species else "Unknown",
        }
        encounter_responses.append(EncounterResponse.model_validate(encounter_dict))

    return EncounterListResponse(
        encounters=encounter_responses, total=total, limit=limit, offset=offset
    )


@router.get(
    "/v1/runs/{run_id}/blocklist",
    response_model=BlocklistResponse,
    responses={
        200: {"description": "Blocklist retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
    },
)
async def get_blocklist(
    run_id: UUID,
    repos: RepositoryContainer = Depends(get_repository_container)
) -> BlocklistResponse:
    """
    Get the global blocklist for a run.

    Returns all evolution families that are blocked (already encountered/caught)
    along with the species names in each family.
    """
    # Verify run exists using repository
    run = await repos.run.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Get blocklist entries using repository
    blocklist_entries = await repos.blocklist.get_by_run_id(run_id)

    # Get all unique family IDs to batch load species data
    family_ids = list(set(entry.family_id for entry in blocklist_entries))

    # Batch load all species for all families to prevent N+1 queries
    species_by_family = {}
    for family_id in family_ids:
        family_species = await repos.species.get_by_family_id(family_id)
        species_by_family[family_id] = [species.name for species in family_species]

    blocked_families = []
    for entry in blocklist_entries:
        species_names = species_by_family.get(entry.family_id, [])

        blocked_entry = BlocklistEntry(
            family_id=entry.family_id,
            origin=entry.origin,
            created_at=entry.created_at,
            species_names=species_names,
        )
        blocked_families.append(blocked_entry)

    return BlocklistResponse(blocked_families=blocked_families)


@router.get(
    "/v1/runs/{run_id}/links",
    response_model=LinkListResponse,
    responses={
        200: {"description": "Soul links retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
    },
)
async def get_links(
    run_id: UUID,
    repos: RepositoryContainer = Depends(get_repository_container)
) -> LinkListResponse:
    """
    Get all soul links for a run.

    Returns groups of Pokemon that are soul-linked (caught on the same route
    by different players). If one Pokemon in a soul link faints, all linked
    Pokemon are considered dead.
    """
    # Verify run exists using repository
    run = await repos.run.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Get links using repository
    links = await repos.link.get_by_run_id(run_id)

    link_responses = []
    for link in links:
        # Get link members using repository
        members = await repos.link_member.get_by_link_id(link.id)
        
        # Build member responses
        member_responses = []
        for member in members:
            # Get related data using repositories
            player = member.player if hasattr(member, 'player') else await repos.player.get_by_id(member.player_id)
            encounter = member.encounter if hasattr(member, 'encounter') else await repos.encounter.get_by_id(member.encounter_id)
            species = encounter.species if hasattr(encounter, 'species') else await repos.species.get_by_id(encounter.species_id)
            
            member_data = LinkMemberResponse(
                player_id=member.player_id,
                player_name=player.name if player else "Unknown",
                encounter_id=member.encounter_id,
                species_id=encounter.species_id,
                species_name=species.name if species else "Unknown",
                level=encounter.level,
                shiny=encounter.shiny,
                status=encounter.status,
            )
            member_responses.append(member_data)

        # Get route using repository
        route = link.route if hasattr(link, 'route') else await repos.route.get_by_id(link.route_id)
        
        link_data = LinkResponse(
            id=link.id,
            route_id=link.route_id,
            route_label=route.label if route else "Unknown",
            members=member_responses,
        )
        link_responses.append(link_data)

    return LinkListResponse(links=link_responses)


@router.get(
    "/v1/runs/{run_id}/routes/status",
    response_model=RouteStatusResponse,
    responses={
        200: {"description": "Route status matrix retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
    },
)
async def get_route_status(
    run_id: UUID,
    repos: RepositoryContainer = Depends(get_repository_container)
) -> RouteStatusResponse:
    """
    Get the route status matrix for a run.

    Returns a matrix showing which routes each player has encountered/caught
    Pokemon on. This gives a quick overview of run progress.
    """
    # Verify run exists using repository
    run = await repos.run.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Get all players in the run using repository
    players = await repos.player.get_by_run_id(run_id)

    # Build player lookup for faster access
    players_by_id = {player.id: player.name for player in players}

    # Get all caught encounters using repository
    encounters = await repos.encounter.get_by_run_id(
        run_id=run_id,
        status=EncounterStatus.CAUGHT,
        limit=10000,  # Large limit to get all caught encounters
    )

    # Group encounters by route for efficient processing
    encounters_by_route = {}
    for encounter in encounters:
        route_id = encounter.route_id
        if route_id not in encounters_by_route:
            # Get route info using repository if not already loaded
            route = encounter.route if hasattr(encounter, 'route') else await repos.route.get_by_id(route_id)
            encounters_by_route[route_id] = {"route": route, "encounters": []}
        encounters_by_route[route_id]["encounters"].append(encounter)

    route_statuses = []
    for route_id, route_data in encounters_by_route.items():
        players_status = {}

        # Initialize all players with None (no encounter)
        for player_name in players_by_id.values():
            players_status[player_name] = None

        # Update status for players who caught something on this route
        for encounter in route_data["encounters"]:
            # Get player and species info using repositories if not already loaded
            player = encounter.player if hasattr(encounter, 'player') else await repos.player.get_by_id(encounter.player_id)
            species = encounter.species if hasattr(encounter, 'species') else await repos.species.get_by_id(encounter.species_id)
            
            player_name = player.name if player else "Unknown"
            species_name = species.name if species else "Unknown"
            players_status[player_name] = species_name

        route_entry = RouteStatusEntry(
            route_id=route_id,
            route_label=route_data["route"].label if route_data["route"] else "Unknown",
            players_status=players_status,
        )
        route_statuses.append(route_entry)

    # Sort routes by ID for consistent ordering
    route_statuses.sort(key=lambda x: x.route_id)

    return RouteStatusResponse(routes=route_statuses)
