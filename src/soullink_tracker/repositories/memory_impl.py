"""In-memory implementations of repository interfaces for testing."""

from typing import List, Optional, Dict, Any, Set
from uuid import UUID, uuid4
from datetime import datetime, timezone

from .interfaces import (
    RunRepository,
    PlayerRepository,
    EncounterRepository,
    SpeciesRepository,
    RouteRepository,
    LinkRepository,
    LinkMemberRepository,
    BlocklistRepository,
    PartyStatusRepository,
    IdempotencyKeyRepository,
    EventRepository,
    RouteProgressRepository,
)
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


class BaseMemoryRepository:
    """Base in-memory repository implementation."""

    def __init__(self):
        self._committed_changes: Set = set()

    async def save(self, entity) -> None:
        """Save an entity to the repository."""
        # In memory implementation doesn't need explicit saves
        pass

    async def delete(self, entity) -> None:
        """Delete an entity from the repository."""
        # Handled by specific implementations
        pass

    async def commit(self) -> None:
        """Commit the current transaction."""
        # In memory - changes are immediate
        pass

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        # In memory - no rollback needed for simple case
        pass


class MemoryRunRepository(BaseMemoryRepository, RunRepository):
    """In-memory implementation of RunRepository."""

    def __init__(self):
        super().__init__()
        self._runs: Dict[UUID, Run] = {}

    async def get_by_id(self, run_id: UUID) -> Optional[Run]:
        """Get a run by ID."""
        return self._runs.get(run_id)

    async def get_by_name(self, name: str) -> Optional[Run]:
        """Get a run by name."""
        for run in self._runs.values():
            if run.name == name:
                return run
        return None

    async def create(self, name: str, rules_json: Dict[str, Any] = None) -> Run:
        """Create a new run."""
        run = Run(
            id=uuid4(),
            name=name,
            rules_json=rules_json or {},
            created_at=datetime.now(timezone.utc),
        )
        self._runs[run.id] = run
        return run

    async def list_all(self) -> List[Run]:
        """Get all runs."""
        return list(self._runs.values())


class MemoryPlayerRepository(BaseMemoryRepository, PlayerRepository):
    """In-memory implementation of PlayerRepository."""

    def __init__(self):
        super().__init__()
        self._players: Dict[UUID, Player] = {}
        self._token_hash_index: Dict[str, UUID] = {}

    async def get_by_id(self, player_id: UUID) -> Optional[Player]:
        """Get a player by ID."""
        return self._players.get(player_id)

    async def get_by_token_hash(self, token_hash: str) -> Optional[Player]:
        """Get a player by token hash."""
        player_id = self._token_hash_index.get(token_hash)
        if player_id:
            return self._players.get(player_id)
        return None

    async def get_by_run_id(self, run_id: UUID) -> List[Player]:
        """Get all players for a run."""
        return [
            player for player in self._players.values()
            if player.run_id == run_id
        ]

    async def get_by_run_and_name(self, run_id: UUID, name: str) -> Optional[Player]:
        """Get a player by run and name."""
        for player in self._players.values():
            if player.run_id == run_id and player.name == name:
                return player
        return None

    async def create(
        self,
        run_id: UUID,
        name: str,
        game: str,
        region: str,
        token_hash: str,
    ) -> Player:
        """Create a new player."""
        player = Player(
            id=uuid4(),
            run_id=run_id,
            name=name,
            game=game,
            region=region,
            token_hash=token_hash,
            created_at=datetime.now(timezone.utc),
        )
        self._players[player.id] = player
        self._token_hash_index[token_hash] = player.id
        return player


