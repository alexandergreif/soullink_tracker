"""Enhanced race condition tests for multi-player scenarios.

Tests complex concurrent scenarios with 3+ players competing simultaneously,
high-volume stress testing, and cross-event-type races that could occur in
real Pokemon SoulLink runs.
"""

import pytest
import uuid
from datetime import datetime, timezone

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.db.models import RouteProgress, Blocklist
from src.soullink_tracker.domain.events import (
    EncounterEvent,
    CatchResultEvent,
    FirstEncounterFinalizedEvent,
    FamilyBlockedEvent,
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from tests.helpers.concurrency import run_in_threads, session_worker


def append_apply_commit(event_store, projection_engine, event, db_session):
    """Helper to append event, apply via engine, and commit."""
    envelope = event_store.append(event)
    db_session.commit()
    projection_engine.apply_event(envelope)
    db_session.commit()
    return envelope


class TestEnhancedMultiPlayerRaces:
    """Test complex multi-player race scenarios."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_three_players_compete_to_finalize_single_route(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test that exactly one player can finalize a route when 3 players compete."""
        # Arrange: Create run and 3 players
        run = make_run("Three Player Route Race")
        player_a = make_player(run.id, "PlayerA")
        player_b = make_player(run.id, "PlayerB") 
        player_c = make_player(run.id, "PlayerC")
        
        route_id = 31
        family_id = 129  # Magikarp family
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Step 1: Each player has an encounter on the same route (sequential)
        encounters = []
        for i, player in enumerate([player_a, player_b, player_c]):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=route_id,
                species_id=129,
                family_id=family_id,
                level=5 + i,
                encounter_method=EncounterMethod.SURF,
                status=EncounterStatus.FIRST_ENCOUNTER,
            )
            encounters.append(encounter)
            append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Verify all players have route progress (fe_finalized=False)
        route_progress_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id
        ).count()
        assert route_progress_count == 3
        
        # Step 2: Concurrent catch results - race to finalize
        barrier = barrier_factory(3)
        
        def make_catch_worker(player, encounter):
            def worker(session):
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                catch_result = CatchResultEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player.id,
                    timestamp=datetime.now(timezone.utc),
                    encounter_id=encounter.event_id,
                    status=EncounterStatus.CAUGHT
                )
                
                # Synchronize start
                barrier.wait()
                
                # Apply catch result
                append_apply_commit(event_store, projection_engine, catch_result, session)
                
            return session_worker(session_factory, worker)
        
        # Execute concurrent catch results
        workers = [
            make_catch_worker(player_a, encounters[0]),
            make_catch_worker(player_b, encounters[1]),
            make_catch_worker(player_c, encounters[2])
        ]
        
        errors = run_in_threads(workers, join_timeout=15.0)
        
        # Assert: No errors occurred (graceful handling worked)
        assert all(error is None for error in errors), f"Errors occurred: {errors}"
        
        # Assert: Exactly one route has fe_finalized=True
        finalized_routes = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        unfinalized_routes = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id,
            RouteProgress.fe_finalized.is_(False)
        ).all()
        
        assert len(finalized_routes) == 1, f"Expected 1 finalized route, got {len(finalized_routes)}"
        assert len(unfinalized_routes) == 2, f"Expected 2 unfinalized routes, got {len(unfinalized_routes)}"
        
        # Assert: Exactly one blocklist entry for the family
        blocklist_entries = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == family_id
        ).all()
        
        assert len(blocklist_entries) == 1, f"Expected 1 blocklist entry, got {len(blocklist_entries)}"
        assert blocklist_entries[0].origin == "caught"

    @pytest.mark.v3_only 
    @pytest.mark.concurrency
    @pytest.mark.stress
    def test_high_volume_competing_catches(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Stress test with 10 players competing for route finalization."""
        # Arrange: Create run and 10 players
        run = make_run("High Volume Route Race")
        players = [make_player(run.id, f"Player{i:02d}") for i in range(10)]
        
        route_id = 42
        family_id = 25  # Pikachu family
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Step 1: Each player encounters on the same route
        encounters = []
        for i, player in enumerate(players):
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=route_id,
                species_id=25,
                family_id=family_id,
                level=10 + i,
                encounter_method=EncounterMethod.GRASS,
                status=EncounterStatus.FIRST_ENCOUNTER,
            )
            encounters.append(encounter)
            append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Step 2: All players attempt to catch simultaneously
        barrier = barrier_factory(10)
        
        def make_catch_worker(player, encounter):
            def worker(session):
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                catch_result = CatchResultEvent(
                    event_id=uuid.uuid4(),
                    run_id=run.id,
                    player_id=player.id,
                    timestamp=datetime.now(timezone.utc),
                    encounter_id=encounter.event_id,
                    status=EncounterStatus.CAUGHT
                )
                
                barrier.wait()  # Synchronize start
                append_apply_commit(event_store, projection_engine, catch_result, session)
                
            return session_worker(session_factory, worker)
        
        workers = [
            make_catch_worker(player, encounter)
            for player, encounter in zip(players, encounters)
        ]
        
        errors = run_in_threads(workers, join_timeout=20.0)
        
        # Assert: No errors (all constraint violations handled gracefully)
        assert all(error is None for error in errors), f"Errors occurred: {errors}"
        
        # Assert: Exactly one finalized route
        finalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id,
            RouteProgress.fe_finalized.is_(True)
        ).count()
        
        unfinalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id,
            RouteProgress.fe_finalized.is_(False)
        ).count()
        
        assert finalized_count == 1, f"Expected 1 finalized route, got {finalized_count}"
        assert unfinalized_count == 9, f"Expected 9 unfinalized routes, got {unfinalized_count}"
        
        # Assert: Single blocklist entry
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == family_id
        ).count()
        
        assert blocklist_count == 1, f"Expected 1 blocklist entry, got {blocklist_count}"


class TestCrossEventTypeRaces:
    """Test races between different event types."""

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_fe_finalized_event_vs_catch_result_race(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test FirstEncounterFinalizedEvent racing with CatchResultEvent."""
        # Arrange: Create run, player, and initial encounter
        run = make_run("FE vs Catch Race")
        player = make_player(run.id, "RacePlayer")
        
        route_id = 15
        family_id = 1  # Bulbasaur family
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Initial encounter (creates route_progress with fe_finalized=False)
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=route_id,
            species_id=1,
            family_id=family_id,
            level=5,
            encounter_method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Verify initial state
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == route_id
        ).one()
        assert not route_progress.fe_finalized
        
        # Prepare competing operations
        barrier = barrier_factory(2)
        
        def fe_finalized_worker(session):
            event_store = EventStore(session)
            projection_engine = ProjectionEngine(session)
            
            fe_event = FirstEncounterFinalizedEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=route_id,
            )
            
            barrier.wait()  # Synchronize start
            append_apply_commit(event_store, projection_engine, fe_event, session)
        
        def catch_result_worker(session):
            event_store = EventStore(session)
            projection_engine = ProjectionEngine(session)
            
            catch_result = CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=encounter.event_id,
                status=EncounterStatus.CAUGHT
            )
            
            barrier.wait()  # Synchronize start
            append_apply_commit(event_store, projection_engine, catch_result, session)
        
        workers = [
            session_worker(session_factory, fe_finalized_worker),
            session_worker(session_factory, catch_result_worker)
        ]
        
        errors = run_in_threads(workers, join_timeout=10.0)
        
        # Assert: No errors (graceful constraint handling)
        assert all(error is None for error in errors), f"Errors occurred: {errors}"
        
        # Assert: Exactly one finalized route
        final_route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == route_id
        ).one()
        
        assert final_route_progress.fe_finalized, "Route should be finalized"
        
        # Assert: Blocklist entry created (from catch result)
        blocklist_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == family_id
        ).one_or_none()
        
        assert blocklist_entry is not None, "Blocklist entry should be created"
        assert blocklist_entry.origin == "caught"

    @pytest.mark.v3_only
    def test_encounter_dupe_skip_after_existing_finalization_for_multiple_players(
        self, db_session, make_run, make_player
    ):
        """Test that encounters after route finalization are dupe-skip and create no route_progress."""
        # Arrange: Create run and 3 players
        run = make_run("Dupe Skip After Finalization")
        player1 = make_player(run.id, "FirstPlayer")
        player2 = make_player(run.id, "SecondPlayer")
        player3 = make_player(run.id, "ThirdPlayer")
        
        route_id = 22
        family_id = 7  # Squirtle family
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Step 1: Player1 encounters and catches (finalizes route)
        encounter1 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=route_id,
            species_id=7,
            family_id=family_id,
            level=10,
            encounter_method=EncounterMethod.SURF,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        append_apply_commit(event_store, projection_engine, encounter1, db_session)
        
        catch1 = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter1.event_id,
            status=EncounterStatus.CAUGHT
        )
        
        append_apply_commit(event_store, projection_engine, catch1, db_session)
        
        # Verify route is finalized
        route_progress1 = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id
        ).one()
        assert route_progress1.fe_finalized
        assert route_progress1.player_id == player1.id
        
        # Step 2: Players 2 and 3 attempt encounters on the same route (should be dupe-skip)
        encounter2 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=route_id,
            species_id=8,  # Wartortle (different species, same family)
            family_id=family_id,
            level=15,
            encounter_method=EncounterMethod.SURF,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        encounter3 = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player3.id,
            timestamp=datetime.now(timezone.utc),
            route_id=route_id,
            species_id=9,  # Blastoise (different species, same family)  
            family_id=family_id,
            level=20,
            encounter_method=EncounterMethod.SURF,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        # Apply encounters (should be dupe-skip)
        append_apply_commit(event_store, projection_engine, encounter2, db_session)
        append_apply_commit(event_store, projection_engine, encounter3, db_session)
        
        # Assert: Still only one route_progress record (for player1)
        route_progress_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id
        ).count()
        
        assert route_progress_count == 1, f"Expected 1 route progress, got {route_progress_count}"
        
        # Verify it's still player1's finalized route
        final_route = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == route_id
        ).one()
        
        assert final_route.player_id == player1.id
        assert final_route.fe_finalized

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    def test_family_blocked_event_vs_catch_result_race(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Test FamilyBlockedEvent racing with CatchResultEvent for same family."""
        # Arrange
        run = make_run("Family Block vs Catch Race")
        player1 = make_player(run.id, "BlockPlayer")
        player2 = make_player(run.id, "CatchPlayer")
        
        family_id = 16  # Pidgey family
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Player2 has an encounter ready to catch
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=50,
            species_id=16,  # Pidgey
            family_id=family_id,
            level=8,
            encounter_method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER,
        )
        
        append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Prepare racing events
        barrier = barrier_factory(2)
        
        def family_blocked_worker(session):
            event_store = EventStore(session)
            projection_engine = ProjectionEngine(session)
            
            block_event = FamilyBlockedEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player1.id,
                timestamp=datetime.now(timezone.utc),
                family_id=family_id,
                origin="first_encounter",
            )
            
            barrier.wait()  # Synchronize start
            append_apply_commit(event_store, projection_engine, block_event, session)
        
        def catch_result_worker(session):
            event_store = EventStore(session)
            projection_engine = ProjectionEngine(session)
            
            catch_result = CatchResultEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player2.id,
                timestamp=datetime.now(timezone.utc),
                encounter_id=encounter.event_id,
                status=EncounterStatus.CAUGHT
            )
            
            barrier.wait()  # Synchronize start
            append_apply_commit(event_store, projection_engine, catch_result, session)
        
        workers = [
            session_worker(session_factory, family_blocked_worker),
            session_worker(session_factory, catch_result_worker)
        ]
        
        errors = run_in_threads(workers, join_timeout=10.0)
        
        # Assert: No errors (graceful handling)
        assert all(error is None for error in errors), f"Errors occurred: {errors}"
        
        # Assert: Exactly one blocklist entry (higher priority wins)
        blocklist_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == family_id
        ).one()
        
        # Caught should win over first_encounter priority
        assert blocklist_entry.origin == "caught"
        
        # Assert: Route should be finalized
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 50
        ).one()
        assert route_progress.fe_finalized

    @pytest.mark.v3_only
    @pytest.mark.concurrency
    @pytest.mark.stress
    def test_mixed_event_type_storm(
        self, db_session, session_factory, barrier_factory, make_run, make_player
    ):
        """Stress test with multiple event types racing simultaneously."""
        # Arrange
        run = make_run("Mixed Event Storm")
        players = [make_player(run.id, f"StormPlayer{i}") for i in range(6)]
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Setup: Create encounters for some players
        encounters = []
        for i in [0, 2, 4]:  # Players 0, 2, 4 have encounters
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=players[i].id,
                timestamp=datetime.now(timezone.utc),
                route_id=60 + i,
                species_id=100 + i,
                family_id=100 + i,
                level=15,
                encounter_method=EncounterMethod.GRASS,
                status=EncounterStatus.FIRST_ENCOUNTER,
            )
            encounters.append(encounter)
            append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        barrier = barrier_factory(6)
        
        def make_mixed_worker(worker_id, player):
            def worker(session):
                event_store = EventStore(session)
                projection_engine = ProjectionEngine(session)
                
                if worker_id == 0:
                    # Player 0: Catch their encounter
                    event = CatchResultEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        encounter_id=encounters[0].event_id,
                        status=EncounterStatus.CAUGHT
                    )
                elif worker_id == 1:
                    # Player 1: Block a family
                    event = FamilyBlockedEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        family_id=200,
                        origin="first_encounter",
                    )
                elif worker_id == 2:
                    # Player 2: Finalize their route
                    event = FirstEncounterFinalizedEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        route_id=62,  # Their route
                    )
                elif worker_id == 3:
                    # Player 3: New encounter
                    event = EncounterEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        route_id=70,
                        species_id=150,  # Mewtwo
                        family_id=150,
                        level=70,
                        encounter_method=EncounterMethod.STATIC,
                        status=EncounterStatus.FIRST_ENCOUNTER,
                    )
                elif worker_id == 4:
                    # Player 4: Catch their encounter
                    event = CatchResultEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        encounter_id=encounters[2].event_id,
                        status=EncounterStatus.CAUGHT
                    )
                else:  # worker_id == 5
                    # Player 5: Block another family
                    event = FamilyBlockedEvent(
                        event_id=uuid.uuid4(),
                        run_id=run.id,
                        player_id=player.id,
                        timestamp=datetime.now(timezone.utc),
                        family_id=201,
                        origin="first_encounter",
                    )
                
                barrier.wait()  # Synchronize all workers
                append_apply_commit(event_store, projection_engine, event, session)
            
            return session_worker(session_factory, worker)
        
        workers = [
            make_mixed_worker(i, players[i])
            for i in range(6)
        ]
        
        errors = run_in_threads(workers, join_timeout=20.0)
        
        # Assert: No errors (all event types handled gracefully)
        assert all(error is None for error in errors), f"Errors occurred: {errors}"
        
        # Assert: Expected number of route progress entries
        route_progress_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).count()
        # Should be: 3 initial encounters + 1 new encounter = 4 total
        assert route_progress_count == 4
        
        # Assert: Expected number of blocklist entries
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id
        ).count()
        # Should be: 2 catches + 2 explicit blocks = 4 total (families: 100, 104, 200, 201)
        assert blocklist_count == 4
        
        # Assert: Two routes should be finalized (from catches)
        finalized_count = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.fe_finalized.is_(True)
        ).count()
        assert finalized_count == 2