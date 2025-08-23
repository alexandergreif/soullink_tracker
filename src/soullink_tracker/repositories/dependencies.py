"""Dependency injection for repository layer."""

from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from ..db.database import get_db
from .interfaces import RepositoryContainer
from .sqlalchemy_impl import (
    SQLAlchemyRunRepository,
    SQLAlchemyPlayerRepository,
    SQLAlchemyEncounterRepository,
    SQLAlchemySpeciesRepository,
    SQLAlchemyRouteRepository,
    SQLAlchemyLinkRepository,
    SQLAlchemyLinkMemberRepository,
    SQLAlchemyBlocklistRepository,
    SQLAlchemyPartyStatusRepository,
    SQLAlchemyIdempotencyKeyRepository,
    SQLAlchemyEventRepository,
    SQLAlchemyRouteProgressRepository,
)


def get_repository_container(
    db: Session = Depends(get_db),
) -> RepositoryContainer:
    """
    Create and configure a repository container with SQLAlchemy implementations.
    
    This is the main dependency injection point for repositories.
    """
    return RepositoryContainer(
        run_repo=SQLAlchemyRunRepository(db),
        player_repo=SQLAlchemyPlayerRepository(db),
        encounter_repo=SQLAlchemyEncounterRepository(db),
        species_repo=SQLAlchemySpeciesRepository(db),
        route_repo=SQLAlchemyRouteRepository(db),
        link_repo=SQLAlchemyLinkRepository(db),
        link_member_repo=SQLAlchemyLinkMemberRepository(db),
        blocklist_repo=SQLAlchemyBlocklistRepository(db),
        party_status_repo=SQLAlchemyPartyStatusRepository(db),
        idempotency_key_repo=SQLAlchemyIdempotencyKeyRepository(db),
        event_repo=SQLAlchemyEventRepository(db),
        route_progress_repo=SQLAlchemyRouteProgressRepository(db),
    )


# Individual repository dependencies for backwards compatibility
# or when only specific repositories are needed


def get_run_repository(db: Session = Depends(get_db)) -> SQLAlchemyRunRepository:
    """Get Run repository instance."""
    return SQLAlchemyRunRepository(db)


def get_player_repository(db: Session = Depends(get_db)) -> SQLAlchemyPlayerRepository:
    """Get Player repository instance."""
    return SQLAlchemyPlayerRepository(db)


def get_encounter_repository(db: Session = Depends(get_db)) -> SQLAlchemyEncounterRepository:
    """Get Encounter repository instance."""
    return SQLAlchemyEncounterRepository(db)


def get_species_repository(db: Session = Depends(get_db)) -> SQLAlchemySpeciesRepository:
    """Get Species repository instance."""
    return SQLAlchemySpeciesRepository(db)


def get_route_repository(db: Session = Depends(get_db)) -> SQLAlchemyRouteRepository:
    """Get Route repository instance."""
    return SQLAlchemyRouteRepository(db)


def get_link_repository(db: Session = Depends(get_db)) -> SQLAlchemyLinkRepository:
    """Get Link repository instance."""
    return SQLAlchemyLinkRepository(db)


def get_link_member_repository(db: Session = Depends(get_db)) -> SQLAlchemyLinkMemberRepository:
    """Get LinkMember repository instance."""
    return SQLAlchemyLinkMemberRepository(db)


def get_blocklist_repository(db: Session = Depends(get_db)) -> SQLAlchemyBlocklistRepository:
    """Get Blocklist repository instance."""
    return SQLAlchemyBlocklistRepository(db)


def get_party_status_repository(db: Session = Depends(get_db)) -> SQLAlchemyPartyStatusRepository:
    """Get PartyStatus repository instance."""
    return SQLAlchemyPartyStatusRepository(db)


def get_idempotency_key_repository(db: Session = Depends(get_db)) -> SQLAlchemyIdempotencyKeyRepository:
    """Get IdempotencyKey repository instance."""
    return SQLAlchemyIdempotencyKeyRepository(db)


def get_event_repository(db: Session = Depends(get_db)) -> SQLAlchemyEventRepository:
    """Get Event repository instance."""
    return SQLAlchemyEventRepository(db)


def get_route_progress_repository(db: Session = Depends(get_db)) -> SQLAlchemyRouteProgressRepository:
    """Get RouteProgress repository instance."""
    return SQLAlchemyRouteProgressRepository(db)