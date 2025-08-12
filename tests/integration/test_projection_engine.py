"""Integration tests for ProjectionEngine correctness.

Tests the core V3 projection engine functionality including:
- Projections built from events using pure rules engine  
- Event replay equivalence for projection rebuilding
- Integration between pure rules and ProjectionEngine
- All event types and their projection effects
- Edge cases: race conditions, constraint violations, rollback scenarios
"""

import pytest
import uuid
from datetime import datetime, timezone

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine, ProjectionError
from src.soullink_tracker.db.models import RouteProgress, Blocklist, PartyStatus
from src.soullink_tracker.domain.events import (
    EncounterEvent, 
    CatchResultEvent, 
    FaintEvent, 
    FamilyBlockedEvent, 
    FirstEncounterFinalizedEvent
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus


class TestProjectionEngineCorrectness:
    """Test projection engine correctness with real database operations."""

    @pytest.mark.v3_only
    def test_apply_encounter_builds_route_progress(self, db_session, make_run, make_player):
        """Test that encounter events build route progress projections."""
        # Arrange
        run = make_run("Projection Test Run")
        player = make_player(run.id, "ProjectionPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=10,
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
        
        # Act
        envelope = event_store.append(encounter)
        db_session.commit()
        
        projection_engine.apply_event(envelope)
        db_session.commit()
        
        # Assert
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == 10
        ).first()
        
        assert route_progress is not None
        assert route_progress.fe_finalized is False
        
        # No blocklist entry for just encounter
        blocked_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 25
        ).count()
        assert blocked_count == 0

    @pytest.mark.v3_only
    def test_catch_result_finalizes_and_blocks(self, db_session, make_run, make_player):
        """Test that catch result events finalize route progress and add to blocklist."""
        # Arrange
        run = make_run("Catch Result Test Run")
        player = make_player(run.id, "CatchPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # First, create and apply encounter
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=11,
            species_id=4,  # Charmander
            family_id=4,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        encounter_envelope = event_store.append(encounter)
        db_session.commit()
        projection_engine.apply_event(encounter_envelope)
        db_session.commit()
        
        # Now create catch result
        catch_result = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter.event_id,
            status=EncounterStatus.CAUGHT,  # Using status for compatibility
        )
        
        # Act
        catch_envelope = event_store.append(catch_result)
        db_session.commit()
        projection_engine.apply_event(catch_envelope)
        db_session.commit()
        
        # Assert
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == 11
        ).first()
        
        assert route_progress is not None
        assert route_progress.fe_finalized is True
        
        # Family should be blocked with origin="caught"
        blocklist_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 4
        ).first()
        
        assert blocklist_entry is not None
        assert blocklist_entry.origin == "caught"

    @pytest.mark.v3_only 
    def test_faint_updates_party_status(self, db_session, make_run, make_player):
        """Test that faint events update party status projections."""
        # Arrange
        run = make_run("Faint Test Run")
        player = make_player(run.id, "FaintPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        faint_time = datetime.now(timezone.utc)
        faint_event = FaintEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=faint_time,
            pokemon_key="pikachu_001",
        )
        
        # Act
        envelope = event_store.append(faint_event)
        db_session.commit()
        projection_engine.apply_event(envelope)
        db_session.commit()
        
        # Assert
        party_status = db_session.query(PartyStatus).filter(
            PartyStatus.run_id == run.id,
            PartyStatus.player_id == player.id,
            PartyStatus.pokemon_key == "pikachu_001"
        ).first()
        
        assert party_status is not None
        assert party_status.alive is False
        # Compare timestamps without timezone (DB stores naive datetime)
        assert party_status.last_update == faint_time.replace(tzinfo=None)

    @pytest.mark.v3_only
    def test_rebuild_projections_matches_direct_application(self, db_session, make_run, make_player):
        """Test that rebuilding projections from event replay produces identical results."""
        # Arrange
        run = make_run("Rebuild Test Run")
        player = make_player(run.id, "RebuildPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create sequence of events
        encounter_id = uuid.uuid4()
        encounter = EncounterEvent(
            event_id=encounter_id,
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=12,
            species_id=7,  # Squirtle
            family_id=7,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        catch_result = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter_id,
            status=EncounterStatus.CAUGHT,
        )
        
        faint_event = FaintEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            pokemon_key="squirtle_001",
        )
        
        # Store all events
        envelopes = []
        for event in [encounter, catch_result, faint_event]:
            envelope = event_store.append(event)
            envelopes.append(envelope)
        db_session.commit()
        
        # Apply events directly to build initial state
        for envelope in envelopes:
            projection_engine.apply_event(envelope)
        db_session.commit()
        
        # Snapshot the results
        route_progress = db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).all()
        blocklist = db_session.query(Blocklist).filter(Blocklist.run_id == run.id).all()  
        party_status = db_session.query(PartyStatus).filter(PartyStatus.run_id == run.id).all()
        
        initial_route_count = len(route_progress)
        initial_block_count = len(blocklist)
        initial_party_count = len(party_status)
        initial_fe_finalized = route_progress[0].fe_finalized if route_progress else None
        initial_block_origin = blocklist[0].origin if blocklist else None
        initial_party_alive = party_status[0].alive if party_status else None
        
        # Act: Clear and rebuild from event replay
        projection_engine._clear_projections(run.id)
        db_session.commit()
        
        # Verify cleared
        assert db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).count() == 0
        assert db_session.query(Blocklist).filter(Blocklist.run_id == run.id).count() == 0
        assert db_session.query(PartyStatus).filter(PartyStatus.run_id == run.id).count() == 0
        
        # Rebuild from events
        all_events = event_store.get_events(run.id)
        projection_engine.rebuild_all_projections(run.id, all_events)
        db_session.commit()
        
        # Assert: Results match the snapshot
        rebuilt_route_progress = db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).all()
        rebuilt_blocklist = db_session.query(Blocklist).filter(Blocklist.run_id == run.id).all()
        rebuilt_party_status = db_session.query(PartyStatus).filter(PartyStatus.run_id == run.id).all()
        
        assert len(rebuilt_route_progress) == initial_route_count
        assert len(rebuilt_blocklist) == initial_block_count
        assert len(rebuilt_party_status) == initial_party_count
        
        if rebuilt_route_progress:
            assert rebuilt_route_progress[0].fe_finalized == initial_fe_finalized
        if rebuilt_blocklist:
            assert rebuilt_blocklist[0].origin == initial_block_origin
        if rebuilt_party_status:
            assert rebuilt_party_status[0].alive == initial_party_alive

    @pytest.mark.v3_only
    def test_dupe_skip_after_route_finalization(self, db_session, make_run, make_player):
        """Test that encounters are marked as dupe-skip after route is finalized."""
        # Arrange
        run = make_run("Dupe Skip Test Run")
        player1 = make_player(run.id, "Player1")
        player2 = make_player(run.id, "Player2") 
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Player1: encounter + catch to finalize route
        p1_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=13,
            species_id=1,  # Bulbasaur
            family_id=1,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        p1_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p1_encounter.event_id,
            status=EncounterStatus.CAUGHT,
        )
        
        # Apply player1 events to finalize route
        for event in [p1_encounter, p1_catch]:
            envelope = event_store.append(event)
            db_session.commit()
            projection_engine.apply_event(envelope)
            db_session.commit()
        
        # Player2: encounter on same route after finalization
        p2_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=13,  # Same route
            species_id=4,  # Different species (Charmander)
            family_id=4,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,  # Will be overridden by projection logic
            fe_finalized=False,
        )
        
        # Act: Apply player2 encounter after route is finalized
        p2_envelope = event_store.append(p2_encounter)
        db_session.commit()
        projection_engine.apply_event(p2_envelope)
        db_session.commit()
        
        # Assert: Player2 should NOT have route progress (dupe-skip behavior)
        p2_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player2.id,
            RouteProgress.route_id == 13
        ).first()
        
        # Should be None due to dupe-skip decision in projection
        assert p2_route_progress is None
        
        # Player1's route progress should still exist and be finalized
        p1_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player1.id,
            RouteProgress.route_id == 13
        ).first()
        
        assert p1_route_progress is not None
        assert p1_route_progress.fe_finalized is True

    @pytest.mark.v3_only
    def test_race_condition_single_finalized_route(self, db_session, make_run, make_player):
        """Test race condition handling when multiple players try to finalize same route."""
        # Arrange
        run = make_run("Race Condition Test Run")
        player1 = make_player(run.id, "RacePlayer1")
        player2 = make_player(run.id, "RacePlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create encounters for both players on same route
        p1_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=14,
            species_id=16,  # Pidgey
            family_id=16,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        p2_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=14,  # Same route
            species_id=19,  # Rattata
            family_id=19,
            level=3,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        # Store both encounters
        p1_env = event_store.append(p1_encounter)
        p2_env = event_store.append(p2_encounter)
        db_session.commit()
        
        # Apply both encounters
        projection_engine.apply_event(p1_env)
        projection_engine.apply_event(p2_env)
        db_session.commit()
        
        # Create catch results for both
        p1_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p1_encounter.event_id,
            status=EncounterStatus.CAUGHT,
        )
        
        p2_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p2_encounter.event_id,
            status=EncounterStatus.CAUGHT,
        )
        
        # Act: Apply player1 catch first (should finalize)
        p1_catch_env = event_store.append(p1_catch)
        db_session.commit()
        projection_engine.apply_event(p1_catch_env)
        db_session.commit()
        
        # Apply player2 catch second (should hit race condition)
        p2_catch_env = event_store.append(p2_catch)
        db_session.commit()
        projection_engine.apply_event(p2_catch_env)  # Should handle IntegrityError gracefully
        db_session.commit()
        
        # Assert: Exactly one route progress should be fe_finalized=True
        finalized_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 14,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        assert len(finalized_progress) == 1
        assert finalized_progress[0].player_id == player1.id  # First player won
        
        # Player2's route progress should exist but not be finalized
        p2_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player2.id,
            RouteProgress.route_id == 14
        ).first()
        
        assert p2_progress is not None
        assert p2_progress.fe_finalized is False

    @pytest.mark.v3_only
    def test_blocklist_origin_priority_upgrade(self, db_session, make_run, make_player):
        """Test that blocklist origins are upgraded to higher priority (caught > first_encounter > faint)."""
        # Arrange
        run = make_run("Blocklist Priority Test Run")
        player = make_player(run.id, "BlocklistPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create a family blocked event with lower priority origin
        family_blocked = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=50,  # Diglett family
            origin="faint",  # Lower priority
        )
        
        family_env = event_store.append(family_blocked)
        db_session.commit()
        projection_engine.apply_event(family_env)
        db_session.commit()
        
        # Verify initial blocklist entry
        initial_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 50
        ).first()
        
        assert initial_entry is not None
        assert initial_entry.origin == "faint"
        
        # Now create a higher priority event (caught)
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=15,
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
        
        catch_result = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter.event_id,
            status=EncounterStatus.CAUGHT,
        )
        
        # Act: Apply higher priority events
        enc_env = event_store.append(encounter)
        catch_env = event_store.append(catch_result)
        db_session.commit()
        
        projection_engine.apply_event(enc_env)
        projection_engine.apply_event(catch_env)
        db_session.commit()
        
        # Assert: Origin should be upgraded to "caught"
        updated_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 50
        ).first()
        
        assert updated_entry is not None
        assert updated_entry.origin == "caught"  # Upgraded from "faint"

    @pytest.mark.v3_only
    def test_catch_result_without_known_encounter_raises(self, db_session, make_run, make_player):
        """Test that catch result without corresponding encounter raises ProjectionError."""
        # Arrange
        run = make_run("Invalid Catch Test Run")
        player = make_player(run.id, "InvalidPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create catch result without corresponding encounter
        invalid_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=uuid.uuid4(),  # Non-existent encounter
            status=EncounterStatus.CAUGHT,
        )
        
        envelope = event_store.append(invalid_catch)
        db_session.commit()
        
        # Count projections before
        initial_route_count = db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).count()
        initial_block_count = db_session.query(Blocklist).filter(Blocklist.run_id == run.id).count()
        
        # Act & Assert: Should raise ProjectionError
        with pytest.raises(ProjectionError) as exc_info:
            projection_engine.apply_event(envelope)
        
        assert "not found in event store" in str(exc_info.value)
        
        # Verify no projection changes were committed
        final_route_count = db_session.query(RouteProgress).filter(RouteProgress.run_id == run.id).count()
        final_block_count = db_session.query(Blocklist).filter(Blocklist.run_id == run.id).count()
        
        assert final_route_count == initial_route_count
        assert final_block_count == initial_block_count

    @pytest.mark.v3_only
    def test_first_encounter_finalized_event_handler_targets_correct_player(self, db_session, make_run, make_player):
        """Test that FirstEncounterFinalizedEvent only affects the correct player's route progress."""
        # Arrange  
        run = make_run("FE Finalized Test Run")
        player1 = make_player(run.id, "FEPlayer1")
        player2 = make_player(run.id, "FEPlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create encounters for both players on same route
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=16,
                species_id=72 if player == player1 else 73,  # Different species
                family_id=72 if player == player1 else 73,
                level=5,
                shiny=False,
                encounter_method=EncounterMethod.SURF,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            
            env = event_store.append(encounter)
            db_session.commit()
            projection_engine.apply_event(env)
            db_session.commit()
        
        # Both should have unfinalized route progress
        for player in [player1, player2]:
            progress = db_session.query(RouteProgress).filter(
                RouteProgress.run_id == run.id,
                RouteProgress.player_id == player.id,
                RouteProgress.route_id == 16
            ).first()
            assert progress is not None
            assert progress.fe_finalized is False
        
        # Create FirstEncounterFinalizedEvent for player1 only
        fe_finalized = FirstEncounterFinalizedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=16,
        )
        
        # Act
        env = event_store.append(fe_finalized)
        db_session.commit()
        projection_engine.apply_event(env)
        db_session.commit()
        
        # Assert: Only player1's route progress should be finalized
        p1_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player1.id,
            RouteProgress.route_id == 16
        ).first()
        
        p2_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player2.id,
            RouteProgress.route_id == 16
        ).first()
        
        assert p1_progress is not None
        assert p1_progress.fe_finalized is True  # Finalized
        
        assert p2_progress is not None  
        assert p2_progress.fe_finalized is False  # Still unfinalized