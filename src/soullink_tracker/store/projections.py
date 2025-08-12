"""Projection engine for building read models from domain events.

This module handles the transformation of domain events into queryable
projections like route_progress and blocklist for efficient reads.
"""

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from .integrity_policy import (
    ExpectedIntegrityTag,
)
from .savepoints import (
    expected_conflict_savepoint,
    handle_projection_integrity_error,
    GracefulProjectionError,
)

from ..domain.events import (
    EventEnvelope,
    EncounterEvent,
    CatchResultEvent,
    FaintEvent,
    SoulLinkCreatedEvent,
    SoulLinkBrokenEvent,
    FamilyBlockedEvent,
    FirstEncounterFinalizedEvent,
)
from ..domain.rules import (
    RunState,
    PlayerRouteState,
    evaluate_encounter,
    apply_catch_result,
    process_family_blocked,
    process_faint,
)
from ..db.models import RouteProgress, Blocklist, PartyStatus
from ..core.enums import EncounterStatus


class ProjectionError(Exception):
    """Base exception for projection engine operations."""

    pass


class ProjectionEngine:
    """Engine for applying domain events to projection tables."""

    def __init__(self, db_session: Session):
        self.db = db_session

        # Map event types to their handler methods
        self._handlers: Dict[str, callable] = {
            "encounter": self._handle_encounter_event,
            "catch_result": self._handle_catch_result_event,
            "faint": self._handle_faint_event,
            "soul_link_created": self._handle_soul_link_created_event,
            "soul_link_broken": self._handle_soul_link_broken_event,
            "family_blocked": self._handle_family_blocked_event,
            "first_encounter_finalized": self._handle_first_encounter_finalized_event,
        }

    def apply_event(self, envelope: EventEnvelope) -> None:
        """
        Apply a single event to update projections.

        Args:
            envelope: Event envelope containing the event to apply

        Raises:
            ProjectionError: If the event could not be applied
        """
        event = envelope.event
        event_type = event.event_type

        handler = self._handlers.get(event_type)
        if not handler:
            raise ProjectionError(f"No handler for event type: {event_type}")

        try:
            handler(event, envelope.sequence_number)

        except IntegrityError as e:
            # Handle expected constraint violations gracefully
            context = {
                "operation": f"apply_{event_type}_event",
                "entity_type": event_type,
                "entity_id": str(event.event_id),
                "run_id": str(event.run_id),
                "player_id": str(event.player_id),
            }
            
            try:
                handle_projection_integrity_error(e, context)
                # If we get here, it was an expected constraint violation that was handled
                return
            except GracefulProjectionError:
                # Expected constraint violation - handle gracefully
                return
            except Exception:
                # Re-raise as ProjectionError for unexpected violations
                raise ProjectionError(
                    f"Database constraint violation applying event {event.event_id}: {e}"
                ) from e

        except SQLAlchemyError as e:
            raise ProjectionError(
                f"Database error applying event {event.event_id}: {e}"
            ) from e
        except Exception as e:
            raise ProjectionError(f"Failed to apply event {event.event_id}: {e}") from e

    def apply_events(self, envelopes: List[EventEnvelope]) -> None:
        """
        Apply multiple events in sequence.

        Args:
            envelopes: List of event envelopes to apply in order
        """
        for envelope in envelopes:
            self.apply_event(envelope)

    def rebuild_all_projections(
        self, run_id: UUID, event_stream: List[EventEnvelope]
    ) -> None:
        """
        Rebuild all projections for a run from scratch.

        Args:
            run_id: Run ID to rebuild projections for
            event_stream: Complete ordered stream of events for the run
        """
        try:
            # Clear existing projections for this run
            self._clear_projections(run_id)

            # Apply all events in sequence
            self.apply_events(event_stream)

        except Exception as e:
            # Rollback on any error to maintain consistency
            self.db.rollback()
            raise ProjectionError(
                f"Failed to rebuild projections for run {run_id}: {e}"
            ) from e

    def _clear_projections(self, run_id: UUID) -> None:
        """Clear all projection data for a run."""
        # Delete route progress
        self.db.execute(delete(RouteProgress).where(RouteProgress.run_id == run_id))

        # Delete blocklist entries
        self.db.execute(delete(Blocklist).where(Blocklist.run_id == run_id))

        # Delete party status
        self.db.execute(delete(PartyStatus).where(PartyStatus.run_id == run_id))

        # Note: We don't clear Links and LinkMembers as they're part of the core domain
        # and not just projections - they represent actual game state

    def _handle_encounter_event(self, event: EncounterEvent, sequence: int) -> None:
        """
        Handle encounter event using pure rules engine.

        Uses domain/rules.py for decision making and handles database constraints
        for race condition safety.
        """
        # Build current run state for rules evaluation
        state = self._build_run_state(event.run_id)

        # Check for route-level duplication across players
        def cross_player_lookup(route_id: int, family_id: int) -> bool:
            """Check if any other player has finalized this family on this route."""
            result = self.db.execute(
                select(RouteProgress).where(
                    RouteProgress.run_id == event.run_id,
                    RouteProgress.route_id == route_id,
                    RouteProgress.fe_finalized.is_(True),
                    RouteProgress.player_id != event.player_id,
                )
            ).first()
            return result is not None

        # Apply enhanced rules with cross-player check
        decision = evaluate_encounter(state, event)
        if not decision.dupes_skip and cross_player_lookup(
            event.route_id, event.family_id
        ):
            decision = decision.__class__(
                status=EncounterStatus.DUPE_SKIP,
                dupes_skip=True,
                fe_finalized=False,
                blocklist_add=None,
            )

        # Apply the decision to projections
        if decision.should_create_route_progress:
            self._upsert_route_progress(
                event.run_id,
                event.player_id,
                event.route_id,
                fe_finalized=decision.fe_finalized,
                timestamp=event.timestamp,
            )

        # Handle any blocklist additions (though encounters typically don't block)
        if decision.blocklist_add:
            family_id, origin = decision.blocklist_add
            self._upsert_blocklist(event.run_id, family_id, origin, event.timestamp)

    def _handle_catch_result_event(
        self, event: CatchResultEvent, sequence: int
    ) -> None:
        """Handle catch result event using pure rules engine."""
        # Build current run state for rules evaluation
        state = self._build_run_state(event.run_id)

        # Create encounter lookup helper
        def encounter_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            """Resolve encounter_id to (player_id, route_id, family_id)."""
            # In v3, we need to look this up from the event store
            from .event_store import EventStore

            event_store = EventStore(self.db)

            # Get the encounter event from event store
            envelopes = event_store.get_events_by_type(event.run_id, "encounter")
            for envelope in envelopes:
                if envelope.event.event_id == encounter_id:
                    enc_event = envelope.event
                    return enc_event.player_id, enc_event.route_id, enc_event.family_id

            raise ValueError(f"Encounter {encounter_id} not found in event store")

        # Apply rules
        decision = apply_catch_result(state, event, encounter_lookup)

        # Update route progress finalization
        if decision.fe_finalized:
            player_id, route_id, family_id = encounter_lookup(event.encounter_id)
            self._finalize_route_progress(
                event.run_id, player_id, route_id, event.timestamp
            )

        # Handle family blocking
        if decision.blocklist_add:
            family_id, origin = decision.blocklist_add
            self._upsert_blocklist(event.run_id, family_id, origin, event.timestamp)

    def _handle_faint_event(self, event: FaintEvent, sequence: int) -> None:
        """Handle faint event using pure rules engine."""
        # Build current run state (though faint events don't affect route/blocklist projections)
        state = self._build_run_state(event.run_id)

        # Apply pure rules (returns FaintDecision which is currently empty)
        process_faint(state, event)

        # Update party status (this is separate from route/blocklist projections)
        self._update_party_status(
            event.run_id,
            event.player_id,
            event.pokemon_key,
            alive=False,
            timestamp=event.timestamp,
        )

    def _handle_soul_link_created_event(
        self, event: SoulLinkCreatedEvent, sequence: int
    ) -> None:
        """Handle soul link creation - links are managed in the main domain."""
        # Soul links are managed as part of the core domain model,
        # not as projections, so this is handled elsewhere
        pass

    def _handle_soul_link_broken_event(
        self, event: SoulLinkBrokenEvent, sequence: int
    ) -> None:
        """Handle soul link break - update affected party statuses."""
        # Mark all affected players' Pokemon as fainted
        for player_id in event.affected_players:
            if player_id != event.caused_by_player:  # Don't double-update the causer
                # This would need additional context about which Pokemon are linked
                # For now, this is handled by separate faint events
                pass

    def _handle_family_blocked_event(
        self, event: FamilyBlockedEvent, sequence: int
    ) -> None:
        """Handle family blocking using pure rules engine."""
        # Build current run state
        state = self._build_run_state(event.run_id)

        # Apply pure rules (updates the run state)
        process_family_blocked(state, event)

        # Persist the blocklist change
        self._upsert_blocklist(
            event.run_id, event.family_id, event.origin, event.timestamp
        )

    def _handle_first_encounter_finalized_event(
        self, event: FirstEncounterFinalizedEvent, sequence: int
    ) -> None:
        """Handle first encounter finalization - update route progress."""
        context = {
            "operation": "finalize_route_progress",
            "entity_type": "route_progress",
            "entity_id": f"{event.run_id}:{event.route_id}",
            "run_id": str(event.run_id),
            "player_id": str(event.player_id),
        }
        
        with expected_conflict_savepoint(
            self.db, {ExpectedIntegrityTag.ROUTE_ALREADY_FINALIZED}, context
        ):
            # Find and update the route progress
            route_progress = self.db.execute(
                select(RouteProgress).where(
                    RouteProgress.run_id == event.run_id,
                    RouteProgress.player_id == event.player_id,
                    RouteProgress.route_id == event.route_id,
                    RouteProgress.fe_finalized.is_(False),
                )
            ).scalar_one_or_none()

            if route_progress:
                route_progress.fe_finalized = True
                route_progress.last_update = event.timestamp
                # Flush to trigger constraint check within savepoint
                self.db.flush()
        
        # Check if we hit the expected constraint violation
        if "integrity_tag" in context:
            # Another player won the race - this is expected and handled gracefully
            # No further action needed as the constraint violation was expected
            pass

    # Helper methods for the pure rules integration

    def _build_run_state(self, run_id: UUID) -> RunState:
        """Build a RunState from current projection data."""
        # Get blocked families
        blocked_families = set(
            self.db.execute(
                select(Blocklist.family_id).where(Blocklist.run_id == run_id)
            ).scalars().all()
        )

        # Get player route states
        route_progress_entities = self.db.execute(
            select(RouteProgress).where(RouteProgress.run_id == run_id)
        ).scalars().all()

        player_routes = {}
        for progress in route_progress_entities:
            key = (progress.player_id, progress.route_id)
            player_routes[key] = PlayerRouteState(
                fe_finalized=progress.fe_finalized,
                # Note: We don't currently track these in route_progress
                first_encounter_family_id=None,
                last_encounter_method=None,
                last_rod_kind=None,
            )

        return RunState(blocked_families=blocked_families, player_routes=player_routes)

    def _upsert_route_progress(
        self,
        run_id: UUID,
        player_id: UUID,
        route_id: int,
        fe_finalized: bool,
        timestamp,
    ) -> None:
        """Create or update route progress record."""
        route_progress = self.db.execute(
            select(RouteProgress).where(
                RouteProgress.run_id == run_id,
                RouteProgress.player_id == player_id,
                RouteProgress.route_id == route_id,
            )
        ).scalar_one_or_none()

        try:
            if not route_progress:
                # Create new route progress
                route_progress = RouteProgress(
                    run_id=run_id,
                    player_id=player_id,
                    route_id=route_id,
                    fe_finalized=fe_finalized,
                    last_update=timestamp,
                )
                self.db.add(route_progress)

                # Always flush after creating a new record to ensure visibility for subsequent operations
                self.db.flush()
            else:
                # Update existing route progress
                if fe_finalized and not route_progress.fe_finalized:
                    # Try to finalize first encounter
                    route_progress.fe_finalized = True
                    route_progress.last_update = timestamp
                    # Flush to trigger constraint validation
                    self.db.flush()
                else:
                    # Safe update (not changing fe_finalized to True)
                    route_progress.last_update = timestamp

        except IntegrityError as e:
            # Race condition: Another player already finalized first encounter on this route
            self.db.rollback()

            # Check if this is the fe_finalized constraint violation
            if "ix_route_progress_fe_unique" in str(e) and fe_finalized:
                # Another player won the race for first encounter finalization
                # This becomes a dupe-skip scenario - create/update without finalization
                if not route_progress:
                    route_progress = RouteProgress(
                        run_id=run_id,
                        player_id=player_id,
                        route_id=route_id,
                        fe_finalized=False,  # Force to False due to race loss
                        last_update=timestamp,
                    )
                    self.db.add(route_progress)
                else:
                    # Update timestamp only, don't finalize
                    route_progress.last_update = timestamp

                # Log the race condition resolution
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"First encounter race condition on route {route_id}: "
                    f"Player {player_id} lost to another player, treating as dupe-skip"
                )
            else:
                # Different integrity error - re-raise
                raise

    def _finalize_route_progress(
        self, run_id: UUID, player_id: UUID, route_id: int, timestamp
    ) -> None:
        """Finalize route progress for catch result."""
        self._upsert_route_progress(
            run_id, player_id, route_id, fe_finalized=True, timestamp=timestamp
        )

    def _upsert_blocklist(
        self, run_id: UUID, family_id: int, origin: str, timestamp
    ) -> None:
        """Create or update blocklist entry."""
        context = {
            "operation": "upsert_blocklist",
            "entity_type": "blocklist",
            "entity_id": f"{run_id}:{family_id}",
        }
        
        with expected_conflict_savepoint(
            self.db, {ExpectedIntegrityTag.BLOCK_ALREADY_EXISTS}, context
        ):
            # Try to create blocklist entry
            blocklist_entry = Blocklist(
                run_id=run_id, family_id=family_id, origin=origin, created_at=timestamp
            )
            self.db.add(blocklist_entry)
            self.db.flush()  # Trigger constraint check within savepoint
        
        # Check if we hit the expected constraint violation
        if "integrity_tag" in context:
            # Family already blocked - update existing entry if needed
            existing = self.db.execute(
                select(Blocklist).where(
                    Blocklist.run_id == run_id, Blocklist.family_id == family_id
                )
            ).scalar_one()

            # Update to the most restrictive origin (caught > first_encounter > faint)
            origin_priority = {"caught": 3, "first_encounter": 2, "faint": 1}
            if origin_priority.get(origin, 0) > origin_priority.get(existing.origin, 0):
                existing.origin = origin
                existing.created_at = timestamp

    def _update_party_status(
        self, run_id: UUID, player_id: UUID, pokemon_key: str, alive: bool, timestamp
    ) -> None:
        """Update party status for a Pokemon."""
        party_status = self.db.execute(
            select(PartyStatus).where(
                PartyStatus.run_id == run_id,
                PartyStatus.player_id == player_id,
                PartyStatus.pokemon_key == pokemon_key,
            )
        ).scalar_one_or_none()

        if not party_status:
            party_status = PartyStatus(
                run_id=run_id,
                player_id=player_id,
                pokemon_key=pokemon_key,
                alive=alive,
                last_update=timestamp,
            )
            self.db.add(party_status)
        else:
            party_status.alive = alive
            party_status.last_update = timestamp


