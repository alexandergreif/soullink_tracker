"""Pydantic models for API request/response validation."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from pydantic.types import constr

from ..core.enums import EncounterMethod, EncounterStatus, RodKind, GameVersion, Region


# Base response models
class BaseResponse(BaseModel):
    """Base response model with common fields."""
    model_config = ConfigDict(from_attributes=True)


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs."""
    type: str = Field(description="A URI reference that identifies the problem type")
    title: str = Field(description="A short, human-readable summary of the problem type")
    status: int = Field(description="The HTTP status code")
    detail: Optional[str] = Field(None, description="A human-readable explanation specific to this occurrence")
    instance: Optional[str] = Field(None, description="A URI reference that identifies the specific occurrence")


# Run-related schemas
class RunCreate(BaseModel):
    """Schema for creating a new run."""
    name: constr(min_length=1, max_length=255) = Field(description="Name of the run")
    rules_json: Dict = Field(default_factory=dict, description="Run rules configuration")


class RunResponse(BaseResponse):
    """Schema for run response."""
    id: UUID
    name: str
    rules_json: Dict
    created_at: datetime


class RunListResponse(BaseResponse):
    """Schema for listing runs."""
    runs: List[RunResponse]


# Player-related schemas
class PlayerCreate(BaseModel):
    """Schema for creating a new player."""
    name: constr(min_length=1, max_length=100) = Field(description="Player name")
    game: GameVersion = Field(description="Game version (HeartGold/SoulSilver)")
    region: Region = Field(description="Game region (EU/US/JP)")


class PlayerResponse(BaseResponse):
    """Schema for player response."""
    id: UUID
    run_id: UUID
    name: str
    game: str
    region: str
    created_at: datetime


class PlayerWithTokenResponse(PlayerResponse):
    """Schema for player response including token (only returned once)."""
    player_token: str = Field(description="Bearer token for this player (shown only once)")


class PlayerListResponse(BaseResponse):
    """Schema for listing players."""
    players: List[PlayerResponse]


# Event-related schemas
class EventEncounter(BaseModel):
    """Schema for encounter event."""
    type: str = Field("encounter", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime
    route_id: int
    species_id: int
    level: int
    shiny: bool = False
    method: EncounterMethod
    rod_kind: Optional[RodKind] = None


class EventCatchResult(BaseModel):
    """Schema for catch result event."""
    type: str = Field("catch_result", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime
    encounter_id: UUID
    result: EncounterStatus = Field(description="Result of the catch attempt")


class EventFaint(BaseModel):
    """Schema for faint event."""
    type: str = Field("faint", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime
    pokemon_key: str = Field(description="Personality value or unique identifier")


class EventResponse(BaseResponse):
    """Schema for event processing response."""
    message: str = Field("Event processed successfully")
    event_id: Optional[UUID] = None
    applied_rules: List[str] = Field(default_factory=list, description="Rules that were applied")


# Data retrieval schemas
class EncounterFilter(BaseModel):
    """Schema for filtering encounters."""
    player_id: Optional[UUID] = None
    route_id: Optional[int] = None
    species_id: Optional[int] = None
    family_id: Optional[int] = None
    status: Optional[EncounterStatus] = None
    method: Optional[EncounterMethod] = None
    shiny: Optional[bool] = None
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class EncounterResponse(BaseResponse):
    """Schema for encounter response."""
    id: UUID
    run_id: UUID
    player_id: UUID
    route_id: int
    species_id: int
    family_id: int
    level: int
    shiny: bool
    method: str
    rod_kind: Optional[str]
    time: datetime
    status: str
    dupes_skip: bool
    fe_finalized: bool
    
    # Related data
    player_name: str
    route_label: str
    species_name: str


class EncounterListResponse(BaseResponse):
    """Schema for listing encounters."""
    encounters: List[EncounterResponse]
    total: int = Field(description="Total number of encounters matching filter")
    limit: int
    offset: int


class BlocklistEntry(BaseResponse):
    """Schema for blocklist entry."""
    family_id: int
    origin: str = Field(description="How this family was blocked (first_encounter or caught)")
    created_at: datetime
    species_names: List[str] = Field(description="Names of species in this family")


class BlocklistResponse(BaseResponse):
    """Schema for blocklist response."""
    blocked_families: List[BlocklistEntry]


class LinkMemberResponse(BaseResponse):
    """Schema for link member response."""
    player_id: UUID
    player_name: str
    encounter_id: UUID
    species_id: int
    species_name: str
    level: int
    shiny: bool
    status: str


class LinkResponse(BaseResponse):
    """Schema for soul link response."""
    id: UUID
    route_id: int
    route_label: str
    members: List[LinkMemberResponse]


class LinkListResponse(BaseResponse):
    """Schema for listing soul links."""
    links: List[LinkResponse]


class RouteStatusEntry(BaseResponse):
    """Schema for route status entry."""
    route_id: int
    route_label: str
    players_status: Dict[str, Optional[str]] = Field(
        description="Status per player name (species caught or None)"
    )


class RouteStatusResponse(BaseResponse):
    """Schema for route status matrix."""
    routes: List[RouteStatusEntry]


# WebSocket schemas
class WebSocketEvent(BaseModel):
    """Schema for WebSocket events."""
    type: str = Field(description="Event type")
    run_id: UUID
    timestamp: datetime
    data: Dict = Field(description="Event-specific data")


# Health and info schemas
class HealthResponse(BaseResponse):
    """Schema for health check response."""
    status: str = "healthy"
    service: str = "soullink-tracker"
    version: str