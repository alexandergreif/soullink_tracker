"""Integration tests for event store persistence and replay functionality.

Tests the core V3 event store architecture including:
- Event persistence with proper sequence numbers
- Event replay and projection rebuilding
- Cross-scenario compatibility (V2, V3, dual-write)
- Database constraint enforcement
"""

import pytest
import uuid
from datetime import datetime, timezone

from src.soullink_tracker.domain.events import EncounterEvent, CatchResultEvent, FaintEvent
from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus


class TestEventStorePersistence:
    """Test event store persistence and replay functionality."""

    @pytest.mark.v3_only
    def test_encounter_event_persistence(self, db_session, make_run, make_player):
        """Test that encounter events are properly persisted with sequence numbers."""
        # Create test data
        run = make_run("Event Store Test Run")
        player = make_player(run.id, "TestPlayer")
        
        # Create event store
        event_store = EventStore(db_session)
        
        # Create encounter event
        encounter_event = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=31,
            species_id=25,  # Pikachu
            family_id=25,   # Pikachu family
            level=5,
            shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False
        )
        
        # Store event
        envelope = event_store.append(encounter_event)
        db_session.commit()
        
        # Verify event was stored with proper sequence
        assert envelope.sequence_number == 1
        assert envelope.event.event_id == encounter_event.event_id
        assert envelope.event.run_id == run.id
        assert envelope.event.player_id == player.id
        
        # Retrieve events
        events = event_store.get_events(run.id)
        assert len(events) == 1
        
        retrieved_event = events[0].event
        assert isinstance(retrieved_event, EncounterEvent)
        assert retrieved_event.route_id == 31
        assert retrieved_event.species_id == 25
        assert retrieved_event.encounter_method == EncounterMethod.GRASS

    @pytest.mark.v3_only  
    def test_multiple_events_sequence_ordering(self, db_session, make_run, make_player):
        """Test that multiple events maintain proper sequence ordering."""
        run = make_run("Sequence Test Run")
        player1 = make_player(run.id, "Player1")
        player2 = make_player(run.id, "Player2")
        
        event_store = EventStore(db_session)
        
        # Create multiple events
        events = [
            EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player1.id,
                timestamp=datetime.now(timezone.utc),
                route_id=30,
                species_id=19,  # Rattata
                family_id=19,
                level=3,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False
            ),
            CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player1.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=uuid.uuid4(),  # Would normally reference the encounter
                status=EncounterStatus.CAUGHT
            ),
            EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player2.id,
                timestamp=datetime.now(timezone.utc),
                route_id=31,
                species_id=16,  # Pidgey
                family_id=16,
                level=4,
                shiny=True,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False
            )
        ]
        
        # Store events and collect sequence numbers
        sequences = []
        for event in events:
            envelope = event_store.append(event)
            sequences.append(envelope.sequence_number)
        
        db_session.commit()
        
        # Verify sequence numbers are sequential
        assert sequences == [1, 2, 3]
        
        # Retrieve and verify ordering
        retrieved = event_store.get_events(run.id)
        assert len(retrieved) == 3
        
        # Events should be in sequence order
        for i, envelope in enumerate(retrieved):
            assert envelope.sequence_number == i + 1

    @pytest.mark.v3_only
    def test_event_store_replay_with_projections(self, db_session, make_run, make_player):
        """Test complete event replay and projection rebuilding."""
        run = make_run("Replay Test Run")
        player = make_player(run.id, "ReplayPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create sequence of events that should affect projections
        encounter_id = uuid.uuid4()
        events = [
            # 1. Encounter event
            EncounterEvent(
                event_id=encounter_id,
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=32,
                species_id=129,  # Magikarp
                family_id=129,
                level=10,
                shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
            ),
            # 2. Catch result
            CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=encounter_id,
                status=EncounterStatus.CAUGHT
            ),
            # 3. Faint event
            FaintEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                pokemon_key="magikarp_001"
            )
        ]
        
        # Store all events
        envelopes = []
        for event in events:
            envelope = event_store.append(event)
            envelopes.append(envelope)
        
        db_session.commit()
        
        # Apply events to projections
        for envelope in envelopes:
            projection_engine.apply_event(envelope)
        
        db_session.commit()
        
        # Verify projections were created
        from src.soullink_tracker.db.models import RouteProgress, Blocklist, PartyStatus
        
        # Check route progress
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == 32
        ).first()
        assert route_progress is not None
        assert route_progress.fe_finalized is True  # Should be finalized after catch
        
        # Check blocklist (family should be blocked after catch)
        blocked = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 129
        ).first()
        assert blocked is not None
        assert blocked.origin == "caught"
        
        # Check party status (should show as dead after faint)
        party_status = db_session.query(PartyStatus).filter(
            PartyStatus.run_id == run.id,
            PartyStatus.player_id == player.id,
            PartyStatus.pokemon_key == "magikarp_001"
        ).first()
        assert party_status is not None
        assert party_status.alive is False
        
        # Now test replay: clear projections and rebuild
        projection_engine._clear_projections(run.id)
        db_session.commit()
        
        # Verify projections are cleared
        assert db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).count() == 0
        assert db_session.query(Blocklist).filter(Blocklist.run_id == run.id).count() == 0
        assert db_session.query(PartyStatus).filter(PartyStatus.run_id == run.id).count() == 0
        
        # Replay events
        all_events = event_store.get_events(run.id)
        projection_engine.rebuild_all_projections(run.id, all_events)
        db_session.commit()
        
        # Verify projections are restored identically
        rebuilt_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == 32
        ).first()
        assert rebuilt_route_progress is not None
        assert rebuilt_route_progress.fe_finalized is True
        
        rebuilt_blocked = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 129
        ).first()
        assert rebuilt_blocked is not None
        assert rebuilt_blocked.origin == "caught"
        
        rebuilt_party_status = db_session.query(PartyStatus).filter(
            PartyStatus.run_id == run.id,
            PartyStatus.player_id == player.id,
            PartyStatus.pokemon_key == "magikarp_001"
        ).first()
        assert rebuilt_party_status is not None
        assert rebuilt_party_status.alive is False

    @pytest.mark.v3_only
    def test_event_type_filtering(self, db_session, make_run, make_player):
        """Test filtering events by type from the event store."""
        run = make_run("Filter Test Run")
        player = make_player(run.id, "FilterPlayer")
        
        event_store = EventStore(db_session)
        
        # Create mixed event types
        encounter_event = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=33,
            species_id=74,  # Geodude
            family_id=74,
            level=8,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        catch_event = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter_event.event_id,
            status=EncounterStatus.CAUGHT
        )
        
        faint_event = FaintEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            pokemon_key="geodude_001"
        )
        
        # Store all events
        for event in [encounter_event, catch_event, faint_event]:
            event_store.append(event)
        
        db_session.commit()
        
        # Test filtering by type
        encounter_events = event_store.get_events(run.id, event_types=["encounter"])
        assert len(encounter_events) == 1
        assert isinstance(encounter_events[0].event, EncounterEvent)
        
        catch_events = event_store.get_events(run.id, event_types=["catch_result"])
        assert len(catch_events) == 1
        assert isinstance(catch_events[0].event, CatchResultEvent)
        
        faint_events = event_store.get_events(run.id, event_types=["faint"])
        assert len(faint_events) == 1
        assert isinstance(faint_events[0].event, FaintEvent)

    @pytest.mark.v3_only
    def test_concurrent_event_sequence_safety(self, db_session, make_run, make_player):
        """Test that concurrent event storage maintains sequence integrity."""
        run = make_run("Concurrent Test Run") 
        player1 = make_player(run.id, "ConcurrentPlayer1")
        player2 = make_player(run.id, "ConcurrentPlayer2")
        
        event_store = EventStore(db_session)
        
        # Simulate concurrent event creation (same timestamp)
        timestamp = datetime.now(timezone.utc)
        
        event1 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=timestamp,
            route_id=34,
            species_id=60,  # Poliwag
            family_id=60,
            level=15,
            shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        event2 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=timestamp,  # Same timestamp
            route_id=34,  # Same route
            species_id=72,  # Tentacool
            family_id=72,
            level=16,
            shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        # Store events in rapid succession
        envelope1 = event_store.append(event1)
        envelope2 = event_store.append(event2)
        
        db_session.commit()
        
        # Verify both events got unique sequence numbers
        assert envelope1.sequence_number != envelope2.sequence_number
        assert envelope1.sequence_number in [1, 2]
        assert envelope2.sequence_number in [1, 2]
        
        # Verify both events are retrievable
        events = event_store.get_events(run.id)
        assert len(events) == 2
        
        # Events should be ordered by sequence
        assert events[0].sequence_number < events[1].sequence_number


