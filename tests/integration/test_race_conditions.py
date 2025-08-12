"""Integration tests for race condition handling with DB constraints.

Tests the projection engine's behavior under constraint races, rollbacks, and
idempotent retries. These tests validate that database constraints properly
enforce "first wins" semantics and that the projection engine handles
constraint violations gracefully without data corruption.
"""

import pytest
import uuid
from datetime import datetime, timezone

from src.soullink_tracker.store.event_store import EventStore
from src.soullink_tracker.store.projections import ProjectionEngine, ProjectionError
from src.soullink_tracker.db.models import RouteProgress, Blocklist
from src.soullink_tracker.domain.events import (
    EncounterEvent, 
    CatchResultEvent, 
    FamilyBlockedEvent, 
    FirstEncounterFinalizedEvent
)
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus


def append_apply_commit(event_store: EventStore, projection_engine: ProjectionEngine, event, db_session):
    """Helper to append event, commit, apply via engine, and commit.
    
    This ensures proper transaction boundaries for race condition testing.
    """
    envelope = event_store.append(event)
    db_session.commit()
    projection_engine.apply_event(envelope) 
    db_session.commit()
    return envelope


class TestRaceConditionHandling:
    """Test race condition handling with database constraints."""

    @pytest.mark.v3_only
    def test_route_finalization_first_wins_with_competing_catches(self, db_session, make_run, make_player):
        """Test that only one player can finalize a route via competing catch results."""
        # Arrange
        run = make_run("Route Race Run")
        player1 = make_player(run.id, "RacePlayer1")
        player2 = make_player(run.id, "RacePlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Both players encounter on same route
        p1_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=20,
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
        
        p2_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=20,  # Same route
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
        
        # Apply encounters with commit boundaries
        append_apply_commit(event_store, projection_engine, p1_encounter, db_session)
        append_apply_commit(event_store, projection_engine, p2_encounter, db_session)
        
        # Both players catch - competing for finalization
        p1_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p1_encounter.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        p2_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p2_encounter.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        # Act: Apply catches with proper transaction boundaries
        # Player1 catches first - should win finalization
        append_apply_commit(event_store, projection_engine, p1_catch, db_session)
        
        # Player2 catches second - should hit constraint and lose finalization race
        append_apply_commit(event_store, projection_engine, p2_catch, db_session)
        
        # Assert: First wins semantics
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 20
        ).all()
        
        # Find finalized entries
        finalized = [rp for rp in route_progress if rp.fe_finalized]
        unfinalized = [rp for rp in route_progress if not rp.fe_finalized]
        
        # Exactly one finalized entry (player1 wins)
        assert len(finalized) == 1
        assert finalized[0].player_id == player1.id
        
        # Player2 should have unfinalized entry (constraint prevented finalization)
        assert len(unfinalized) == 1  
        assert unfinalized[0].player_id == player2.id

    @pytest.mark.v3_only
    def test_route_finalization_loser_idempotent_retry_keeps_non_finalized(self, db_session, make_run, make_player):
        """Test that retrying the losing finalizer remains idempotent."""
        # Arrange: Set up the same race condition scenario
        run = make_run("Idempotent Retry Run")
        player1 = make_player(run.id, "Winner")
        player2 = make_player(run.id, "Loser")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Set up encounters
        p1_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=21,
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
        
        p2_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=21,  # Same route
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
        
        # Apply encounters
        append_apply_commit(event_store, projection_engine, p1_encounter, db_session)
        append_apply_commit(event_store, projection_engine, p2_encounter, db_session)
        
        # Set up catches
        p1_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p1_encounter.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        p2_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=p2_encounter.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        # Apply first catch (winner)
        append_apply_commit(event_store, projection_engine, p1_catch, db_session)
        
        # Apply second catch (loser) - and get the envelope
        p2_envelope = event_store.append(p2_catch)
        db_session.commit()
        projection_engine.apply_event(p2_envelope)
        db_session.commit()
        
        # Act: Retry the loser's catch result (idempotent test)
        projection_engine.apply_event(p2_envelope)  # Reuse same envelope
        db_session.commit()
        
        # Assert: State remains consistent
        finalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 21,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        unfinalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 21,
            RouteProgress.fe_finalized.is_(False)
        ).all()
        
        # Still exactly one finalized (player1)
        assert len(finalized) == 1
        assert finalized[0].player_id == player1.id
        
        # Player2 still unfinalized
        assert len(unfinalized) == 1
        assert unfinalized[0].player_id == player2.id

    @pytest.mark.v3_only 
    def test_blocklist_duplicate_inserts_idempotent(self, db_session, make_run, make_player):
        """Test that duplicate blocklist inserts with same priority are idempotent."""
        # Arrange
        run = make_run("Blocklist Idempotent Run")
        player = make_player(run.id, "BlocklistPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Two identical family blocked events
        blocked_event1 = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=16,  # Pidgey family
            origin="first_encounter",
        )
        
        blocked_event2 = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=16,  # Same family
            origin="first_encounter",  # Same priority
        )
        
        # Act: Apply both events with transaction boundaries
        append_apply_commit(event_store, projection_engine, blocked_event1, db_session)
        append_apply_commit(event_store, projection_engine, blocked_event2, db_session)
        
        # Assert: Only one blocklist entry exists
        blocklist_entries = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 16
        ).all()
        
        assert len(blocklist_entries) == 1
        assert blocklist_entries[0].origin == "first_encounter"

    @pytest.mark.v3_only
    def test_missing_encounter_raises_then_session_stays_usable(self, db_session, make_run, make_player):
        """Test session recoverability after ProjectionError."""
        # Arrange
        run = make_run("Session Recovery Run")
        player = make_player(run.id, "RecoveryPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Invalid catch result (no corresponding encounter)
        invalid_catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=uuid.uuid4(),  # Non-existent encounter
            result=EncounterStatus.CAUGHT,
        )
        
        invalid_envelope = event_store.append(invalid_catch)
        db_session.commit()
        
        # Act: Apply invalid event (should raise)
        with pytest.raises(ProjectionError):
            projection_engine.apply_event(invalid_envelope)
        # Don't commit after error
        
        # Session should still be usable - create valid event
        valid_encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=22,
            species_id=39,  # Jigglypuff
            family_id=39,
            level=8,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        # This should succeed (session is still usable)
        append_apply_commit(event_store, projection_engine, valid_encounter, db_session)
        
        # Assert: No corruption from invalid event, valid event processed
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id
        ).all()
        
        # Only the valid encounter should have created route progress
        assert len(route_progress) == 1
        assert route_progress[0].route_id == 22
        assert route_progress[0].player_id == player.id
        
        # No blocklist entries from invalid catch
        blocklist_count = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id
        ).count()
        assert blocklist_count == 0

    @pytest.mark.v3_only
    def test_fe_finalized_event_race_first_wins(self, db_session, make_run, make_player):
        """Test FirstEncounterFinalizedEvent race with first wins semantics."""
        # Arrange
        run = make_run("FE Race Run")
        player1 = make_player(run.id, "FEPlayer1")
        player2 = make_player(run.id, "FEPlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create encounters for both players on same route (unfinalized)
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=23,
                species_id=74 if player == player1 else 95,  # Geodude vs Onix
                family_id=74 if player == player1 else 95,
                level=12,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Competing finalization events
        fe_event1 = FirstEncounterFinalizedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=23,
        )
        
        fe_event2 = FirstEncounterFinalizedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=23,  # Same route
        )
        
        # Act: Apply finalization events with transaction boundaries  
        # Player1 finalizes first - should win
        append_apply_commit(event_store, projection_engine, fe_event1, db_session)
        
        # Player2 finalizes second - should hit constraint 
        append_apply_commit(event_store, projection_engine, fe_event2, db_session)
        
        # Assert: First wins semantics
        finalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 23,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        unfinalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 23,
            RouteProgress.fe_finalized.is_(False)
        ).all()
        
        # Exactly one finalized (player1 wins)
        assert len(finalized) == 1
        assert finalized[0].player_id == player1.id
        
        # Player2 remains unfinalized
        assert len(unfinalized) == 1
        assert unfinalized[0].player_id == player2.id

    @pytest.mark.v3_only
    def test_competing_finalizations_in_single_transaction_first_wins(self, db_session, make_run, make_player):
        """Test savepoint-based graceful handling with competing finalizations in single transaction.
        
        With savepoint-based graceful error handling, the first finalization succeeds and commits
        its savepoint, while the second finalization hits the constraint and has only its savepoint
        rolled back, leaving the first finalization intact.
        """
        # Arrange
        run = make_run("Transaction Coupling Run")
        player1 = make_player(run.id, "TxPlayer1")
        player2 = make_player(run.id, "TxPlayer2")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Create unfinalized route progress for both players
        for player in [player1, player2]:
            encounter = EncounterEvent(
                event_id=uuid.uuid4(),
                run_id=run.id,
                player_id=player.id,
                timestamp=datetime.now(timezone.utc),
                route_id=24,
                species_id=104 if player == player1 else 111,  # Cubone vs Rhyhorn
                family_id=104 if player == player1 else 111,
                level=15,
                shiny=False,
                encounter_method=EncounterMethod.GRASS,
                rod_kind=None,
                status=EncounterStatus.FIRST_ENCOUNTER,
                dupes_skip=False,
                fe_finalized=False,
            )
            append_apply_commit(event_store, projection_engine, encounter, db_session)
        
        # Prepare competing finalization events
        fe_event1 = FirstEncounterFinalizedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player1.id,
            timestamp=datetime.now(timezone.utc),
            route_id=24,
        )
        
        fe_event2 = FirstEncounterFinalizedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player2.id,
            timestamp=datetime.now(timezone.utc),
            route_id=24,
        )
        
        # Store both events
        env1 = event_store.append(fe_event1)
        env2 = event_store.append(fe_event2)
        db_session.commit()
        
        # Act: Apply both in single transaction (no commit between)
        projection_engine.apply_event(env1)  # Should succeed, but uncommitted
        projection_engine.apply_event(env2)  # Should cause rollback of both
        db_session.commit()  # Final commit after rollback
        
        # Assert: Both should be unfinalized due to transactional coupling
        finalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 24,
            RouteProgress.fe_finalized.is_(True)
        ).all()
        
        unfinalized = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.route_id == 24,
            RouteProgress.fe_finalized.is_(False)
        ).all()
        
        # With savepoint-based graceful handling, first wins and second is ignored
        assert len(finalized) == 1  # First finalization succeeded  
        assert len(unfinalized) == 1  # Second player remains unfinalized

    @pytest.mark.v3_only  
    def test_blocklist_upgrade_preserves_atomicity(self, db_session, make_run, make_player):
        """Test that blocklist upgrade conflicts don't corrupt route finalization.
        
        This test may expose architectural issues if blocklist rollback
        undoes route finalization in the same transaction.
        """
        # Arrange
        run = make_run("Atomicity Test Run")
        player = make_player(run.id, "AtomicityPlayer")
        
        event_store = EventStore(db_session)
        projection_engine = ProjectionEngine(db_session)
        
        # Pre-block family with lower priority
        pre_blocked = FamilyBlockedEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            family_id=129,  # Magikarp family
            origin="first_encounter",  # Lower priority
        )
        append_apply_commit(event_store, projection_engine, pre_blocked, db_session)
        
        # Create encounter and catch for same family (should upgrade blocklist)
        encounter = EncounterEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            route_id=25,
            species_id=129,  # Magikarp
            family_id=129,
            level=10,
            shiny=False,
            encounter_method=EncounterMethod.SURF,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )
        
        catch = CatchResultEvent(
            event_id=uuid.uuid4(),
            run_id=run.id,
            player_id=player.id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter.event_id,
            result=EncounterStatus.CAUGHT,
        )
        
        # Act: Apply encounter and catch (catch should upgrade blocklist)
        append_apply_commit(event_store, projection_engine, encounter, db_session)
        append_apply_commit(event_store, projection_engine, catch, db_session)
        
        # Assert: Both route finalization and blocklist upgrade should persist
        # Route should be finalized
        route_progress = db_session.query(RouteProgress).filter(
            RouteProgress.run_id == run.id,
            RouteProgress.player_id == player.id,
            RouteProgress.route_id == 25
        ).first()
        
        assert route_progress is not None
        assert route_progress.fe_finalized is True
        
        # Blocklist should be upgraded to "caught"
        blocklist_entry = db_session.query(Blocklist).filter(
            Blocklist.run_id == run.id,
            Blocklist.family_id == 129
        ).first()
        
        assert blocklist_entry is not None
        assert blocklist_entry.origin == "caught"  # Upgraded from "first_encounter"