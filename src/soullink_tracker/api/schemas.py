"""Pydantic models for API request/response validation."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, model_validator  # type: ignore

from ..core.enums import EncounterMethod, EncounterStatus, RodKind


# Base response models
class BaseResponse(BaseModel):
    """Base response model with common fields."""

    model_config = ConfigDict(from_attributes=True)


class ProblemDetails(BaseModel):
    """RFC 9457 Problem Details for HTTP APIs."""

    type: str = Field(description="A URI reference that identifies the problem type")
    title: str = Field(
        description="A short, human-readable summary of the problem type"
    )
    status: int = Field(description="The HTTP status code")
    detail: Optional[str] = Field(
        None, description="A human-readable explanation specific to this occurrence"
    )
    instance: Optional[str] = Field(
        None, description="A URI reference that identifies the specific occurrence"
    )


# Authentication schemas
class LoginRequest(BaseModel):
    """Schema for login request."""

    run_id: Optional[UUID] = Field(
        None, description="UUID of the run (alternative to run_name)"
    )
    run_name: Optional[str] = Field(
        None, description="Name of the run (alternative to run_id)"
    )
    player_name: str = Field(description="Player name", min_length=1, max_length=100)
    password: str = Field(description="Run password", min_length=1)


class LoginResponse(BaseModel):
    """Schema for login response."""

    session_token: str = Field(description="Session token for API authentication")
    run_id: UUID = Field(description="UUID of the run")
    player_id: UUID = Field(description="UUID of the player")
    expires_at: datetime = Field(description="Token expiration timestamp")


class JWTTokenResponse(BaseModel):
    """Schema for JWT token response."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    access_expires_at: datetime = Field(description="Access token expiration timestamp")
    refresh_expires_at: datetime = Field(
        description="Refresh token expiration timestamp"
    )
    run_id: UUID = Field(description="UUID of the run")
    player_id: UUID = Field(description="UUID of the player")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(description="JWT refresh token")


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response."""

    access_token: str = Field(description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_at: datetime = Field(description="Access token expiration timestamp")


# Run-related schemas
class RunCreate(BaseModel):
    """Schema for creating a new run."""

    name: str = Field(description="Name of the run", min_length=1, max_length=255)
    password: Optional[str] = Field(
        None, description="Password for run access", min_length=1
    )
    rules_json: Dict = Field(
        default_factory=dict, description="Run rules configuration"
    )


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

    name: str = Field(description="Player name", min_length=1, max_length=100)
    game: Optional[str] = Field(None, description="Game version (HeartGold/SoulSilver)")
    region: Optional[str] = Field(None, description="Game region (EU/US/JP)")


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

    new_token: str = Field(description="Bearer token for this player (shown only once)")


class PlayerListResponse(BaseResponse):
    """Schema for listing players."""

    players: List[PlayerResponse]


# Event-related schemas with V2/V3 compatibility
class EventEncounter(BaseModel):
    """Schema for encounter event with V2/V3 compatibility."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    type: str = Field("encounter", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime
    route_id: int
    species_id: int
    level: int
    shiny: bool = False

    # V3 canonical field
    method: EncounterMethod = Field(description="Encounter method")

    # V2 legacy field (aliased to method)
    encounter_method: Optional[EncounterMethod] = Field(
        None, alias="method", description="V2 legacy: encounter method"
    )

    rod_kind: Optional[RodKind] = None

    @model_validator(mode="before")
    @classmethod
    def handle_v2_v3_compatibility(cls, values):
        """Handle V2 to V3 format transformation."""
        if isinstance(values, dict):
            # Handle encounter_method -> method transformation
            if "encounter_method" in values and "method" not in values:
                values["method"] = values["encounter_method"]
            elif "method" not in values and "encounter_method" not in values:
                # Neither field provided, validation will catch this
                pass

            # String to enum coercion for method
            method_value = values.get("method")
            if isinstance(method_value, str):
                try:
                    values["method"] = EncounterMethod(method_value.strip().lower())
                except ValueError:
                    # Let normal validation handle invalid enum values
                    pass

            # String to enum coercion for rod_kind
            rod_kind_value = values.get("rod_kind")
            if isinstance(rod_kind_value, str):
                try:
                    values["rod_kind"] = RodKind(rod_kind_value.strip().lower())
                except ValueError:
                    # Let normal validation handle invalid enum values
                    pass

        return values

    @model_validator(mode="after")
    def validate_fishing_requirements(self):
        """Validate that fishing encounters have rod_kind."""
        if self.method == EncounterMethod.FISH and self.rod_kind is None:
            raise ValueError("Fishing encounters must specify rod_kind")
        return self


