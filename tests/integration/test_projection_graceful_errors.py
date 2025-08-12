"""
Test projection engine graceful handling of IntegrityError exceptions.

These tests validate that database constraint violations (IntegrityError)
are handled gracefully as success indicators rather than unhandled exceptions.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.domain.events import (
    EncounterEvent,
    CatchResultEvent,
    FamilyBlockedEvent,
    FirstEncounterFinalizedEvent,
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from src.soullink_tracker.db.models import RouteProgress, Blocklist


@pytest.mark.v3_only
class TestProjectionGracefulErrorHandling:
    """Test graceful handling of IntegrityError in projection engine."""

    def test_route_finalization_race_should_not_raise_integrity_error(
        self, db_session, make_run, make_player
    ):
        """Test that route finalization race conditions are handled gracefully."""
        # Arrange: Create run, players, and event store
        run = make_run()
        player1 = make_player(run_id=run.id, name="Player1")
        player2 = make_player(run_id=run.id, name="Player2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create two encounter events on the same route
        encounter1 = EncounterEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player1.id,
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            encounter_method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        encounter2 = EncounterEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player2.id,
            route_id=31,  # Same route
            species_id=1,  # Same species
            family_id=1,  # Same family
            level=7,
            encounter_method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        # Store both encounters
        env1 = event_store.append(encounter1)
        env2 = event_store.append(encounter2)
        db_session.commit()
        
        # Apply first encounter - should succeed
        projection_engine.apply_event(env1)
        db_session.commit()
        
        # Create catch results that would both try to finalize
        catch1 = CatchResultEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player1.id,
            encounter_id=encounter1.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        catch2 = CatchResultEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player2.id,
            encounter_id=encounter2.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        env_catch1 = event_store.append(catch1)
        env_catch2 = event_store.append(catch2)
        db_session.commit()
        
        # Apply first catch - should finalize route
        projection_engine.apply_event(env_catch1)
        db_session.commit()
        
        # Act: Second catch should NOT raise IntegrityError due to graceful handling
        # The constraint violation should be handled gracefully
        projection_engine.apply_event(env_catch2)
        db_session.commit()
        
        # Assert: Should have route progress entries for both players
        from src.soullink_tracker.db.models import RouteProgress
        from sqlalchemy import select
        
        route_progress_count = db_session.execute(
            select(RouteProgress).where(
                RouteProgress.run_id == run.id,
                RouteProgress.route_id == 31
            )
        ).scalars().all()
        
        # Should have exactly 1 entry (only the winner of the race gets to finalize)
        # The constraint prevents multiple finalized entries for the same route
        assert len(route_progress_count) == 1, f"Expected 1 route progress entry, got {len(route_progress_count)}"
        
        # The single entry should be finalized (winner of the race)
        finalized_entry = route_progress_count[0]
        assert finalized_entry.fe_finalized == True, "Route progress should be finalized"

    def test_blocklist_duplicate_should_not_raise_integrity_error(
        self, db_session, make_run
    ):
        """Test that duplicate blocklist entries are handled gracefully."""
        # Arrange: Create run and event store
        run = make_run()
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create two identical family blocked events
        family_blocked1 = FamilyBlockedEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=uuid4(),  # Player ID doesn't matter for this event
            family_id=1,
            origin="caught",
        )
        
        family_blocked2 = FamilyBlockedEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=uuid4(),
            family_id=1,  # Same family
            origin="caught",
        )
        
        # Store both events
        env1 = event_store.append(family_blocked1)
        env2 = event_store.append(family_blocked2)
        db_session.commit()
        
        # Apply first event - should succeed
        projection_engine.apply_event(env1)
        db_session.commit()
        
        # Act: Second event should NOT raise IntegrityError due to graceful handling
        projection_engine.apply_event(env2)
        db_session.commit()
        
        # Assert: Should have exactly one blocklist entry (duplicates handled gracefully)
        from sqlalchemy import select
        
        blocklist_count = db_session.execute(
            select(Blocklist).where(
                Blocklist.run_id == run.id,
                Blocklist.family_id == 1
            )
        ).scalars().all()
        
        assert len(blocklist_count) == 1, f"Expected 1 blocklist entry, got {len(blocklist_count)}"

    def test_first_encounter_finalized_race_should_not_raise_integrity_error(
        self, db_session, make_run, make_player
    ):
        """Test that FirstEncounterFinalizedEvent races are handled gracefully."""
        # Arrange: Create run, players, and initial route progress
        run = make_run()
        player1 = make_player(run_id=run.id, name="Player1")
        player2 = make_player(run_id=run.id, name="Player2")
        
        # Create route progress for both players (not finalized)
        route_progress1 = RouteProgress(
            run_id=run.id,
            player_id=player1.id,
            route_id=31,
            fe_finalized=False,
            last_update=datetime.now(timezone.utc),
        )
        route_progress2 = RouteProgress(
            run_id=run.id,
            player_id=player2.id,
            route_id=31,
            fe_finalized=False,
            last_update=datetime.now(timezone.utc),
        )
        
        db_session.add(route_progress1)
        db_session.add(route_progress2)
        db_session.commit()
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create two finalization events for the same route
        finalize1 = FirstEncounterFinalizedEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player1.id,
            route_id=31,
        )
        
        finalize2 = FirstEncounterFinalizedEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player2.id,
            route_id=31,  # Same route - race condition
        )
        
        # Store both events
        env1 = event_store.append(finalize1)
        env2 = event_store.append(finalize2)
        db_session.commit()
        
        # Apply first event - should succeed
        projection_engine.apply_event(env1)
        db_session.commit()
        
        # Act: Second event should NOT raise IntegrityError due to graceful handling
        projection_engine.apply_event(env2)
        db_session.commit()
        
        # Assert: Should have exactly one finalized route (winner of race condition)
        from sqlalchemy import select
        finalized_routes = db_session.execute(
            select(RouteProgress).where(
                RouteProgress.run_id == run.id,
                RouteProgress.route_id == 31,
                RouteProgress.fe_finalized.is_(True),
            )
        ).scalars().all()
        
        assert len(finalized_routes) == 1, f"Expected exactly 1 finalized route, got {len(finalized_routes)}"
        # The first player should be the winner since they applied first
        assert finalized_routes[0].player_id == player1.id

    def test_unexpected_integrity_error_should_still_raise(
        self, db_session, make_run, make_player
    ):
        """Test that truly unexpected IntegrityError still propagates."""
        # Arrange: Create scenario that would cause a foreign key violation
        # Act: Second event should NOT raise IntegrityError due to graceful handling
        projection_engine.apply_event(env2)
        db_session.commit()
        
        # Assert: Should have exactly one blocklist entry (duplicates handled gracefully)
        from sqlalchemy import select
        
        blocklist_count = db_session.execute(
            select(Blocklist).where(
                Blocklist.run_id == run.id,
                Blocklist.family_id == 1
            )
        ).scalars().all()
        
        assert len(blocklist_count) == 1, f"Expected 1 blocklist entry, got {len(blocklist_count)}"

    def test_unexpected_integrity_error_should_still_raise(
        self, db_session, make_run, make_player
    ):
        """Test that truly unexpected IntegrityError still propagates."""
        # Arrange: Create a scenario that will cause an unexpected constraint violation
        run = make_run()
        player = make_player(run_id=run.id, name="TestPlayer")
        projection_engine = ProjectionEngine(db_session)
        
        # Create a valid encounter event that will cause route progress creation
        encounter_event = EncounterEvent(
            event_id=uuid4(),
            run_id=run.id,
            player_id=player.id,
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            encounter_method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        # Mock the event envelope
        from src.soullink_tracker.domain.events import EventEnvelope
        encounter_envelope = EventEnvelope(
            sequence_number=1,
            event=encounter_event,
        )
        
        # Apply encounter event - this should work
        projection_engine.apply_event(encounter_envelope)
        db_session.commit()
        
        # Now manually break the database by creating a constraint that doesn't match our expected ones
        # We'll directly violate a constraint that's not in our CONSTRAINT_TAG_MAP
        from src.soullink_tracker.db.models import RouteProgress
        
        # Create another route progress with the same primary key manually (this will cause an unexpected constraint)
        duplicate_route_progress = RouteProgress(
            run_id=run.id,
            player_id=player.id,
            route_id=31,  # Same as before - this will violate primary key
            fe_finalized=False,
            last_update=datetime.now(timezone.utc),
        )
        
        # Try to add it directly to session - this should cause PRIMARY KEY constraint violation
        # which is NOT in our expected constraint map
        db_session.add(duplicate_route_progress)
        
        # Act & Assert: This should raise IntegrityError because it's hitting the primary key constraint
        # which is NOT in our CONSTRAINT_TAG_MAP (we only map the finalization constraint)
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed: route_progress.player_id"):
            db_session.commit()

    def test_logging_for_graceful_integrity_handling(
        self, db_session, make_run, make_player, caplog
    ):
        """Test that graceful IntegrityError handling is logged at INFO level."""
        # This test will be implemented after the graceful handling is added
        pytest.skip("Will be implemented after graceful handling is added")

    def test_metrics_for_graceful_integrity_handling(
        self, db_session, make_run, make_player
    ):
        """Test that graceful IntegrityError handling increments metrics."""
        # This test will be implemented after the graceful handling is added
        pytest.skip("Will be implemented after graceful handling is added")


@pytest.mark.v3_only 
class TestProjectionRetryability:
    """Test that projection operations are retryable after constraint violations."""

    def test_projection_engine_transaction_not_poisoned_after_constraint_violation(
        self, db_session, make_run, make_player
    ):
        """Test that the database transaction can continue after graceful constraint handling."""
        # This test verifies that after handling a constraint violation gracefully,
        # the same transaction can continue with other operations
        pytest.skip("Will be implemented with savepoint handling")

    def test_projection_engine_rollback_and_retry_works(
        self, db_session, make_run, make_player
    ):
        """Test that projection engine can rollback and retry after constraint violations."""
        # This test verifies the retry mechanism works correctly
        pytest.skip("Will be implemented with retry logic")