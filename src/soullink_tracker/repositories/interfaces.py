"""Abstract repository interfaces for data access layer."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from ..db.models import (
    Run,
    Player,
    Encounter,
    Species,
    Route,
    Link,
    LinkMember,
    Blocklist,
    PartyStatus,
    IdempotencyKey,
    Event,
    RouteProgress,
)
from ..core.enums import EncounterStatus


class BaseRepository(ABC):
    """Base repository interface with common operations."""

    @abstractmethod
    async def save(self, entity) -> None:
        """Save an entity to the repository."""
        pass

    @abstractmethod
    async def delete(self, entity) -> None:
        """Delete an entity from the repository."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass


class RunRepository(BaseRepository):
    """Repository interface for Run entities."""

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> Optional[Run]:
        """Get a run by ID."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Run]:
        """Get a run by name."""
        pass

    @abstractmethod
    async def create(self, name: str, rules_json: Dict[str, Any] = None) -> Run:
        """Create a new run."""
        pass

    @abstractmethod
    async def list_all(self) -> List[Run]:
        """Get all runs."""
        pass


class PlayerRepository(BaseRepository):
    """Repository interface for Player entities."""

    @abstractmethod
    async def get_by_id(self, player_id: UUID) -> Optional[Player]:
        """Get a player by ID."""
        pass

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> Optional[Player]:
        """Get a player by token hash."""
        pass

    @abstractmethod
    async def get_by_run_id(self, run_id: UUID) -> List[Player]:
        """Get all players for a run."""
        pass

    @abstractmethod
    async def get_by_run_and_name(self, run_id: UUID, name: str) -> Optional[Player]:
        """Get a player by run and name."""
        pass

    @abstractmethod
    async def create(
        self,
        run_id: UUID,
        name: str,
        game: str,
        region: str,
        token_hash: str,
    ) -> Player:
        """Create a new player."""
        pass


class EncounterRepository(BaseRepository):
    """Repository interface for Encounter entities."""

    @abstractmethod
    async def get_by_id(self, encounter_id: UUID) -> Optional[Encounter]:
        """Get an encounter by ID."""
        pass

    @abstractmethod
    async def get_by_run_id(
        self,
        run_id: UUID,
        player_id: Optional[UUID] = None,
        route_id: Optional[int] = None,
        species_id: Optional[int] = None,
        family_id: Optional[int] = None,
        status: Optional[EncounterStatus] = None,
        method: Optional[str] = None,
        shiny: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Encounter]:
        """Get encounters for a run with filtering."""
        pass

    @abstractmethod
    async def get_first_encounter_by_route_player(
        self, run_id: UUID, player_id: UUID, route_id: int
    ) -> Optional[Encounter]:
        """Get the first encounter for a player on a route."""
        pass

    @abstractmethod
    async def create(
        self,
        run_id: UUID,
        player_id: UUID,
        route_id: int,
        species_id: int,
        family_id: int,
        level: int,
        shiny: bool,
        method: str,
        rod_kind: Optional[str],
        time: datetime,
        status: EncounterStatus,
        dupes_skip: bool = False,
        fe_finalized: bool = False,
    ) -> Encounter:
        """Create a new encounter."""
        pass

    @abstractmethod
    async def update_status(self, encounter_id: UUID, status: EncounterStatus) -> bool:
        """Update encounter status."""
        pass


class SpeciesRepository(BaseRepository):
    """Repository interface for Species entities."""

    @abstractmethod
    async def get_by_id(self, species_id: int) -> Optional[Species]:
        """Get a species by ID."""
        pass

    @abstractmethod
    async def get_by_family_id(self, family_id: int) -> List[Species]:
        """Get all species in an evolution family."""
        pass

    @abstractmethod
    async def list_all(self) -> List[Species]:
        """Get all species."""
        pass


class RouteRepository(BaseRepository):
    """Repository interface for Route entities."""

    @abstractmethod
    async def get_by_id(self, route_id: int) -> Optional[Route]:
        """Get a route by ID."""
        pass

    @abstractmethod
    async def get_by_region(self, region: str) -> List[Route]:
        """Get all routes for a region."""
        pass

    @abstractmethod
    async def list_all(self) -> List[Route]:
        """Get all routes."""
        pass


class LinkRepository(BaseRepository):
    """Repository interface for Link entities."""

    @abstractmethod
    async def get_by_id(self, link_id: UUID) -> Optional[Link]:
        """Get a link by ID."""
        pass

    @abstractmethod
    async def get_by_run_route(self, run_id: UUID, route_id: int) -> Optional[Link]:
        """Get a link for a specific run and route."""
        pass

    @abstractmethod
    async def get_by_run_id(self, run_id: UUID) -> List[Link]:
        """Get all links for a run."""
        pass

    @abstractmethod
    async def create(self, run_id: UUID, route_id: int) -> Link:
        """Create a new link."""
        pass


class LinkMemberRepository(BaseRepository):
    """Repository interface for LinkMember entities."""

    @abstractmethod
    async def get_by_link_id(self, link_id: UUID) -> List[LinkMember]:
        """Get all members of a link."""
        pass

    @abstractmethod
    async def create(
        self, link_id: UUID, player_id: UUID, encounter_id: UUID
    ) -> LinkMember:
        """Create a new link member."""
        pass


class BlocklistRepository(BaseRepository):
    """Repository interface for Blocklist entities."""

    @abstractmethod
    async def get_by_run_id(self, run_id: UUID) -> List[Blocklist]:
        """Get all blocklist entries for a run."""
        pass

    @abstractmethod
    async def is_family_blocked(self, run_id: UUID, family_id: int) -> bool:
        """Check if a family is blocked for a run."""
        pass

    @abstractmethod
    async def create(
        self, run_id: UUID, family_id: int, origin: str
    ) -> Blocklist:
        """Create a new blocklist entry."""
        pass


class PartyStatusRepository(BaseRepository):
    """Repository interface for PartyStatus entities."""

    @abstractmethod
    async def get_by_player(
        self, run_id: UUID, player_id: UUID
    ) -> List[PartyStatus]:
        """Get party status for a player."""
        pass

    @abstractmethod
    async def get_by_pokemon_key(
        self, run_id: UUID, player_id: UUID, pokemon_key: str
    ) -> Optional[PartyStatus]:
        """Get status for a specific Pokemon."""
        pass

    @abstractmethod
    async def upsert(
        self,
        run_id: UUID,
        player_id: UUID,
        pokemon_key: str,
        alive: bool,
    ) -> PartyStatus:
        """Create or update party status."""
        pass


class IdempotencyKeyRepository(BaseRepository):
    """Repository interface for IdempotencyKey entities."""

    @abstractmethod
    async def get_by_key(
        self,
        key: str,
        run_id: UUID,
        player_id: UUID,
        request_hash: str,
    ) -> Optional[IdempotencyKey]:
        """Get an idempotency key record."""
        pass

    @abstractmethod
    async def create(
        self,
        key: str,
        run_id: UUID,
        player_id: UUID,
        request_hash: str,
        response_json: Dict[str, Any],
    ) -> IdempotencyKey:
        """Create a new idempotency key record."""
        pass

    @abstractmethod
    async def cleanup_expired(self, before_date: datetime) -> int:
        """Clean up expired idempotency keys."""
        pass


class EventRepository(BaseRepository):
    """Repository interface for Event entities (v3 event store)."""

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get an event by ID."""
        pass

    @abstractmethod
    async def get_by_run_since_seq(
        self, run_id: UUID, since_seq: int = 0, limit: int = 100
    ) -> List[Event]:
        """Get events for a run since a sequence number."""
        pass

    @abstractmethod
    async def create(
        self,
        run_id: UUID,
        player_id: UUID,
        event_type: str,
        payload_json: Dict[str, Any],
    ) -> Event:
        """Create a new event."""
        pass

    @abstractmethod
    async def get_next_sequence(self, run_id: UUID) -> int:
        """Get the next sequence number for a run."""
        pass


