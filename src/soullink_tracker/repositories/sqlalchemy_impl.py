"""SQLAlchemy concrete implementations of repository interfaces."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc

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


class BaseSQLAlchemyRepository:
    """Base SQLAlchemy repository implementation."""

    def __init__(self, session: Session):
        self._session = session

    async def save(self, entity) -> None:
        """Save an entity to the repository."""
        self._session.add(entity)

    async def delete(self, entity) -> None:
        """Delete an entity from the repository."""
        self._session.delete(entity)

    async def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()


class SQLAlchemyRunRepository(BaseSQLAlchemyRepository, RunRepository):
    """SQLAlchemy implementation of RunRepository."""

    async def get_by_id(self, run_id: UUID) -> Optional[Run]:
        """Get a run by ID."""
        return self._session.query(Run).filter(Run.id == run_id).first()

    async def get_by_name(self, name: str) -> Optional[Run]:
        """Get a run by name."""
        return self._session.query(Run).filter(Run.name == name).first()

    async def create(self, name: str, rules_json: Dict[str, Any] = None) -> Run:
        """Create a new run."""
        run = Run(
            name=name,
            rules_json=rules_json or {},
        )
        await self.save(run)
        await self.commit()
        self._session.refresh(run)
        return run

    async def list_all(self) -> List[Run]:
        """Get all runs."""
        return self._session.query(Run).order_by(desc(Run.created_at)).all()


class SQLAlchemyPlayerRepository(BaseSQLAlchemyRepository, PlayerRepository):
    """SQLAlchemy implementation of PlayerRepository."""

    async def get_by_id(self, player_id: UUID) -> Optional[Player]:
        """Get a player by ID."""
        return self._session.query(Player).filter(Player.id == player_id).first()

    async def get_by_token_hash(self, token_hash: str) -> Optional[Player]:
        """Get a player by token hash."""
        return self._session.query(Player).filter(Player.token_hash == token_hash).first()

    async def get_by_run_id(self, run_id: UUID) -> List[Player]:
        """Get all players for a run."""
        return (
            self._session.query(Player)
            .filter(Player.run_id == run_id)
            .order_by(Player.created_at)
            .all()
        )

    async def get_by_run_and_name(self, run_id: UUID, name: str) -> Optional[Player]:
        """Get a player by run and name."""
        return (
            self._session.query(Player)
            .filter(and_(Player.run_id == run_id, Player.name == name))
            .first()
        )

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
            run_id=run_id,
            name=name,
            game=game,
            region=region,
            token_hash=token_hash,
        )
        await self.save(player)
        await self.commit()
        self._session.refresh(player)
        return player


class SQLAlchemyEncounterRepository(BaseSQLAlchemyRepository, EncounterRepository):
    """SQLAlchemy implementation of EncounterRepository."""

    async def get_by_id(self, encounter_id: UUID) -> Optional[Encounter]:
        """Get an encounter by ID."""
        return (
            self._session.query(Encounter)
            .options(joinedload(Encounter.species), joinedload(Encounter.route))
            .filter(Encounter.id == encounter_id)
            .first()
        )

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
        query = (
            self._session.query(Encounter)
            .options(
                joinedload(Encounter.species),
                joinedload(Encounter.route),
                joinedload(Encounter.player)
            )
            .filter(Encounter.run_id == run_id)
        )

        if player_id:
            query = query.filter(Encounter.player_id == player_id)
        if route_id:
            query = query.filter(Encounter.route_id == route_id)
        if species_id:
            query = query.filter(Encounter.species_id == species_id)
        if family_id:
            query = query.filter(Encounter.family_id == family_id)
        if status:
            query = query.filter(Encounter.status == status.value)
        if method:
            query = query.filter(Encounter.method == method)
        if shiny is not None:
            query = query.filter(Encounter.shiny == shiny)

        return (
            query
            .order_by(desc(Encounter.time))
            .limit(limit)
            .offset(offset)
            .all()
        )

    async def get_first_encounter_by_route_player(
        self, run_id: UUID, player_id: UUID, route_id: int
    ) -> Optional[Encounter]:
        """Get the first encounter for a player on a route."""
        return (
            self._session.query(Encounter)
            .filter(
                and_(
                    Encounter.run_id == run_id,
                    Encounter.player_id == player_id,
                    Encounter.route_id == route_id,
                )
            )
            .order_by(Encounter.time)
            .first()
        )

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
        await self.save(encounter)
        await self.commit()
        self._session.refresh(encounter)
        return encounter

    async def update_status(self, encounter_id: UUID, status: EncounterStatus) -> bool:
        """Update encounter status."""
        result = (
            self._session.query(Encounter)
            .filter(Encounter.id == encounter_id)
            .update({"status": status.value})
        )
        await self.commit()
        return result > 0


class SQLAlchemySpeciesRepository(BaseSQLAlchemyRepository, SpeciesRepository):
    """SQLAlchemy implementation of SpeciesRepository."""

    async def get_by_id(self, species_id: int) -> Optional[Species]:
        """Get a species by ID."""
        return self._session.query(Species).filter(Species.id == species_id).first()

    async def get_by_family_id(self, family_id: int) -> List[Species]:
        """Get all species in an evolution family."""
        return (
            self._session.query(Species)
            .filter(Species.family_id == family_id)
            .order_by(Species.id)
            .all()
        )

    async def list_all(self) -> List[Species]:
        """Get all species."""
        return self._session.query(Species).order_by(Species.id).all()


class SQLAlchemyRouteRepository(BaseSQLAlchemyRepository, RouteRepository):
    """SQLAlchemy implementation of RouteRepository."""

    async def get_by_id(self, route_id: int) -> Optional[Route]:
        """Get a route by ID."""
        return self._session.query(Route).filter(Route.id == route_id).first()

    async def get_by_region(self, region: str) -> List[Route]:
        """Get all routes for a region."""
        return (
            self._session.query(Route)
            .filter(Route.region == region)
            .order_by(Route.id)
            .all()
        )

    async def list_all(self) -> List[Route]:
        """Get all routes."""
        return self._session.query(Route).order_by(Route.id).all()


class SQLAlchemyLinkRepository(BaseSQLAlchemyRepository, LinkRepository):
    """SQLAlchemy implementation of LinkRepository."""

    async def get_by_id(self, link_id: UUID) -> Optional[Link]:
        """Get a link by ID."""
        return (
            self._session.query(Link)
            .options(joinedload(Link.members))
            .filter(Link.id == link_id)
            .first()
        )

    async def get_by_run_route(self, run_id: UUID, route_id: int) -> Optional[Link]:
        """Get a link for a specific run and route."""
        return (
            self._session.query(Link)
            .options(joinedload(Link.members))
            .filter(and_(Link.run_id == run_id, Link.route_id == route_id))
            .first()
        )

    async def get_by_run_id(self, run_id: UUID) -> List[Link]:
        """Get all links for a run."""
        return (
            self._session.query(Link)
            .options(joinedload(Link.members))
            .filter(Link.run_id == run_id)
            .order_by(Link.route_id)
            .all()
        )

    async def create(self, run_id: UUID, route_id: int) -> Link:
        """Create a new link."""
        link = Link(run_id=run_id, route_id=route_id)
        await self.save(link)
        await self.commit()
        self._session.refresh(link)
        return link


class SQLAlchemyLinkMemberRepository(BaseSQLAlchemyRepository, LinkMemberRepository):
    """SQLAlchemy implementation of LinkMemberRepository."""

    async def get_by_link_id(self, link_id: UUID) -> List[LinkMember]:
        """Get all members of a link."""
        return (
            self._session.query(LinkMember)
            .options(
                joinedload(LinkMember.player),
                joinedload(LinkMember.encounter),
            )
            .filter(LinkMember.link_id == link_id)
            .all()
        )

    async def create(
        self, link_id: UUID, player_id: UUID, encounter_id: UUID
    ) -> LinkMember:
        """Create a new link member."""
        link_member = LinkMember(
            link_id=link_id,
            player_id=player_id,
            encounter_id=encounter_id,
        )
        await self.save(link_member)
        await self.commit()
        self._session.refresh(link_member)
        return link_member


class SQLAlchemyBlocklistRepository(BaseSQLAlchemyRepository, BlocklistRepository):
    """SQLAlchemy implementation of BlocklistRepository."""

    async def get_by_run_id(self, run_id: UUID) -> List[Blocklist]:
        """Get all blocklist entries for a run."""
        return (
            self._session.query(Blocklist)
            .filter(Blocklist.run_id == run_id)
            .order_by(Blocklist.created_at)
            .all()
        )

    async def is_family_blocked(self, run_id: UUID, family_id: int) -> bool:
        """Check if a family is blocked for a run."""
        return (
            self._session.query(Blocklist)
            .filter(
                and_(
                    Blocklist.run_id == run_id,
                    Blocklist.family_id == family_id,
                )
            )
            .first()
            is not None
        )

    async def create(
        self, run_id: UUID, family_id: int, origin: str
    ) -> Blocklist:
        """Create a new blocklist entry."""
        blocklist_entry = Blocklist(
            run_id=run_id,
            family_id=family_id,
            origin=origin,
        )
        await self.save(blocklist_entry)
        await self.commit()
        self._session.refresh(blocklist_entry)
        return blocklist_entry


class SQLAlchemyPartyStatusRepository(BaseSQLAlchemyRepository, PartyStatusRepository):
    """SQLAlchemy implementation of PartyStatusRepository."""

    async def get_by_player(
        self, run_id: UUID, player_id: UUID
    ) -> List[PartyStatus]:
        """Get party status for a player."""
        return (
            self._session.query(PartyStatus)
            .filter(
                and_(
                    PartyStatus.run_id == run_id,
                    PartyStatus.player_id == player_id,
                )
            )
            .order_by(PartyStatus.last_update)
            .all()
        )

    async def get_by_pokemon_key(
        self, run_id: UUID, player_id: UUID, pokemon_key: str
    ) -> Optional[PartyStatus]:
        """Get status for a specific Pokemon."""
        return (
            self._session.query(PartyStatus)
            .filter(
                and_(
                    PartyStatus.run_id == run_id,
                    PartyStatus.player_id == player_id,
                    PartyStatus.pokemon_key == pokemon_key,
                )
            )
            .first()
        )

    async def upsert(
        self,
        run_id: UUID,
        player_id: UUID,
        pokemon_key: str,
        alive: bool,
    ) -> PartyStatus:
        """Create or update party status."""
        existing = await self.get_by_pokemon_key(run_id, player_id, pokemon_key)
        
        if existing:
            existing.alive = alive
            existing.last_update = datetime.now(timezone.utc)
            await self.commit()
            return existing
        else:
            party_status = PartyStatus(
                run_id=run_id,
                player_id=player_id,
                pokemon_key=pokemon_key,
                alive=alive,
            )
            await self.save(party_status)
            await self.commit()
            self._session.refresh(party_status)
            return party_status


class SQLAlchemyIdempotencyKeyRepository(BaseSQLAlchemyRepository, IdempotencyKeyRepository):
    """SQLAlchemy implementation of IdempotencyKeyRepository."""

    async def get_by_key(
        self,
        key: str,
        run_id: UUID,
        player_id: UUID,
        request_hash: str,
    ) -> Optional[IdempotencyKey]:
        """Get an idempotency key record."""
        return (
            self._session.query(IdempotencyKey)
            .filter(
                and_(
                    IdempotencyKey.key == key,
                    IdempotencyKey.run_id == run_id,
                    IdempotencyKey.player_id == player_id,
                    IdempotencyKey.request_hash == request_hash,
                )
            )
            .first()
        )

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
        )
        await self.save(idempotency_key)
        await self.commit()
        self._session.refresh(idempotency_key)
        return idempotency_key

    async def cleanup_expired(self, before_date: datetime) -> int:
        """Clean up expired idempotency keys."""
        result = (
            self._session.query(IdempotencyKey)
            .filter(IdempotencyKey.created_at < before_date)
            .delete()
        )
        await self.commit()
        return result


class SQLAlchemyEventRepository(BaseSQLAlchemyRepository, EventRepository):
    """SQLAlchemy implementation of EventRepository."""

    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get an event by ID."""
        return self._session.query(Event).filter(Event.id == event_id).first()

    async def get_by_run_since_seq(
        self, run_id: UUID, since_seq: int = 0, limit: int = 100
    ) -> List[Event]:
        """Get events for a run since a sequence number."""
        return (
            self._session.query(Event)
            .filter(
                and_(
                    Event.run_id == run_id,
                    Event.seq > since_seq,
                )
            )
            .order_by(Event.seq)
            .limit(limit)
            .all()
        )

    async def create(
        self,
        run_id: UUID,
        player_id: UUID,
        event_type: str,
        payload_json: Dict[str, Any],
    ) -> Event:
        """Create a new event."""
        # Get next sequence number
        next_seq = await self.get_next_sequence(run_id)
        
        event = Event(
            run_id=run_id,
            player_id=player_id,
            type=event_type,
            payload_json=payload_json,
            seq=next_seq,
        )
        await self.save(event)
        await self.commit()
        self._session.refresh(event)
        return event

    async def get_next_sequence(self, run_id: UUID) -> int:
        """Get the next sequence number for a run."""
        max_seq = (
            self._session.query(func.max(Event.seq))
            .filter(Event.run_id == run_id)
            .scalar()
        )
        return (max_seq or 0) + 1


