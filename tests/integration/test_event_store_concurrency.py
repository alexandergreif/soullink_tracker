"""Event store concurrency and sequence number race tests.

Tests that validate the event store properly handles concurrent appends and maintains
sequence number uniqueness and ordering under high concurrent load. These tests ensure
the event store's atomicity guarantees work correctly.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Set

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.db.models import Event
from src.soullink_tracker.domain.events import (
    EncounterEvent, 
    CatchResultEvent, 
    FamilyBlockedEvent, 
    FirstEncounterFinalizedEvent
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from tests.helpers.concurrency import run_in_threads, session_worker


class TestEventStoreSequencing:
    """Test event store sequence number generation and uniqueness."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_concurrent_appends_maintain_sequence_uniqueness(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that concurrent appends generate unique sequence numbers."""
        # Arrange
        run = make_run("Sequence Uniqueness Run")
        players = [make_player(run.id, f"SeqPlayer{i}") for i in range(5)]
        
        barrier = barrier_factory(5)
        appended_events: List[Optional[Dict]] = [None] * 5
        errors: List[Optional[Exception]] = [None] * 5
        
        def append_worker(worker_id: int) -> None:
            """Worker that appends an event to the event store."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                
                event = EncounterEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=players[worker_id].id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=100 + worker_id,  # Different routes
                    species_id=1 + worker_id,  # Different species
                    family_id=1 + worker_id,
                    level=5,
                    shiny=False,
                    encounter_method=EncounterMethod.GRASS,
                    rod_kind=None,
                    status=EncounterStatus.FIRST_ENCOUNTER,
                    dupes_skip=False,
                    fe_finalized=False,
                )
                
                # Wait for all workers to be ready
                barrier.wait()
                
                # All workers append simultaneously
                envelope = event_store.append(event)
                session.commit()
                session.close()
                
                appended_events[worker_id] = {
                    'event_id': envelope.event_id,
                    'sequence_number': envelope.sequence_number,
                    'event_type': envelope.event_type
                }
                
            except Exception as e:
                errors[worker_id] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run concurrent appends
        workers = [
            session_worker(session_factory, lambda i=i: append_worker(i)) 
            for i in range(5)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No thread errors
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        # No worker errors
        for i, error in enumerate(errors):
            if error:
                pytest.fail(f"Worker {i} had error: {error}")
        
        # All events were appended
        assert all(event is not None for event in appended_events)
        
        # All sequence numbers are unique
        sequence_numbers = [event['sequence_number'] for event in appended_events]
        assert len(set(sequence_numbers)) == 5, "Sequence numbers must be unique"
        
        # Sequence numbers are positive
        assert all(seq > 0 for seq in sequence_numbers)
        
        # Verify in database
        stored_events = db_session.query(Event).filter(
            Event.run_id == run.id
        ).order_by(Event.sequence_number).all()
        
        assert len(stored_events) == 5
        stored_sequences = [e.sequence_number for e in stored_events]
        assert stored_sequences == sorted(stored_sequences), "Events should be ordered by sequence"
        assert set(stored_sequences) == set(sequence_numbers), "DB sequences match returned sequences"

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.stress
    def test_high_volume_concurrent_appends(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Stress test with high volume concurrent appends (20 workers x 5 events each)."""
        # Arrange
        run = make_run("High Volume Run")
        players = [make_player(run.id, f"VolPlayer{i}") for i in range(20)]
        
        barrier = barrier_factory(20)
        results: List[Optional[List[Dict]]] = [None] * 20
        errors: List[Optional[Exception]] = [None] * 20
        
        def bulk_append_worker(worker_id: int) -> None:
            """Worker that appends multiple events."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                
                events = []
                envelopes = []
                
                # Create 5 events per worker
                for event_idx in range(5):
                    event = EncounterEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=players[worker_id].id,
                        timestamp=datetime.now(timezone.utc),
                        route_id=200 + (worker_id * 5) + event_idx,  # Unique routes
                        species_id=50 + (worker_id * 5) + event_idx,  # Unique species
                        family_id=50 + (worker_id * 5) + event_idx,
                        level=10 + event_idx,
                        shiny=False,
                        encounter_method=EncounterMethod.GRASS,
                        rod_kind=None,
                        status=EncounterStatus.FIRST_ENCOUNTER,
                        dupes_skip=False,
                        fe_finalized=False,
                    )
                    events.append(event)
                
                # Wait for all workers
                barrier.wait()
                
                # Append all events for this worker
                for event in events:
                    envelope = event_store.append(event)
                    envelopes.append({
                        'event_id': envelope.event_id,
                        'sequence_number': envelope.sequence_number,
                        'worker_id': worker_id
                    })
                
                session.commit()
                session.close()
                results[worker_id] = envelopes
                
            except Exception as e:
                errors[worker_id] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run high volume concurrent appends
        workers = [
            session_worker(session_factory, lambda i=i: bulk_append_worker(i))
            for i in range(20)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=30.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        for i, error in enumerate(errors):
            if error:
                pytest.fail(f"Worker {i} had error: {error}")
        
        # All workers completed
        assert all(result is not None for result in results)
        
        # Collect all sequence numbers
        all_sequences: Set[int] = set()
        for worker_result in results:
            for envelope in worker_result:
                all_sequences.add(envelope['sequence_number'])
        
        # Total events = 20 workers * 5 events = 100 events
        assert len(all_sequences) == 100, "All 100 events should have unique sequences"
        
        # Verify in database
        total_events = db_session.query(Event).filter(Event.run_id == run.id).count()
        assert total_events == 100
        
        # Verify sequence number continuity
        db_sequences = [
            e.sequence_number for e in 
            db_session.query(Event).filter(Event.run_id == run.id)
            .order_by(Event.sequence_number).all()
        ]
        
        assert db_sequences == sorted(db_sequences), "Sequences should be in order"
        assert set(db_sequences) == all_sequences, "DB sequences should match returned sequences"

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_mixed_event_types_maintain_ordering(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that different event types maintain proper sequence ordering."""
        # Arrange
        run = make_run("Mixed Event Types Run")
        player = make_player(run.id, "MixedPlayer")
        
        # Setup: Create an encounter first
        initial_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=300,
            species_id=25,  # Pikachu
            family_id=25,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        event_store = EventStore(db_session)
        encounter_env = event_store.append(initial_encounter)
        db_session.commit()
        
        # Create different types of events to append concurrently
        events_to_append = [
            CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=encounter_env.event_id,
                result=EncounterStatus.CAUGHT,
            ),
            FamilyBlockedEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                family_id=150,  # Mewtwo
                origin="first_encounter",
            ),
            FirstEncounterFinalizedEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=301,  # Different route
            ),
            EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=302,
                species_id=150,  # Mewtwo
                family_id=150,
                level=70,
                shiny=False,
                encounter_method=EncounterMethod.STATIC,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            ),
        ]
        
        barrier = barrier_factory(4)
        results: List[Optional[Dict]] = [None] * 4
        errors: List[Optional[Exception]] = [None] * 4
        
        def append_event_worker(event_idx: int) -> None:
            """Worker that appends a specific event type."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                
                # Wait for synchronization
                barrier.wait()
                
                # Append the event
                envelope = event_store.append(events_to_append[event_idx])
                session.commit()
                session.close()
                
                results[event_idx] = {
                    'event_type': envelope.event_type,
                    'sequence_number': envelope.sequence_number,
                    'event_id': envelope.event_id
                }
                
            except Exception as e:
                errors[event_idx] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run concurrent mixed event appends
        workers = [
            session_worker(session_factory, lambda i=i: append_event_worker(i))
            for i in range(4)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        for i, error in enumerate(errors):
            if error:
                pytest.fail(f"Worker {i} had error: {error}")
        
        # All events appended successfully
        assert all(result is not None for result in results)
        
        # All sequence numbers are unique and greater than the initial encounter
        sequence_numbers = [result['sequence_number'] for result in results]
        assert len(set(sequence_numbers)) == 4, "All sequences must be unique"
        assert all(seq > encounter_env.sequence_number for seq in sequence_numbers)
        
        # Verify in database - should have 5 total events (1 initial + 4 concurrent)
        all_events = db_session.query(Event).filter(
            Event.run_id == run.id
        ).order_by(Event.sequence_number).all()
        
        assert len(all_events) == 5
        
        # Sequence numbers should be consecutive and ordered
        db_sequences = [e.sequence_number for e in all_events]
        assert db_sequences == sorted(db_sequences)
        
        # Event types should be preserved
        concurrent_events = [e for e in all_events if e.sequence_number > encounter_env.sequence_number]
        event_types = [e.event_type for e in concurrent_events]
        expected_types = {'CatchResultEvent', 'FamilyBlockedEvent', 'FirstEncounterFinalizedEvent', 'EncounterEvent'}
        assert set(event_types) == expected_types

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_sequence_gaps_do_not_occur(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that sequence numbers have no gaps even under concurrent load."""
        # Arrange
        run = make_run("No Gaps Run")
        players = [make_player(run.id, f"GapPlayer{i}") for i in range(10)]
        
        barrier = barrier_factory(10)
        sequences: List[Optional[int]] = [None] * 10
        errors: List[Optional[Exception]] = [None] * 10
        
        def gap_test_worker(worker_id: int) -> None:
            """Worker that appends events and records sequence numbers."""
            try:
                session = session_factory()
                event_store = EventStore(session)
                
                event = EncounterEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=players[worker_id].id,
                    timestamp=datetime.now(timezone.utc),
                    route_id=400 + worker_id,
                    species_id=worker_id + 1,
                    family_id=worker_id + 1,
                    level=15,
                    shiny=False,
                    encounter_method=EncounterMethod.GRASS,
                    rod_kind=None,
                    status=EncounterStatus.FIRST_ENCOUNTER,
                    dupes_skip=False,
                    fe_finalized=False,
                )
                
                # Synchronize all workers
                barrier.wait()
                
                envelope = event_store.append(event)
                session.commit()
                session.close()
                
                sequences[worker_id] = envelope.sequence_number
                
            except Exception as e:
                errors[worker_id] = e
                if 'session' in locals():
                    try:
                        session.rollback()
                        session.close()
                    except:
                        pass
        
        # Act: Run gap test workers
        workers = [
            session_worker(session_factory, lambda i=i: gap_test_worker(i))
            for i in range(10)
        ]
        
        thread_errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No failures
        for i, error in enumerate(thread_errors):
            if error:
                pytest.fail(f"Thread {i} failed: {error}")
        
        for i, error in enumerate(errors):
            if error:
                pytest.fail(f"Worker {i} had error: {error}")
        
        # All sequences recorded
        assert all(seq is not None for seq in sequences)
        
        # Sort sequences and check for gaps
        sorted_sequences = sorted(sequences)
        for i in range(1, len(sorted_sequences)):
            gap = sorted_sequences[i] - sorted_sequences[i-1]
            assert gap == 1, f"Gap detected: {sorted_sequences[i-1]} -> {sorted_sequences[i]} (gap: {gap})"
        
        # Verify database consistency
        db_events = db_session.query(Event).filter(
            Event.run_id == run.id
        ).order_by(Event.sequence_number).all()
        
        assert len(db_events) == 10
        
        db_sequences = [e.sequence_number for e in db_events]
        assert db_sequences == sorted_sequences, "DB sequences should match worker sequences"


