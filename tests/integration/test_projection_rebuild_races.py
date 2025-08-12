"""Projection rebuild vs live updates race condition tests.

Tests that validate the projection rebuild functionality doesn't conflict with
live projection updates and that the system maintains consistency when rebuilds
occur concurrently with new event processing. These tests ensure the admin rebuild
endpoint works correctly under concurrent load.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.db.models import RouteProgress, Blocklist, Event
from src.soullink_tracker.domain.events import (
    EncounterEvent, 
    CatchResultEvent, 
    FirstEncounterFinalizedEvent
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from tests.helpers.concurrency import run_in_threads, session_worker


class TestProjectionRebuildRaces:
    """Test projection rebuild vs live updates race conditions."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.rebuild_race
    def test_rebuild_vs_new_events_consistency(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that projection rebuilds don't conflict with new event processing."""
        # Arrange
        run = make_run("Rebuild Race Run")
        player1 = make_player(run.id, "RebuildPlayer1")
        player2 = make_player(run.id, "RebuildPlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Create initial events that will be part of rebuild
        initial_events = []
        for i, player in enumerate([player1, player2]):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=100 + i,
                species_id=25 + i,  # Pikachu, Raichu
                family_id=25,  # Same family
                level=5 + i,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            initial_events.append(encounter)
            
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Clear projections to simulate need for rebuild
        db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).delete()
        db_session.query(Blocklist).filter(Blocklist.run_id == run.id).delete()
        db_session.commit()
        
        barrier = barrier_factory(2)
        rebuild_error: List[Optional[Exception]] = [None]
        live_update_error: List[Optional[Exception]] = [None]
        
        def rebuild_worker() -> None:
            """Worker that performs projection rebuild."""
            try:
                session = session_factory()
                projection_engine = ProjectionEngine(session)
                
                # Wait for synchronization
                barrier.wait()
                
                # Perform rebuild (this should process initial_events)
                projection_engine.rebuild_projections(run.id)
                session.commit()
                session.close()
                
            except Exception as e:
                rebuild_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        def live_update_worker() -> None:
            """Worker that processes new events during rebuild."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                # Create new event during rebuild
                new_encounter = EncounterEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player1.id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=200,  # Different route
                    species_id=150,  # Mewtwo
                    family_id=150,
                    level=70,
                    shiny=False,
                    encounter_method=EncounterMethod.STATIC,
                    rod_kind=None,
                    status=EncounterStatus.FIRST_ENCOUNTER,
                    dupes_skip=False,
                    fe_finalized=False,
                )
                
                envelope = event_store.append(new_encounter)
                session.commit()
                
                # Wait for synchronization  
                barrier.wait()
                
                # Apply new event during rebuild
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                live_update_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run rebuild and live update concurrently
        workers = [
            session_worker(session_factory, rebuild_worker),
            session_worker(session_factory, live_update_worker)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=20.0)
        
        # Assert: No thread errors
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        # No worker errors
        if rebuild_error[0]:
            pytest.fail(f"Rebuild worker failed: {rebuild_error[0]}")
        if live_update_error[0]:
            pytest.fail(f"Live update worker failed: {live_update_error[0]}")
        
        # Verify final state consistency
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).all()
        
        # Should have route progress for all encounters (2 initial + 1 new)
        route_ids = {rp.route_id for rp in route_progress}
        assert 100 in route_ids  # Initial encounter 1
        assert 101 in route_ids  # Initial encounter 2  
        assert 200 in route_ids  # New encounter during rebuild
        
        # Verify event store integrity
        total_events = db_session.query(Event).filter(Event.run_id == run.id).count()
        assert total_events == 3  # 2 initial + 1 new

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.rebuild_race
    def test_multiple_concurrent_rebuilds_idempotent(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that multiple concurrent rebuilds are idempotent and don't corrupt state."""
        # Arrange
        run = make_run("Multi Rebuild Run")
        player = make_player(run.id, "MultiRebuildPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Create events for rebuild
        events = []
        for i in range(5):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=300 + i,
                species_id=100 + i,
                family_id=100 + i,
                level=20,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
            events.append(encounter)
        
        # Create catches to finalize some routes
        for i in [0, 2, 4]:  # Finalize routes 300, 302, 304
            catch = CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=events[i].event_id,
                result=EncounterStatus.CAUGHT,
            )
            
            envelope = event_store.append(catch)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Record expected final state
        expected_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).all()
        expected_blocklist = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id
        ).all()
        
        # Clear projections 
        db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).delete()
        db_session.query(Blocklist).filter(Blocklist.run_id == run.id).delete()
        db_session.commit()
        
        barrier = barrier_factory(3)
        errors: List[Optional[Exception]] = [None, None, None]
        
        def concurrent_rebuild_worker(worker_id: int) -> None:
            """Worker that performs concurrent rebuilds."""
            try:
                session = session_factory()
                projection_engine = ProjectionEngine(session)
                
                # Synchronize all rebuild workers
                barrier.wait()
                
                # All workers rebuild simultaneously
                projection_engine.rebuild_projections(run.id)
                session.commit()
                session.close()
                
            except Exception as e:
                errors[worker_id] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run multiple concurrent rebuilds
        workers = [
            session_worker(session_factory, lambda i=i: concurrent_rebuild_worker(i))
            for i in range(3)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=25.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        for i, error in enumerate(errors):
            if error:
                pytest.fail(f"Rebuild worker {i} failed: {error}")
        
        # Verify final state matches expected (rebuild is idempotent)
        final_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).all()
        final_blocklist = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id
        ).all()
        
        # Same number of entries
        assert len(final_route_progress) == len(expected_route_progress)
        assert len(final_blocklist) == len(expected_blocklist)
        
        # Same route finalization state
        final_finalized = {
            (rp.route_id, rp.player_id): rp.fe_finalized 
            for rp in final_route_progress
        }
        expected_finalized = {
            (rp.route_id, rp.player_id): rp.fe_finalized 
            for rp in expected_route_progress
        }
        assert final_finalized == expected_finalized

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.rebuild_race
    def test_rebuild_with_competing_constraint_violations(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test rebuild behavior when live updates cause constraint violations."""
        # Arrange
        run = make_run("Rebuild Constraint Run")
        player1 = make_player(run.id, "RebuildConstraintPlayer1")
        player2 = make_player(run.id, "RebuildConstraintPlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Create encounters that will compete for finalization
        encounters = []
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=400,  # Same route - will compete
                species_id=144 if player == player1 else 145,  # Articuno vs Zapdos
                family_id=144 if player == player1 else 145,
                level=50,
                shiny=False,
                encounter_method=EncounterMethod.STATIC,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            encounters.append(encounter)
            
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Create one catch event that will finalize during rebuild
        catch_event = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounters[0].event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        catch_envelope = event_store.append(catch_event)
        db_session.commit()
        
        # Clear projections but leave the catch event unapplied
        db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).delete()
        db_session.query(Blocklist).filter(Blocklist.run_id == run.id).delete()
        db_session.commit()
        
        barrier = barrier_factory(2)
        rebuild_error: List[Optional[Exception]] = [None]
        competing_update_error: List[Optional[Exception]] = [None]
        
        def rebuild_with_catch_worker() -> None:
            """Worker that rebuilds including the catch event."""
            try:
                session = session_factory()
                projection_engine = ProjectionEngine(session)
                
                # Wait for sync
                barrier.wait()
                
                # Rebuild will process encounters + catch event
                projection_engine.rebuild_projections(run.id)
                session.commit()
                session.close()
                
            except Exception as e:
                rebuild_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        def competing_finalization_worker() -> None:
            """Worker that tries to finalize the same route via direct event."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                # Create competing finalization event
                fe_event = FirstEncounterFinalizedEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player2.id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=400,
                )
                
                envelope = event_store.append(fe_event)
                session.commit()
                
                # Wait for sync
                barrier.wait()
                
                # Try to finalize during rebuild (should hit constraint)
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                competing_update_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run rebuild with competing finalization
        workers = [
            session_worker(session_factory, rebuild_with_catch_worker),
            session_worker(session_factory, competing_finalization_worker)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=20.0)
        
        # Assert: No thread failures (graceful handling should work)
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        # No worker errors (constraint violations should be handled gracefully)
        if rebuild_error[0]:
            pytest.fail(f"Rebuild worker failed: {rebuild_error[0]}")
        if competing_update_error[0]:
            pytest.fail(f"Competing update worker failed: {competing_update_error[0]}")
        
        # Verify consistent final state - exactly one finalized route
        finalized_routes = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 400,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        assert len(finalized_routes) == 1, "Exactly one route should be finalized"
        
        # Should have route progress for both players
        all_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 400
        ).all()
        
        assert len(all_route_progress) == 2, "Both players should have route progress"

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.rebuild_race
    def test_partial_rebuild_vs_incremental_updates(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that partial rebuilds don't interfere with incremental updates."""
        # Arrange
        run = make_run("Partial Rebuild Run")
        player = make_player(run.id, "PartialRebuildPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Create a series of events with some already processed
        events = []
        
        # First batch: encounters and catches (will be part of rebuild)
        for i in range(3):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=500 + i,
                species_id=200 + i,
                family_id=200 + i,
                level=30,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            events.append(encounter)
            
            envelope = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Apply catches for first 2 encounters
        for i in range(2):
            catch = CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=events[i].event_id,
                result=EncounterStatus.CAUGHT,
            )
            
            envelope = event_store.append(catch)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Partially clear projections (simulate partial corruption)
        db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 501  # Remove middle route only
        ).delete()
        db_session.commit()
        
        barrier = barrier_factory(2)
        rebuild_error: List[Optional[Exception]] = [None]
        incremental_error: List[Optional[Exception]] = [None]
        
        def partial_rebuild_worker() -> None:
            """Worker that performs full rebuild to fix partial corruption."""
            try:
                session = session_factory()
                projection_engine = ProjectionEngine(session)
                
                # Wait for sync
                barrier.wait()
                
                # Full rebuild will restore missing projections
                projection_engine.rebuild_projections(run.id)
                session.commit()
                session.close()
                
            except Exception as e:
                rebuild_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        def incremental_update_worker() -> None:
            """Worker that processes new incremental updates."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                # Create new encounter on different route
                new_encounter = EncounterEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player.id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=600,  # New route
                    species_id=300,
                    family_id=300,
                    level=40,
                    shiny=False,
                    encounter_method=EncounterMethod.SURF,
                    rod_kind=None,
                    status=EncounterStatus.FIRST_ENCOUNTER,
                    dupes_skip=False,
                    fe_finalized=False,
                )
                
                envelope = event_store.append(new_encounter)
                session.commit()
                
                # Wait for sync
                barrier.wait()
                
                # Apply incremental update during rebuild
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                incremental_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run partial rebuild with incremental updates
        workers = [
            session_worker(session_factory, partial_rebuild_worker),
            session_worker(session_factory, incremental_update_worker)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=20.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        if rebuild_error[0]:
            pytest.fail(f"Rebuild worker failed: {rebuild_error[0]}")
        if incremental_error[0]:
            pytest.fail(f"Incremental worker failed: {incremental_error[0]}")
        
        # Verify all projections are present and correct
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).all()
        
        route_ids = {rp.route_id for rp in route_progress}
        expected_routes = {500, 501, 502, 600}  # 3 original + 1 new
        assert route_ids == expected_routes
        
        # Verify finalization states
        finalized_routes = {
            rp.route_id for rp in route_progress 
            if rp.fe_finalized
        }
        expected_finalized = {500, 501}  # First two were caught
        assert finalized_routes == expected_finalized
        
        # Verify blocklist entries
        blocklist_families = {
            b.family_id for b in 
            db_session.query(Blocklist).filter(Blocklist.run_id == run.id).all()
        }
        expected_blocked = {200, 201}  # Families for caught pokemon
        assert blocklist_families == expected_blocked


class TestRebuildEdgeCases:
    """Test edge cases in projection rebuild functionality."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.rebuild_race
    def test_rebuild_empty_run_with_concurrent_events(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test rebuilding an empty run while events are being added."""
        # Arrange
        run = make_run("Empty Rebuild Run")
        player = make_player(run.id, "EmptyRebuildPlayer")
        
        barrier = barrier_factory(2)
        rebuild_error: List[Optional[Exception]] = [None]
        event_creation_error: List[Optional[Exception]] = [None]
        
        def rebuild_empty_worker() -> None:
            """Worker that rebuilds an initially empty run."""
            try:
                session = session_factory()
                projection_engine = ProjectionEngine(session)
                
                # Wait for sync
                barrier.wait()
                
                # Rebuild empty run (should be no-op initially)
                projection_engine.rebuild_projections(run.id)
                session.commit()
                session.close()
                
            except Exception as e:
                rebuild_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        def concurrent_event_creation_worker() -> None:
            """Worker that creates events during empty rebuild."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                # Create event
                encounter = EncounterEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player.id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=700,
                    species_id=400,
                    family_id=400,
                    level=50,
                    shiny=False,
                    encounter_method=EncounterMethod.STATIC,
                    rod_kind=None,
                    status=EncounterStatus.FIRST_ENCOUNTER,
                    dupes_skip=False,
                    fe_finalized=False,
                )
                
                envelope = event_store.append(encounter)
                session.commit()
                
                # Wait for sync
                barrier.wait()
                
                # Apply event during rebuild
                projection_engine.apply_event(envelope)
                session.commit()
                session.close()
                
            except Exception as e:
                event_creation_error[0] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run empty rebuild with concurrent event creation
        workers = [
            session_worker(session_factory, rebuild_empty_worker),
            session_worker(session_factory, concurrent_event_creation_worker)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        if rebuild_error[0]:
            pytest.fail(f"Rebuild worker failed: {rebuild_error[0]}")
        if event_creation_error[0]:
            pytest.fail(f"Event creation worker failed: {event_creation_error[0]}")
        
        # Verify final state has the new event processed
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 700
        ).first()
        
        assert route_progress is not None
        assert route_progress.species_id == 400