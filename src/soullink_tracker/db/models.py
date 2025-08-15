"""SQLAlchemy models for the SoulLink tracker."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR

from .database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type using String for SQLite."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, UUID):
                return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, UUID):
                return UUID(value)
            return value


class Run(Base):
    """A SoulLink run containing multiple players."""

    __tablename__ = "runs"

    id = Column(GUID(), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    rules_json = Column(JSON, nullable=False, default=dict)
    password_hash = Column(String(255), nullable=True)  # Password-based auth
    password_salt = Column(String(64), nullable=True)   # Salt for password hashing
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    players = relationship("Player", back_populates="run", cascade="all, delete-orphan")
    sessions = relationship("PlayerSession", back_populates="run", cascade="all, delete-orphan")
    encounters = relationship(
        "Encounter", back_populates="run", cascade="all, delete-orphan"
    )
    links = relationship("Link", back_populates="run", cascade="all, delete-orphan")
    blocklist_entries = relationship(
        "Blocklist", back_populates="run", cascade="all, delete-orphan"
    )
    party_statuses = relationship(
        "PartyStatus", back_populates="run", cascade="all, delete-orphan"
    )
    idempotency_keys = relationship(
        "IdempotencyKey", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Run(id={self.id}, name='{self.name}')>"


class Player(Base):
    """A player in a SoulLink run."""

    __tablename__ = "players"

    id = Column(GUID(), primary_key=True, default=uuid4)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    name = Column(String(100), nullable=False)
    game = Column(String(50), nullable=False)  # HeartGold/SoulSilver
    region = Column(String(10), nullable=False)  # EU/US/JP
    token_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("Run", back_populates="players")
    sessions = relationship("PlayerSession", back_populates="player", cascade="all, delete-orphan")
    encounters = relationship(
        "Encounter", back_populates="player", cascade="all, delete-orphan"
    )
    link_members = relationship(
        "LinkMember", back_populates="player", cascade="all, delete-orphan"
    )
    party_statuses = relationship(
        "PartyStatus", back_populates="player", cascade="all, delete-orphan"
    )
    idempotency_keys = relationship(
        "IdempotencyKey", back_populates="player", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("run_id", "name", name="uq_player_name_per_run"),
        Index("ix_player_token_hash", "token_hash"),
    )

    def verify_token(self, token: str) -> bool:
        """Verify a bearer token against the stored hash."""
        from ..auth.security import verify_bearer_token

        return verify_bearer_token(token, self.token_hash)

    @classmethod
    def generate_token(cls) -> tuple[str, str]:
        """Generate a new token and its hash."""
        from ..auth.security import generate_secure_token

        return generate_secure_token()

    def rotate_token(self) -> str:
        """
        Generate a new token for this player, replacing the old one.

        Returns:
            str: The new plain token (should be returned to user immediately)
        """
        token, token_hash = self.generate_token()
        self.token_hash = token_hash
        return token

    @classmethod
    def create_with_token(
        cls,
        db_session,
        run_id: UUID,
        name: str,
        game: str = None,
        region: str = None,
    ) -> tuple["Player", str]:
        """
        Create a new player with a generated token.

        Args:
            db_session: SQLAlchemy session
            run_id: UUID of the run
            name: Player name
            game: Game version (optional)
            region: Game region (optional)

        Returns:
            tuple: (Player instance, raw_token)
        """
        token, token_hash = cls.generate_token()
        player = cls(
            run_id=run_id,
            name=name,
            game=game or "Unknown",
            region=region or "Unknown",
            token_hash=token_hash,
        )
        db_session.add(player)
        db_session.commit()
        db_session.refresh(player)
        return player, token

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name='{self.name}', game='{self.game}')>"


class PlayerSession(Base):
    """Session tokens for player authentication."""

    __tablename__ = "player_sessions"

    id = Column(GUID(), primary_key=True, default=uuid4)
    token_hash = Column(String(64), nullable=False, unique=True)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    player_id = Column(GUID(), ForeignKey("players.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("Run", back_populates="sessions")
    player = relationship("Player", back_populates="sessions")

    __table_args__ = (
        Index("ix_player_session_token_hash", "token_hash"),
        Index("ix_player_session_expires_at", "expires_at"),
        Index("ix_player_session_run_player", "run_id", "player_id"),
    )

    def __repr__(self) -> str:
        return f"<PlayerSession(id={self.id}, player_id={self.player_id}, expires_at={self.expires_at})>"


class Species(Base):
    """Pokemon species reference data."""

    __tablename__ = "species"

    id = Column(Integer, primary_key=True)  # National Dex ID
    name = Column(String(100), nullable=False)
    family_id = Column(Integer, nullable=False)  # Evolution family ID

    # Relationships
    encounters = relationship("Encounter", back_populates="species")

    __table_args__ = (Index("ix_species_family_id", "family_id"),)

    def __repr__(self) -> str:
        return (
            f"<Species(id={self.id}, name='{self.name}', family_id={self.family_id})>"
        )


class Route(Base):
    """Game route/location reference data."""

    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False)  # "Route 31", "Violet City", etc.
    region = Column(String(10), nullable=False)  # EU/US/JP

    # Relationships
    encounters = relationship("Encounter", back_populates="route")
    links = relationship("Link", back_populates="route")

    def __repr__(self) -> str:
        return f"<Route(id={self.id}, label='{self.label}', region='{self.region}')>"


class Encounter(Base):
    """An encounter event (Pokemon seen/caught/failed)."""

    __tablename__ = "encounters"

    id = Column(GUID(), primary_key=True, default=uuid4)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    player_id = Column(GUID(), ForeignKey("players.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    family_id = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    shiny = Column(Boolean, nullable=False, default=False)
    method = Column(String(20), nullable=False)  # EncounterMethod enum
    rod_kind = Column(String(10), nullable=True)  # RodKind enum, only for fishing
    time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False)  # EncounterStatus enum
    dupes_skip = Column(Boolean, nullable=False, default=False)
    fe_finalized = Column(
        Boolean, nullable=False, default=False
    )  # First encounter finalized

    # Relationships
    run = relationship("Run", back_populates="encounters")
    player = relationship("Player", back_populates="encounters")
    route = relationship("Route", back_populates="encounters")
    species = relationship("Species", back_populates="encounters")
    link_members = relationship(
        "LinkMember", back_populates="encounter", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_encounter_run_player", "run_id", "player_id"),
        Index("ix_encounter_route_species", "route_id", "species_id"),
        Index("ix_encounter_family_time", "family_id", "time"),
        Index("ix_encounter_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Encounter(id={self.id}, species_id={self.species_id}, level={self.level}, status='{self.status}')>"


class Link(Base):
    """A soul link grouping Pokemon caught on the same route."""

    __tablename__ = "links"

    id = Column(GUID(), primary_key=True, default=uuid4)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)

    # Relationships
    run = relationship("Run", back_populates="links")
    route = relationship("Route", back_populates="links")
    members = relationship(
        "LinkMember", back_populates="link", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("run_id", "route_id", name="uq_link_per_route_per_run"),
    )

    def __repr__(self) -> str:
        return f"<Link(id={self.id}, run_id={self.run_id}, route_id={self.route_id})>"


class LinkMember(Base):
    """A member of a soul link (specific Pokemon)."""

    __tablename__ = "link_members"

    link_id = Column(GUID(), ForeignKey("links.id"), primary_key=True)
    player_id = Column(GUID(), ForeignKey("players.id"), primary_key=True)
    encounter_id = Column(GUID(), ForeignKey("encounters.id"), nullable=False)

    # Relationships
    link = relationship("Link", back_populates="members")
    player = relationship("Player", back_populates="link_members")
    encounter = relationship("Encounter", back_populates="link_members")

    def __repr__(self) -> str:
        return f"<LinkMember(link_id={self.link_id}, player_id={self.player_id}, encounter_id={self.encounter_id})>"


class Blocklist(Base):
    """Blocked evolution families (can't be caught again)."""

    __tablename__ = "blocklist"

    run_id = Column(GUID(), ForeignKey("runs.id"), primary_key=True)
    family_id = Column(Integer, primary_key=True)
    origin = Column(String(50), nullable=False)  # "first_encounter" or "caught"
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("Run", back_populates="blocklist_entries")

    def __repr__(self) -> str:
        return f"<Blocklist(run_id={self.run_id}, family_id={self.family_id}, origin='{self.origin}')>"


class PartyStatus(Base):
    """Current status of Pokemon in player's party."""

    __tablename__ = "party_status"

    run_id = Column(GUID(), ForeignKey("runs.id"), primary_key=True)
    player_id = Column(GUID(), ForeignKey("players.id"), primary_key=True)
    pokemon_key = Column(String(255), primary_key=True)  # Personality value or hash
    alive = Column(Boolean, nullable=False, default=True)
    last_update = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("Run", back_populates="party_statuses")
    player = relationship("Player", back_populates="party_statuses")

    def __repr__(self) -> str:
        return f"<PartyStatus(player_id={self.player_id}, pokemon_key='{self.pokemon_key}', alive={self.alive})>"


class IdempotencyKey(Base):
    """Idempotency keys for preventing duplicate event processing."""

    __tablename__ = "idempotency_keys"

    key = Column(String(255), primary_key=True)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    player_id = Column(GUID(), ForeignKey("players.id"), nullable=False)
    request_hash = Column(String(255), nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    run = relationship("Run", back_populates="idempotency_keys")
    player = relationship("Player", back_populates="idempotency_keys")

    __table_args__ = (
        Index("ix_idempotency_created_at", "created_at"),  # For TTL cleanup
    )

    def __repr__(self) -> str:
        return f"<IdempotencyKey(key='{self.key}', run_id={self.run_id}, player_id={self.player_id})>"


class Event(Base):
    """Event store for append-only domain events (v3 architecture)."""

    __tablename__ = "events"

    id = Column(GUID(), primary_key=True, default=uuid4)
    run_id = Column(GUID(), ForeignKey("runs.id"), nullable=False)
    player_id = Column(GUID(), ForeignKey("players.id"), nullable=False)
    type = Column(String(50), nullable=False)  # Event type identifier
    payload_json = Column(JSON, nullable=False)  # Serialized event data
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    seq = Column(Integer, nullable=False)  # Sequence number per run

    # Relationships
    run = relationship("Run")
    player = relationship("Player")

    __table_args__ = (
        UniqueConstraint(
            "run_id", "seq", name="uq_event_run_seq"
        ),  # Ensures sequence integrity
        Index("ix_event_run_seq", "run_id", "seq"),  # Primary query pattern
        Index(
            "ix_event_run_player_created", "run_id", "player_id", "created_at"
        ),  # Player history
        Index("ix_event_type_created", "type", "created_at"),  # Event type queries
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type='{self.type}', seq={self.seq})>"


class RouteProgress(Base):
    """Projection table tracking route progress and first encounter status."""

    __tablename__ = "route_progress"

    player_id = Column(GUID(), ForeignKey("players.id"), primary_key=True)
    run_id = Column(GUID(), ForeignKey("runs.id"), primary_key=True)
    route_id = Column(Integer, ForeignKey("routes.id"), primary_key=True)
    fe_finalized = Column(
        Boolean, nullable=False, default=False
    )  # First encounter finalized
    last_update = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    player = relationship("Player")
    run = relationship("Run")
    route = relationship("Route")

    __table_args__ = (
        # Note: Partial unique constraint for fe_finalized=True will be added via migration
        # as SQLAlchemy UniqueConstraint doesn't support WHERE conditions
        Index("ix_route_progress_run_route", "run_id", "route_id"),
        Index("ix_route_progress_fe_finalized", "run_id", "route_id", "fe_finalized"),
    )

    def __repr__(self) -> str:
        return f"<RouteProgress(player_id={self.player_id}, route_id={self.route_id}, fe_finalized={self.fe_finalized})>"
