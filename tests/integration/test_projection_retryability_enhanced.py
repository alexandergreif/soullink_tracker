"""Enhanced transaction boundary and savepoint recovery tests.

Tests that validate the graceful error handling system doesn't poison transactions
and that savepoint-based recovery works correctly under various constraint violation
scenarios. These tests ensure that the projection engine maintains transaction integrity
even when handling expected constraint violations.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.db.models import RouteProgress, Blocklist
from src.soullink_tracker.domain.events import (
    EncounterEvent, 
    CatchResultEvent, 
    FamilyBlockedEvent, 
    FirstEncounterFinalizedEvent
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from tests.helpers.concurrency import run_in_threads, session_worker


class TestSavepointRecovery:
    """Test savepoint-based transaction recovery after constraint violations."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_route_finalization_constraint_doesnt_poison_transaction(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that route finalization constraint violations don't poison the transaction."""
        # Arrange
        run = make_run("Savepoint Recovery Run")
        player1 = make_player(run.id, "SavepointPlayer1")
        player2 = make_player(run.id, "SavepointPlayer2")
        
        barrier = barrier_factory(2)
        
        # Create encounters for both players
        encounters = []
        for i, player in enumerate([player1, player2]):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=30,
                species_id=25 + i,  # Different species
                family_id=25 + i,
                level=5,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            encounters.append(encounter)
            
            # Apply encounter with main session
            event_store = EventStore(db_session)
            projection_engine = ProjectionEngine(db_session)
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Create competing catch events
        catches = []
        for encounter in encounters:
            catch = CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=encounter.player_id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=encounter.event_id,
                result=EncounterStatus.CAUGHT,
            )
            catches.append(catch)
        
        results: List[Optional[BaseException]] = [None, None]
        
        def competing_catch_worker(player_idx: int) -> None:
            """Worker that attempts to finalize route via catch result."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                # Store the catch event
                envelope = event_store.append(catches[player_idx])
                session.commit()
                
                # Wait for both threads to be ready
                barrier.wait()
                
                # Both try to finalize simultaneously
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                results[player_idx] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run competing catch attempts
        workers = [
            session_worker(session_factory, lambda: competing_catch_worker(0)),
            session_worker(session_factory, lambda: competing_catch_worker(1))
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No thread errors (graceful handling worked)
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        # No worker exceptions
        for i, result in enumerate(results):
            if result:
                pytest.fail(f"Worker {i} had exception: {result}")
        
        # Exactly one route should be finalized
        finalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 30,
            RouteProgress.fe_finalized.is_(True)
        ).count()
        
        assert finalized_count == 1

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_blocklist_constraint_preserves_other_operations(
        self, db_session, session_factory, make_run, make_player
    ):
        """Test that blocklist constraint violations don't affect other operations in the transaction."""
        # Arrange
        run = make_run("Blocklist Transaction Run")
        player = make_player(run.id, "BlocklistTxPlayer")
        
        session = session_factory()
        event_store = EventStore(session)
        projection_engine = ProjectionEngine(session)
        
        # Create initial blocklist entry
        initial_block = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=150,  # Mewtwo family
            origin="first_encounter",
        )
        
        envelope = event_store.append(initial_block)
        session.commit()
        projection_engine.apply_event(envelope)
        session.commit()
        
        # Create an encounter for a different family (should succeed)
        valid_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=31,
            species_id=144,  # Articuno (different family)
            family_id=144,
            level=50,
            shiny=False,
            encounter_method=EncounterMethod.STATIC,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        # Create duplicate blocklist event (should cause constraint violation)
        duplicate_block = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=150,  # Same family - should violate constraint
            origin="first_encounter",
        )
        
        # Store both events
        encounter_env = event_store.append(valid_encounter)
        duplicate_env = event_store.append(duplicate_block)
        session.commit()
        
        # Act: Apply both events in same transaction
        projection_engine.apply_event(encounter_env)  # Should succeed
        projection_engine.apply_event(duplicate_env)  # Should hit constraint gracefully
        session.commit()
        session.close()
        
        # Assert: Valid encounter should be processed despite blocklist constraint
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 31,
            RouteProgress.player_id == player.id
        ).first()
        
        assert route_progress is not None
        assert route_progress.species_id == 144
        
        # Blocklist should still have exactly one entry
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 150
        ).count()
        
        assert blocklist_count == 1

    @pytest.mark.v3_only 
    @pytest.mark.concurrency
    def test_mixed_constraint_violations_dont_cascade(
        self, db_session, session_factory, make_run, make_player
    ):
        """Test that multiple different constraint violations in one transaction don't cascade."""
        # Arrange
        run = make_run("Mixed Constraint Run")
        player1 = make_player(run.id, "MixedPlayer1")
        player2 = make_player(run.id, "MixedPlayer2")
        
        session = session_factory()
        event_store = EventStore(session)
        projection_engine = ProjectionEngine(session)
        
        # Setup: Create initial state
        # 1. Blocklist entry for family 100
        initial_block = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            family_id=100,  # Voltorb family
            origin="first_encounter",
        )
        
        # 2. Encounters for both players on route 32
        encounters = []
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=32,
                species_id=81 if player == player1 else 82,  # Magnemite vs Magneton
                family_id=81,  # Same family
                level=20,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            encounters.append(encounter)
        
        # Apply initial setup
        for event in [initial_block] + encounters:
            env = event_store.append(event)
            session.commit()
            projection_engine.apply_event(env)
            session.commit()
        
        # Create events that will cause multiple constraint violations
        events_with_violations = []
        
        # 1. Duplicate blocklist (constraint violation)
        duplicate_block = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            family_id=100,  # Already blocked
            origin="first_encounter",
        )
        events_with_violations.append(duplicate_block)
        
        # 2. Valid encounter on different route (should succeed)
        valid_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=33,  # Different route
            species_id=54,  # Psyduck
            family_id=54,
            level=15,
            shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        events_with_violations.append(valid_encounter)
        
        # 3. Competing route finalization (constraint violation)
        catch_player1 = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounters[0].event_id,
            result=EncounterStatus.CAUGHT,
        )
        catch_player2 = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounters[1].event_id,
            result=EncounterStatus.CAUGHT,
        )
        events_with_violations.extend([catch_player1, catch_player2])
        
        # Store all events
        envelopes = []
        for event in events_with_violations:
            env = event_store.append(event)
            envelopes.append(env)
        session.commit()
        
        # Act: Apply all events in single transaction (multiple constraint violations expected)
        for env in envelopes:
            projection_engine.apply_event(env)
        session.commit()
        session.close()
        
        # Assert: Valid operations should succeed despite constraint violations
        # Valid encounter should be processed
        valid_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 33,
            RouteProgress.species_id == 54
        ).first()
        
        assert valid_route_progress is not None
        
        # Exactly one player should have finalized route 32
        finalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 32,
            RouteProgress.fe_finalized.is_(True)
        ).count()
        
        assert finalized_count == 1
        
        # Still only one blocklist entry for family 100
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 100
        ).count()
        
        assert blocklist_count == 1

    @pytest.mark.v3_only
    @pytest.mark.concurrency  
    def test_savepoint_rollback_preserves_session_integrity(
        self, db_session, session_factory, make_run, make_player
    ):
        """Test that savepoint rollbacks don't corrupt the session state."""
        # Arrange
        run = make_run("Session Integrity Run")
        player = make_player(run.id, "IntegrityPlayer")
        
        session = session_factory()
        event_store = EventStore(session)
        projection_engine = ProjectionEngine(session)
        
        # Create multiple events: some valid, some that will cause constraint violations
        events = []
        
        # 1. Valid encounter
        valid_encounter1 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=34,
            species_id=50,  # Diglett
            family_id=50,
            level=8,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        events.append(valid_encounter1)
        
        # 2. Blocklist event for family 200
        block_event = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=200,  # Misdreavus family
            origin="first_encounter",
        )
        events.append(block_event)
        
        # 3. Another valid encounter
        valid_encounter2 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=35,
            species_id=60,  # Poliwag  
            family_id=60,
            level=12,
            shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        events.append(valid_encounter2)
        
        # 4. Duplicate blocklist (constraint violation)
        duplicate_block = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=200,  # Same family - constraint violation
            origin="first_encounter",
        )
        events.append(duplicate_block)
        
        # 5. Final valid encounter
        valid_encounter3 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=36,
            species_id=70,  # Bellsprout
            family_id=70,
            level=14,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        events.append(valid_encounter3)
        
        # Store all events
        envelopes = []
        for event in events:
            env = event_store.append(event)
            envelopes.append(env)
        session.commit()
        
        # Act: Apply events sequentially (constraint violation in middle)
        for i, env in enumerate(envelopes):
            projection_engine.apply_event(env)
            # Don't commit between - test session integrity within transaction
        
        session.commit()
        session.close()
        
        # Assert: All valid operations should have succeeded
        # Route progress for all valid encounters
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id
        ).all()
        
        route_ids = [rp.route_id for rp in route_progress]
        assert 34 in route_ids  # valid_encounter1
        assert 35 in route_ids  # valid_encounter2
        assert 36 in route_ids  # valid_encounter3
        
        # Only one blocklist entry (constraint violation was gracefully handled)
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 200
        ).count()
        
        assert blocklist_count == 1