class RouteProgressRepository(BaseRepository):
    """Repository interface for RouteProgress entities (v3 projections)."""

    @abstractmethod
    async def get_by_player_route(
        self, player_id: UUID, run_id: UUID, route_id: int
    ) -> Optional[RouteProgress]:
        """Get route progress for a player."""
        pass

    @abstractmethod
    async def get_by_run_id(self, run_id: UUID) -> List[RouteProgress]:
        """Get all route progress for a run."""
        pass

    @abstractmethod
    async def upsert(
        self,
        player_id: UUID,
        run_id: UUID,
        route_id: int,
        fe_finalized: bool,
    ) -> RouteProgress:
        """Create or update route progress."""
        pass


class RepositoryContainer:
    """Container for all repository interfaces to support dependency injection."""

    def __init__(
        self,
        run_repo: RunRepository,
        player_repo: PlayerRepository,
        encounter_repo: EncounterRepository,
        species_repo: SpeciesRepository,
        route_repo: RouteRepository,
        link_repo: LinkRepository,
        link_member_repo: LinkMemberRepository,
        blocklist_repo: BlocklistRepository,
        party_status_repo: PartyStatusRepository,
        idempotency_key_repo: IdempotencyKeyRepository,
        event_repo: EventRepository,
        route_progress_repo: RouteProgressRepository,
    ):
        self.run = run_repo
        self.player = player_repo
        self.encounter = encounter_repo
        self.species = species_repo
        self.route = route_repo
        self.link = link_repo
        self.link_member = link_member_repo
        self.blocklist = blocklist_repo
        self.party_status = party_status_repo
        self.idempotency_key = idempotency_key_repo
        self.event = event_repo
        self.route_progress = route_progress_repo