class ProjectionQueries:
    """Query interface for projection data."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_route_progress(
        self, run_id: UUID, player_id: Optional[UUID] = None
    ) -> List[RouteProgress]:
        """Get route progress for a run, optionally filtered by player."""
        query = select(RouteProgress).where(RouteProgress.run_id == run_id)

        if player_id:
            query = query.where(RouteProgress.player_id == player_id)

        return self.db.execute(query).scalars().all()

    def get_blocklist(self, run_id: UUID) -> List[Blocklist]:
        """Get all blocked families for a run."""
        return (
            self.db.execute(
                select(Blocklist)
                .where(Blocklist.run_id == run_id)
                .order_by(Blocklist.created_at)
            )
            .scalars()
            .all()
        )

    def get_party_status(self, run_id: UUID, player_id: UUID) -> List[PartyStatus]:
        """Get party status for a specific player."""
        return (
            self.db.execute(
                select(PartyStatus)
                .where(PartyStatus.run_id == run_id, PartyStatus.player_id == player_id)
                .order_by(PartyStatus.last_update.desc())
            )
            .scalars()
            .all()
        )

    def is_family_blocked(self, run_id: UUID, family_id: int) -> bool:
        """Check if a family is blocked in a run."""
        return (
            self.db.execute(
                select(Blocklist).where(
                    Blocklist.run_id == run_id, Blocklist.family_id == family_id
                )
            ).scalar_one_or_none()
            is not None
        )

    def get_finalized_routes(self, run_id: UUID) -> List[int]:
        """Get list of route IDs that have finalized first encounters."""
        results = (
            self.db.execute(
                select(RouteProgress.route_id)
                .where(
                    RouteProgress.run_id == run_id, RouteProgress.fe_finalized.is_(True)
                )
                .distinct()
            )
            .scalars()
            .all()
        )

        return list(results)

    # Helper methods for the pure rules integration

    def _build_run_state(self, run_id: UUID) -> RunState:
        """Build a RunState from current projection data."""
        # Get blocked families
        blocked_families = set(
            self.db.execute(
                select(Blocklist.family_id).where(Blocklist.run_id == run_id)
            ).scalars().all()
        )

        # Get player route states
        route_progress_entities = self.db.execute(
            select(RouteProgress).where(RouteProgress.run_id == run_id)
        ).scalars().all()

        player_routes = {}
        for progress in route_progress_entities:
            key = (progress.player_id, progress.route_id)
            player_routes[key] = PlayerRouteState(
                fe_finalized=progress.fe_finalized,
                # Note: We don't currently track these in route_progress
                first_encounter_family_id=None,
                last_encounter_method=None,
                last_rod_kind=None,
            )

        return RunState(blocked_families=blocked_families, player_routes=player_routes)

    def _upsert_route_progress(
        self,
        run_id: UUID,
        player_id: UUID,
        route_id: int,
        fe_finalized: bool,
        timestamp,
    ) -> None:
        """Create or update route progress record."""
        route_progress = self.db.execute(
            select(RouteProgress).where(
                RouteProgress.run_id == run_id,
                RouteProgress.player_id == player_id,
                RouteProgress.route_id == route_id,
            )
        ).scalar_one_or_none()

        try:
            if not route_progress:
                # Create new route progress
                route_progress = RouteProgress(
                    run_id=run_id,
                    player_id=player_id,
                    route_id=route_id,
                    fe_finalized=fe_finalized,
                    last_update=timestamp,
                )
                self.db.add(route_progress)

                # Always flush after creating a new record to ensure visibility for subsequent operations
                self.db.flush()
            else:
                # Update existing route progress
                if fe_finalized and not route_progress.fe_finalized:
                    # Try to finalize first encounter
                    route_progress.fe_finalized = True
                    route_progress.last_update = timestamp
                    # Flush to trigger constraint validation
                    self.db.flush()
                else:
                    # Safe update (not changing fe_finalized to True)
                    route_progress.last_update = timestamp

        except IntegrityError as e:
            # Race condition: Another player already finalized first encounter on this route
            self.db.rollback()

            # Check if this is the fe_finalized constraint violation
            if "ix_route_progress_fe_unique" in str(e) and fe_finalized:
                # Another player won the race for first encounter finalization
                # This becomes a dupe-skip scenario - create/update without finalization
                if not route_progress:
                    route_progress = RouteProgress(
                        run_id=run_id,
                        player_id=player_id,
                        route_id=route_id,
                        fe_finalized=False,  # Force to False due to race loss
                        last_update=timestamp,
                    )
                    self.db.add(route_progress)
                else:
                    # Update timestamp only, don't finalize
                    route_progress.last_update = timestamp

                # Log the race condition resolution
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"First encounter race condition on route {route_id}: "
                    f"Player {player_id} lost to another player, treating as dupe-skip"
                )
            else:
                # Different integrity error - re-raise
                raise

    def _finalize_route_progress(
        self, run_id: UUID, player_id: UUID, route_id: int, timestamp
    ) -> None:
        """Finalize route progress for catch result."""
        self._upsert_route_progress(
            run_id, player_id, route_id, fe_finalized=True, timestamp=timestamp
        )

    def _upsert_blocklist(
        self, run_id: UUID, family_id: int, origin: str, timestamp
    ) -> None:
        """Create or update blocklist entry."""
        try:
            # Try to create blocklist entry
            blocklist_entry = Blocklist(
                run_id=run_id, family_id=family_id, origin=origin, created_at=timestamp
            )
            self.db.add(blocklist_entry)

        except IntegrityError:
            # Family already blocked - this is idempotent
            self.db.rollback()
            # Get existing entry and potentially update origin if needed
            existing = self.db.execute(
                select(Blocklist).where(
                    Blocklist.run_id == run_id, Blocklist.family_id == family_id
                )
            ).scalar_one()

            # Update to the most restrictive origin (caught > first_encounter > faint)
            origin_priority = {"caught": 3, "first_encounter": 2, "faint": 1}
            if origin_priority.get(origin, 0) > origin_priority.get(existing.origin, 0):
                existing.origin = origin
                existing.created_at = timestamp

    def _update_party_status(
        self, run_id: UUID, player_id: UUID, pokemon_key: str, alive: bool, timestamp
    ) -> None:
        """Update party status for a Pokemon."""
        party_status = self.db.execute(
            select(PartyStatus).where(
                PartyStatus.run_id == run_id,
                PartyStatus.player_id == player_id,
                PartyStatus.pokemon_key == pokemon_key,
            )
        ).scalar_one_or_none()

        if not party_status:
            party_status = PartyStatus(
                run_id=run_id,
                player_id=player_id,
                pokemon_key=pokemon_key,
                alive=alive,
                last_update=timestamp,
            )
            self.db.add(party_status)
        else:
            party_status.alive = alive
            party_status.last_update = timestamp