class SQLAlchemyRouteProgressRepository(BaseSQLAlchemyRepository, RouteProgressRepository):
    """SQLAlchemy implementation of RouteProgressRepository."""

    async def get_by_player_route(
        self, player_id: UUID, run_id: UUID, route_id: int
    ) -> Optional[RouteProgress]:
        """Get route progress for a player."""
        return (
            self._session.query(RouteProgress)
            .filter(
                and_(
                    RouteProgress.player_id == player_id,
                    RouteProgress.run_id == run_id,
                    RouteProgress.route_id == route_id,
                )
            )
            .first()
        )

    async def get_by_run_id(self, run_id: UUID) -> List[RouteProgress]:
        """Get all route progress for a run."""
        return (
            self._session.query(RouteProgress)
            .options(
                joinedload(RouteProgress.player),
                joinedload(RouteProgress.route),
            )
            .filter(RouteProgress.run_id == run_id)
            .order_by(RouteProgress.route_id, RouteProgress.player_id)
            .all()
        )

    async def upsert(
        self,
        player_id: UUID,
        run_id: UUID,
        route_id: int,
        fe_finalized: bool,
    ) -> RouteProgress:
        """Create or update route progress."""
        existing = await self.get_by_player_route(player_id, run_id, route_id)
        
        if existing:
            existing.fe_finalized = fe_finalized
            existing.last_update = datetime.now(timezone.utc)
            await self.commit()
            return existing
        else:
            route_progress = RouteProgress(
                player_id=player_id,
                run_id=run_id,
                route_id=route_id,
                fe_finalized=fe_finalized,
            )
            await self.save(route_progress)
            await self.commit()
            self._session.refresh(route_progress)
            return route_progress