class EventCatchResult(BaseModel):
    """Schema for catch result event."""

    model_config = {"populate_by_name": True}

    type: str = Field("catch_result", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime

    # Support both V2 legacy format and V3 format
    encounter_id: Optional[UUID] = Field(
        None, description="V3: Direct reference to encounter event"
    )
    encounter_ref: Optional[Dict[str, int]] = Field(
        None, description="V2 legacy: Route/species reference"
    )

    # Support both field names for backward compatibility
    result: Optional[EncounterStatus] = Field(
        None, description="V3: Result of the catch attempt"
    )
    status: Optional[EncounterStatus] = Field(
        None, description="V2 legacy: Status of catch attempt", alias="result"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_catch_result_fields(cls, values):
        """Custom validation with V2/V3 compatibility and enum coercion."""
        if isinstance(values, dict):
            encounter_id = values.get("encounter_id")
            encounter_ref = values.get("encounter_ref")
            result = values.get("result")
            status = values.get("status")

            # Ensure we have an encounter reference
            if not encounter_id and not encounter_ref:
                raise ValueError(
                    "Either encounter_id or encounter_ref must be provided"
                )

            # Handle status/result field compatibility
            if status and not result:
                values["result"] = status
            elif result and not status:
                values["status"] = result
            elif not result and not status:
                raise ValueError("Either result or status must be provided")

            # String to enum coercion for result/status fields
            for field in ["result", "status"]:
                field_value = values.get(field)
                if isinstance(field_value, str):
                    try:
                        values[field] = EncounterStatus(field_value.strip().lower())
                    except ValueError:
                        # Let normal validation handle invalid enum values
                        pass

        return values


class EventFaint(BaseModel):
    """Schema for faint event."""

    type: str = Field("faint", description="Event type")
    run_id: UUID
    player_id: UUID
    time: datetime
    pokemon_key: str = Field(description="Personality value or unique identifier")
    party_index: Optional[int] = Field(
        None, description="Position in party (0-5), optional for backward compatibility"
    )


class EventResponse(BaseResponse):
    """Schema for event processing response."""

    message: str = Field("Event processed successfully")
    event_id: Optional[UUID] = None
    seq: Optional[int] = Field(None, description="Sequence number for encounter events")
    applied_rules: List[str] = Field(
        default_factory=list, description="Rules that were applied"
    )


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
    origin: str = Field(
        description="How this family was blocked (first_encounter or caught)"
    )
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


class EventCatchUpEntry(BaseModel):
    """Schema for individual event in catch-up response."""

    event_id: UUID
    seq: int = Field(description="Sequence number")
    type: str = Field(description="Event type")
    timestamp: datetime
    player_id: UUID
    data: Dict = Field(description="Event payload data")


class EventCatchUpResponse(BaseResponse):
    """Schema for catch-up events response."""

    events: List[EventCatchUpEntry]
    total: int = Field(description="Total number of events returned")
    latest_seq: int = Field(description="Latest sequence number in this run")
    has_more: bool = Field(description="Whether there are more events beyond the limit")


# Health and info schemas
class HealthResponse(BaseResponse):
    """Schema for health check response."""

    status: str = "healthy"
    service: str = "soullink-tracker"
    version: str
