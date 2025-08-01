"""SQLAlchemy models for the SoulLink tracker."""

from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, JSON,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
import hashlib
import secrets

from .database import Base
from ..core.enums import EncounterMethod, EncounterStatus, RodKind


class GUID(TypeDecorator):
    """Platform-independent GUID type using String for SQLite."""
    
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    players = relationship("Player", back_populates="run", cascade="all, delete-orphan")
    encounters = relationship("Encounter", back_populates="run", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="run", cascade="all, delete-orphan")
    blocklist_entries = relationship("Blocklist", back_populates="run", cascade="all, delete-orphan")
    party_statuses = relationship("PartyStatus", back_populates="run", cascade="all, delete-orphan")
    idempotency_keys = relationship("IdempotencyKey", back_populates="run", cascade="all, delete-orphan")
    
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    run = relationship("Run", back_populates="players")
    encounters = relationship("Encounter", back_populates="player", cascade="all, delete-orphan")
    link_members = relationship("LinkMember", back_populates="player", cascade="all, delete-orphan")
    party_statuses = relationship("PartyStatus", back_populates="player", cascade="all, delete-orphan")
    idempotency_keys = relationship("IdempotencyKey", back_populates="player", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('run_id', 'name', name='uq_player_name_per_run'),
        Index('ix_player_token_hash', 'token_hash'),
    )
    
    def verify_token(self, token: str) -> bool:
        """Verify a bearer token against the stored hash."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(self.token_hash, token_hash)
    
    @classmethod
    def generate_token(cls) -> tuple[str, str]:
        """Generate a new token and its hash."""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash
    
    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name='{self.name}', game='{self.game}')>"


class Species(Base):
    """Pokemon species reference data."""
    
    __tablename__ = "species"
    
    id = Column(Integer, primary_key=True)  # National Dex ID
    name = Column(String(100), nullable=False)
    family_id = Column(Integer, nullable=False)  # Evolution family ID
    
    # Relationships
    encounters = relationship("Encounter", back_populates="species")
    
    __table_args__ = (
        Index('ix_species_family_id', 'family_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Species(id={self.id}, name='{self.name}', family_id={self.family_id})>"


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
    fe_finalized = Column(Boolean, nullable=False, default=False)  # First encounter finalized
    
    # Relationships
    run = relationship("Run", back_populates="encounters")
    player = relationship("Player", back_populates="encounters")
    route = relationship("Route", back_populates="encounters")
    species = relationship("Species", back_populates="encounters")
    link_members = relationship("LinkMember", back_populates="encounter", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_encounter_run_player', 'run_id', 'player_id'),
        Index('ix_encounter_route_species', 'route_id', 'species_id'),
        Index('ix_encounter_family_time', 'family_id', 'time'),
        Index('ix_encounter_status', 'status'),
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
    members = relationship("LinkMember", back_populates="link", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('run_id', 'route_id', name='uq_link_per_route_per_run'),
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
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
    last_update = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    run = relationship("Run", back_populates="idempotency_keys")
    player = relationship("Player", back_populates="idempotency_keys")
    
    __table_args__ = (
        Index('ix_idempotency_created_at', 'created_at'),  # For TTL cleanup
    )
    
    def __repr__(self) -> str:
        return f"<IdempotencyKey(key='{self.key}', run_id={self.run_id}, player_id={self.player_id})>"