class MemoryEncounterRepository(BaseMemoryRepository, EncounterRepository):
    """In-memory implementation of EncounterRepository."""

    def __init__(self):
        super().__init__()
        self._encounters: Dict[UUID, Encounter] = {}

    async def get_by_id(self, encounter_id: UUID) -> Optional[Encounter]:
        """Get an encounter by ID."""
        return self._encounters.get(encounter_id)

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
        encounters = [
            encounter for encounter in self._encounters.values()
            if encounter.run_id == run_id
        ]

        # Apply filters
        if player_id:
            encounters = [e for e in encounters if e.player_id == player_id]
        if route_id:
            encounters = [e for e in encounters if e.route_id == route_id]
        if species_id:
            encounters = [e for e in encounters if e.species_id == species_id]
        if family_id:
            encounters = [e for e in encounters if e.family_id == family_id]
        if status:
            encounters = [e for e in encounters if e.status == status.value]
        if method:
            encounters = [e for e in encounters if e.method == method]
        if shiny is not None:
            encounters = [e for e in encounters if e.shiny == shiny]

        # Sort by time descending
        encounters.sort(key=lambda x: x.time, reverse=True)
        
        # Apply pagination
        return encounters[offset:offset + limit]

    async def get_first_encounter_by_route_player(
        self, run_id: UUID, player_id: UUID, route_id: int
    ) -> Optional[Encounter]:
        """Get the first encounter for a player on a route."""
        encounters = [
            encounter for encounter in self._encounters.values()
            if (encounter.run_id == run_id and 
                encounter.player_id == player_id and 
                encounter.route_id == route_id)
        ]
        
        if encounters:
            encounters.sort(key=lambda x: x.time)
            return encounters[0]
        return None

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
        encounter = Encounter(
            id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            route_id=route_id,
            species_id=species_id,
            family_id=family_id,
            level=level,
            shiny=shiny,
            method=method,
            rod_kind=rod_kind,
            time=time,
            status=status.value,
            dupes_skip=dupes_skip,
            fe_finalized=fe_finalized,
        )
        self._encounters[encounter.id] = encounter
        return encounter

    async def update_status(self, encounter_id: UUID, status: EncounterStatus) -> bool:
        """Update encounter status."""
        encounter = self._encounters.get(encounter_id)
        if encounter:
            encounter.status = status.value
            return True
        return False


class MemorySpeciesRepository(BaseMemoryRepository, SpeciesRepository):
    """In-memory implementation of SpeciesRepository."""

    def __init__(self):
        super().__init__()
        self._species: Dict[int, Species] = {}
        self._family_index: Dict[int, List[int]] = {}

    def _add_species(self, species: Species) -> None:
        """Helper to add species and update family index."""
        self._species[species.id] = species
        if species.family_id not in self._family_index:
            self._family_index[species.family_id] = []
        self._family_index[species.family_id].append(species.id)

    async def get_by_id(self, species_id: int) -> Optional[Species]:
        """Get a species by ID."""
        return self._species.get(species_id)

    async def get_by_family_id(self, family_id: int) -> List[Species]:
        """Get all species in an evolution family."""
        species_ids = self._family_index.get(family_id, [])
        return [self._species[sid] for sid in species_ids]

    async def list_all(self) -> List[Species]:
        """Get all species."""
        return list(self._species.values())


class MemoryRouteRepository(BaseMemoryRepository, RouteRepository):
    """In-memory implementation of RouteRepository."""

    def __init__(self):
        super().__init__()
        self._routes: Dict[int, Route] = {}
        self._region_index: Dict[str, List[int]] = {}

    def _add_route(self, route: Route) -> None:
        """Helper to add route and update region index."""
        self._routes[route.id] = route
        if route.region not in self._region_index:
            self._region_index[route.region] = []
        self._region_index[route.region].append(route.id)

    async def get_by_id(self, route_id: int) -> Optional[Route]:
        """Get a route by ID."""
        return self._routes.get(route_id)

    async def get_by_region(self, region: str) -> List[Route]:
        """Get all routes for a region."""
        route_ids = self._region_index.get(region, [])
        return [self._routes[rid] for rid in route_ids]

    async def list_all(self) -> List[Route]:
        """Get all routes."""
        return list(self._routes.values())


class MemoryLinkRepository(BaseMemoryRepository, LinkRepository):
    """In-memory implementation of LinkRepository."""

    def __init__(self):
        super().__init__()
        self._links: Dict[UUID, Link] = {}
        self._run_route_index: Dict[tuple, UUID] = {}  # (run_id, route_id) -> link_id

    async def get_by_id(self, link_id: UUID) -> Optional[Link]:
        """Get a link by ID."""
        return self._links.get(link_id)

    async def get_by_run_route(self, run_id: UUID, route_id: int) -> Optional[Link]:
        """Get a link for a specific run and route."""
        link_id = self._run_route_index.get((run_id, route_id))
        if link_id:
            return self._links.get(link_id)
        return None

    async def get_by_run_id(self, run_id: UUID) -> List[Link]:
        """Get all links for a run."""
        return [link for link in self._links.values() if link.run_id == run_id]

    async def create(self, run_id: UUID, route_id: int) -> Link:
        """Create a new link."""
        link = Link(id=uuid4(), run_id=run_id, route_id=route_id)
        self._links[link.id] = link
        self._run_route_index[(run_id, route_id)] = link.id
        return link