class TestTransactionBoundaryEdgeCases:
    """Test edge cases around transaction boundaries and constraint timing."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_flush_timing_with_competing_finalizations(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that flush timing doesn't create race windows in constraint enforcement."""
        # Arrange
        run = make_run("Flush Timing Run")
        player1 = make_player(run.id, "FlushPlayer1")
        player2 = make_player(run.id, "FlushPlayer2")
        
        # Setup encounters
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=40,
                species_id=130 if player == player1 else 131,  # Gyarados vs different
                family_id=129,  # Same family (Magikarp line)
                level=20,
                shiny=False,
                encounter_method=EncounterMethod.SURF,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            
            # Apply with main session
            event_store = EventStore(db_session)
            projection_engine = ProjectionEngine(db_session)
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        barrier = barrier_factory(2)
        results: List[Optional[Exception]] = [None, None]
        
        def finalization_worker(player_id: str, player_idx: int) -> None:
            """Worker that tries to finalize via FirstEncounterFinalizedEvent."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                fe_event = FirstEncounterFinalizedEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player_id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=40,
                )
                
                envelope = event_store.append(fe_event)
                session.commit()
                
                # Synchronize to maximize race condition potential
                barrier.wait()
                
                # Apply finalization (will use savepoint internally)
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                results[player_idx] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run competing finalization attempts
        workers = [
            session_worker(session_factory, lambda: finalization_worker(player1.id, 0)),
            session_worker(session_factory, lambda: finalization_worker(player2.id, 1))
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No thread failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        # No worker exceptions
        for i, result in enumerate(results):
            if result:
                pytest.fail(f"Worker {i} had exception: {result}")
        
        # Exactly one finalized entry
        finalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 40,
            RouteProgress.fe_finalized.is_(True)
        ).count()
        
        assert finalized_count == 1

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_constraint_violation_during_bulk_operations(
        self, db_session, session_factory, make_run, make_player
    ):
        """Test constraint violations don't corrupt bulk operations."""
        # Arrange
        run = make_run("Bulk Operations Run")
        player = make_player(run.id, "BulkPlayer")
        
        session = session_factory()
        event_store = EventStore(session)
        projection_engine = ProjectionEngine(session)
        
        # Create many events with one constraint violation in the middle
        events = []
        
        # Valid encounters on routes 50-59
        for route_id in range(50, 60):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=route_id,
                species_id=route_id + 100,  # Different species per route
                family_id=route_id + 100,   # Different families
                level=10,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            events.append(encounter)
        
        # Insert a blocklist event and its duplicate in the middle
        block_original = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=999,  # Special family for this test
            origin="first_encounter",
        )
        
        block_duplicate = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=999,  # Same family - constraint violation
            origin="first_encounter",
        )
        
        # Insert at positions 5 and 7
        events.insert(5, block_original)
        events.insert(7, block_duplicate)
        
        # Store all events
        envelopes = []
        for event in events:
            env = event_store.append(event)
            envelopes.append(env)
        session.commit()
        
        # Act: Apply all events in single transaction
        for env in envelopes:
            projection_engine.apply_event(env)
        session.commit()
        session.close()
        
        # Assert: All valid encounters should be processed
        route_progress_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id >= 50,
            RouteProgress.route_id < 60
        ).count()
        
        assert route_progress_count == 10  # All 10 encounters processed
        
        # Only one blocklist entry
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 999
        ).count()
        
        assert blocklist_count == 1