class TestEventStoreBoundaryConditions:
    """Test event store behavior under boundary conditions."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_rapid_sequential_appends_from_single_session(
        self, db_session, make_run, make_player
    ):
        """Test rapid sequential appends from a single session maintain order."""
        # Arrange
        run = make_run("Rapid Sequential Run")
        player = make_player(run.id, "RapidPlayer")
        
        event_store = EventStore(db_session)
        
        # Create 50 events to append rapidly
        events = []
        for i in range(50):
            event = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=500 + i,
                species_id=i + 1,
                family_id=i + 1,
                level=10,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            events.append(event)
        
        # Act: Append all events rapidly in sequence
        envelopes = []
        for event in events:
            envelope = event_store.append(event)
            envelopes.append(envelope)
        
        db_session.commit()
        
        # Assert: Sequence numbers should be consecutive
        sequences = [env.sequence_number for env in envelopes]
        assert len(sequences) == 50
        assert sequences == sorted(sequences), "Sequences should be ordered"
        
        # Check for consecutive numbering
        for i in range(1, len(sequences)):
            assert sequences[i] == sequences[i-1] + 1, "Sequences should be consecutive"
        
        # Verify in database
        db_events = db_session.query(Event).filter(
            Event.run_id == run.id
        ).order_by(Event.sequence_number).all()
        
        assert len(db_events) == 50
        db_sequences = [e.sequence_number for e in db_events]
        assert db_sequences == sequences