class MemoryLinkMemberRepository(BaseMemoryRepository, LinkMemberRepository):
    """In-memory implementation of LinkMemberRepository."""

    def __init__(self):
        super().__init__()
        self._link_members: Dict[tuple, LinkMember] = {}  # (link_id, player_id) -> LinkMember
        self._link_index: Dict[UUID, List[tuple]] = {}  # link_id -> [(link_id, player_id), ...]

    async def get_by_link_id(self, link_id: UUID) -> List[LinkMember]:
        """Get all members of a link."""
        member_keys = self._link_index.get(link_id, [])
        return [self._link_members[key] for key in member_keys]

    async def create(
        self, link_id: UUID, player_id: UUID, encounter_id: UUID
    ) -> LinkMember:
        """Create a new link member."""
        link_member = LinkMember(
            link_id=link_id,
            player_id=player_id,
            encounter_id=encounter_id,
        )
        
        key = (link_id, player_id)
        self._link_members[key] = link_member
        
        if link_id not in self._link_index:
            self._link_index[link_id] = []
        self._link_index[link_id].append(key)
        
        return link_member


class MemoryBlocklistRepository(BaseMemoryRepository, BlocklistRepository):
    """In-memory implementation of BlocklistRepository."""

    def __init__(self):
        super().__init__()
        self._blocklist: Dict[tuple, Blocklist] = {}  # (run_id, family_id) -> Blocklist
        self._run_index: Dict[UUID, List[tuple]] = {}  # run_id -> [(run_id, family_id), ...]

    async def get_by_run_id(self, run_id: UUID) -> List[Blocklist]:
        """Get all blocklist entries for a run."""
        entry_keys = self._run_index.get(run_id, [])
        return [self._blocklist[key] for key in entry_keys]

    async def is_family_blocked(self, run_id: UUID, family_id: int) -> bool:
        """Check if a family is blocked for a run."""
        return (run_id, family_id) in self._blocklist

    async def create(self, run_id: UUID, family_id: int, origin: str) -> Blocklist:
        """Create a new blocklist entry."""
        blocklist_entry = Blocklist(
            run_id=run_id,
            family_id=family_id,
            origin=origin,
            created_at=datetime.now(timezone.utc),
        )
        
        key = (run_id, family_id)
        self._blocklist[key] = blocklist_entry
        
        if run_id not in self._run_index:
            self._run_index[run_id] = []
        self._run_index[run_id].append(key)
        
        return blocklist_entry


class MemoryPartyStatusRepository(BaseMemoryRepository, PartyStatusRepository):
    """In-memory implementation of PartyStatusRepository."""

    def __init__(self):
        super().__init__()
        self._party_status: Dict[tuple, PartyStatus] = {}  # (run_id, player_id, pokemon_key) -> PartyStatus
        self._player_index: Dict[tuple, List[tuple]] = {}  # (run_id, player_id) -> [keys, ...]

    async def get_by_player(self, run_id: UUID, player_id: UUID) -> List[PartyStatus]:
        """Get party status for a player."""
        status_keys = self._player_index.get((run_id, player_id), [])
        return [self._party_status[key] for key in status_keys]

    async def get_by_pokemon_key(
        self, run_id: UUID, player_id: UUID, pokemon_key: str
    ) -> Optional[PartyStatus]:
        """Get status for a specific Pokemon."""
        return self._party_status.get((run_id, player_id, pokemon_key))

    async def upsert(
        self, run_id: UUID, player_id: UUID, pokemon_key: str, alive: bool,
    ) -> PartyStatus:
        """Create or update party status."""
        key = (run_id, player_id, pokemon_key)
        
        existing = self._party_status.get(key)
        if existing:
            existing.alive = alive
            existing.last_update = datetime.now(timezone.utc)
            return existing
        else:
            party_status = PartyStatus(
                run_id=run_id,
                player_id=player_id,
                pokemon_key=pokemon_key,
                alive=alive,
                last_update=datetime.now(timezone.utc),
            )
            
            self._party_status[key] = party_status
            
            player_key = (run_id, player_id)
            if player_key not in self._player_index:
                self._player_index[player_key] = []
            self._player_index[player_key].append(key)
            
            return party_status


