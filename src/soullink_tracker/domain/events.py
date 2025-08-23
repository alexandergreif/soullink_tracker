"""Domain event contracts for the v3 event sourcing architecture.

This module defines typed event contracts that represent all state changes
in the SoulLink tracker system. Events are immutable and append-only.
"""

from abc import abstractmethod
from datetime import datetime, timezone
from typing import Union, Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict  # type: ignore

from ..core.enums import EncounterMethod, EncounterStatus, RodKind


class BaseEvent(BaseModel):
    """Base class for all domain events."""

    model_config = ConfigDict(
        frozen=True,  # Events are immutable
        extra="forbid",
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
    )

    # Event metadata
    event_id: UUID
    run_id: UUID
    player_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Return the event type identifier."""
        pass


class EncounterEvent(BaseEvent):
    """A Pokemon encounter has occurred."""

    # Encounter details
    route_id: int
    species_id: int
    family_id: int
    level: int
    shiny: bool = False
    encounter_method: EncounterMethod
    rod_kind: Optional[RodKind] = None

    # Computed status (determined by rules engine)
    status: EncounterStatus
    dupes_skip: bool = False
    fe_finalized: bool = False

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "encounter"


class CatchResultEvent(BaseEvent):
    """Result of attempting to catch an encountered Pokemon."""

    model_config = {"populate_by_name": True}

    # Reference to the encounter
    encounter_id: UUID
    result: EncounterStatus = Field(..., alias="status")

    @property
    def status(self) -> EncounterStatus:
        """Alias for result field for backward compatibility."""
        return self.result

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "catch_result"


class FaintEvent(BaseEvent):
    """A Pokemon has fainted."""

    # Pokemon identification
    pokemon_key: str = Field(
        ..., description="Personality value or hash identifying the Pokemon"
    )
    party_index: Optional[int] = Field(None, description="Position in party (0-5)")

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "faint"


class SoulLinkCreatedEvent(BaseEvent):
    """A soul link has been created between Pokemon on the same route."""

    link_id: UUID
    route_id: int
    linked_players: list[UUID] = Field(
        ..., description="Player IDs participating in the link"
    )

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "soul_link_created"


class SoulLinkBrokenEvent(BaseEvent):
    """A soul link has been broken due to a faint."""

    link_id: UUID
    route_id: int
    affected_players: list[UUID] = Field(
        ..., description="All players affected by the break"
    )

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "soul_link_broken"


class FirstEncounterFinalizedEvent(BaseEvent):
    """A first encounter has been finalized for a route."""

    route_id: int
    player_id: UUID = Field(..., description="Player who finalized the first encounter")

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "first_encounter_finalized"


class FamilyBlockedEvent(BaseEvent):
    """An evolution family has been blocked from future catches."""

    family_id: int
    origin: Literal["first_encounter", "caught", "faint"] = Field(
        ..., description="Reason for the block"
    )

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "family_blocked"


# Union type for all possible events
DomainEvent = Union[
    EncounterEvent,
    CatchResultEvent,
    FaintEvent,
    SoulLinkCreatedEvent,
    SoulLinkBrokenEvent,
    FamilyBlockedEvent,
    FirstEncounterFinalizedEvent,
]


class EventEnvelope(BaseModel):
    """Event store envelope containing event with metadata."""

    model_config = ConfigDict(frozen=True)

    # Event store metadata
    sequence_number: int = Field(..., description="Global sequence number")
    stored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Event payload
    event: DomainEvent

    @property
    def event_type(self) -> str:
        """Return the event type for the wrapped event."""
        return self.event.event_type

    @property
    def run_id(self) -> UUID:
        """Return the run ID for the wrapped event."""
        return self.event.run_id

    @property
    def player_id(self) -> UUID:
        """Return the player ID for the wrapped event."""
        return self.event.player_id


class EventStoreRecord(BaseModel):
    """Database record representation of a stored event."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
    )

    id: UUID
    run_id: UUID
    player_id: UUID
    event_type: str
    payload_json: dict
    created_at: datetime
    sequence_number: int