class TestCrossScenarioCompatibility:
    """Test that event store works across V2/V3/dual-write scenarios."""
    
    def test_event_store_data_compatibility(self, db_session, make_run, make_player):
        """Test that event store data can be read regardless of scenario configuration."""
        # This test verifies that event store data persisted in one scenario
        # can be read correctly in any other scenario
        
        run = make_run("Compatibility Test Run")
        player = make_player(run.id, "CompatPlayer")
        
        # Store an event using direct event store (simulating V3-only storage)
        event_store = EventStore(db_session)
        
        encounter_event = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=35,
            species_id=1,  # Bulbasaur
            family_id=1,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        # Actually store the event in the event store
        event_store.append(encounter_event)
        db_session.commit()
        
        # Verify the event can be retrieved using the same event store instance
        retrieved_events = event_store.get_events(run.id)
        assert len(retrieved_events) == 1
        
        retrieved_event = retrieved_events[0].event
        assert retrieved_event.event_id == encounter_event.event_id
        assert retrieved_event.route_id == 35
        assert retrieved_event.species_id == 1
        
        # Create a new event store instance (simulating different scenario)
        new_event_store = EventStore(db_session)
        
        # Should still be able to read the same data
        same_events = new_event_store.get_events(run.id)
        assert len(same_events) == 1
        assert same_events[0].event.event_id == encounter_event.event_id