class MemoryIdempotencyKeyRepository(BaseMemoryRepository, IdempotencyKeyRepository):
    """In-memory implementation of IdempotencyKeyRepository."""

    def __init__(self):
        super().__init__()
        self._keys: Dict[tuple, IdempotencyKey] = {}  # (key, run_id, player_id, request_hash) -> IdempotencyKey

    async def get_by_key(
        self, key: str, run_id: UUID, player_id: UUID, request_hash: str,
    ) -> Optional[IdempotencyKey]:
        """Get an idempotency key record."""
        return self._keys.get((key, run_id, player_id, request_hash))

    async def create(
        self,
        key: str,
        run_id: UUID,
        player_id: UUID,
        request_hash: str,
        response_json: Dict[str, Any],
    ) -> IdempotencyKey:
        """Create a new idempotency key record."""
        idempotency_key = IdempotencyKey(
            key=key,
            run_id=run_id,
            player_id=player_id,
            request_hash=request_hash,
            response_json=response_json,
            created_at=datetime.now(timezone.utc),
        )
        
        key_tuple = (key, run_id, player_id, request_hash)
        self._keys[key_tuple] = idempotency_key
        return idempotency_key

    async def cleanup_expired(self, before_date: datetime) -> int:
        """Clean up expired idempotency keys."""
        expired_keys = [
            key for key, record in self._keys.items()
            if record.created_at < before_date
        ]
        
        for key in expired_keys:
            del self._keys[key]
            
        return len(expired_keys)


class MemoryEventRepository(BaseMemoryRepository, EventRepository):
    """In-memory implementation of EventRepository."""

    def __init__(self):
        super().__init__()
        self._events: Dict[UUID, Event] = {}
        self._run_sequence: Dict[UUID, int] = {}  # run_id -> max_seq
        self._run_events: Dict[UUID, List[UUID]] = {}  # run_id -> [event_ids...]

    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get an event by ID."""
        return self._events.get(event_id)

    async def get_by_run_since_seq(
        self, run_id: UUID, since_seq: int = 0, limit: int = 100
    ) -> List[Event]:
        """Get events for a run since a sequence number."""
        event_ids = self._run_events.get(run_id, [])
        events = [
            self._events[event_id] for event_id in event_ids
            if self._events[event_id].seq > since_seq
        ]
        events.sort(key=lambda x: x.seq)
        return events[:limit]

    async def create(
        self,
        run_id: UUID,
        player_id: UUID,
        event_type: str,
        payload_json: Dict[str, Any],
    ) -> Event:
        """Create a new event."""
        next_seq = await self.get_next_sequence(run_id)
        
        event = Event(
            id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            type=event_type,
            payload_json=payload_json,
            seq=next_seq,
            created_at=datetime.now(timezone.utc),
        )
        
        self._events[event.id] = event
        self._run_sequence[run_id] = next_seq
        
        if run_id not in self._run_events:
            self._run_events[run_id] = []
        self._run_events[run_id].append(event.id)
        
        return event

    async def get_next_sequence(self, run_id: UUID) -> int:
        """Get the next sequence number for a run."""
        current_max = self._run_sequence.get(run_id, 0)
        return current_max + 1


class MemoryRouteProgressRepository(BaseMemoryRepository, RouteProgressRepository):
    """In-memory implementation of RouteProgressRepository."""

    def __init__(self):
        super().__init__()
        self._progress: Dict[tuple, RouteProgress] = {}  # (player_id, run_id, route_id) -> RouteProgress
        self._run_index: Dict[UUID, List[tuple]] = {}  # run_id -> [keys...]

    async def get_by_player_route(
        self, player_id: UUID, run_id: UUID, route_id: int
    ) -> Optional[RouteProgress]:
        """Get route progress for a player."""
        return self._progress.get((player_id, run_id, route_id))

    async def get_by_run_id(self, run_id: UUID) -> List[RouteProgress]:
        """Get all route progress for a run."""
        progress_keys = self._run_index.get(run_id, [])
        return [self._progress[key] for key in progress_keys]

    async def upsert(
        self, player_id: UUID, run_id: UUID, route_id: int, fe_finalized: bool,
    ) -> RouteProgress:
        """Create or update route progress."""
        key = (player_id, run_id, route_id)
        
        existing = self._progress.get(key)
        if existing:
            existing.fe_finalized = fe_finalized
            existing.last_update = datetime.now(timezone.utc)
            return existing
        else:
            route_progress = RouteProgress(
                player_id=player_id,
                run_id=run_id,
                route_id=route_id,
                fe_finalized=fe_finalized,
                last_update=datetime.now(timezone.utc),
            )
            
            self._progress[key] = route_progress
            
            if run_id not in self._run_index:
                self._run_index[run_id] = []
            self._run_index[run_id].append(key)
            
            return route_progress