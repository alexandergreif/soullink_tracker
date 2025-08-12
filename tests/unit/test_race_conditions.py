"""Unit tests for race condition handling in projections."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from src.soullink_tracker.store.projections import ProjectionEngine
from src.soullink_tracker.domain.events import EncounterEvent, FamilyBlockedEvent, EventEnvelope
from src.soullink_tracker.db.models import RouteProgress, Blocklist


@pytest.mark.unit
class TestRaceConditionHandling:
    """Test database constraint enforcement and graceful error handling."""
    
    def test_first_encounter_race_condition_resolution(self, test_db):
        """Test that simultaneous first encounter finalization is handled gracefully."""
        db = test_db()
        projection_engine = ProjectionEngine(db)
        
        # Common test data
        run_id = uuid4()
        route_id = 31
        now = datetime.now(timezone.utc)
        
        # Player 1 and Player 2 encounter on the same route
        player1_id = uuid4()
        player2_id = uuid4()
        
        # Create first encounter events for both players
        event1 = EncounterEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player1_id,
            timestamp=now,
            route_id=route_id,
            species_id=25,  # Pikachu
            family_id=25,   # Pikachu family
            level=5,
            shiny=False,
            method="grass",
            fe_finalized=True  # Both try to finalize
        )
        
        event2 = EncounterEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player2_id,
            timestamp=now,
            route_id=route_id,
            species_id=19,  # Rattata  
            family_id=19,   # Rattata family
            level=4,
            shiny=False,
            method="grass",
            fe_finalized=True  # Both try to finalize
        )
        
        # Apply first event - should succeed
        envelope1 = EventEnvelope(event1, 1, now)
        projection_engine.apply_event(envelope1)
        
        # Check that player 1 has finalized first encounter
        route_progress1 = db.execute(
            text("SELECT * FROM route_progress WHERE run_id = :run_id AND player_id = :player_id AND route_id = :route_id"),
            {"run_id": str(run_id), "player_id": str(player1_id), "route_id": route_id}
        ).fetchone()
        
        assert route_progress1 is not None
        assert route_progress1.fe_finalized is True
        
        # Apply second event - should handle race condition gracefully
        envelope2 = EventEnvelope(event2, 2, now)
        
        # This should not raise an exception but should handle the race condition
        projection_engine.apply_event(envelope2)
        
        # Check that player 2 has route progress but fe_finalized is False (lost the race)
        route_progress2 = db.execute(
            text("SELECT * FROM route_progress WHERE run_id = :run_id AND player_id = :player_id AND route_id = :route_id"),
            {"run_id": str(run_id), "player_id": str(player2_id), "route_id": route_id}
        ).fetchone()
        
        assert route_progress2 is not None
        assert route_progress2.fe_finalized is False  # Lost the race
        
        # Verify only one finalized first encounter exists for this route
        finalized_count = db.execute(
            text("SELECT COUNT(*) as count FROM route_progress WHERE run_id = :run_id AND route_id = :route_id AND fe_finalized = 1"),
            {"run_id": str(run_id), "route_id": route_id}
        ).scalar()
        
        assert finalized_count == 1
    
    def test_family_blocked_idempotency(self, test_db):
        """Test that blocking the same family multiple times is handled gracefully."""
        db = test_db()
        projection_engine = ProjectionEngine(db)
        
        run_id = uuid4()
        family_id = 25  # Pikachu family
        now = datetime.now(timezone.utc)
        
        # Create first family blocked event
        event1 = FamilyBlockedEvent(
            event_id=uuid4(),
            run_id=run_id,
            timestamp=now,
            family_id=family_id,
            origin="first_encounter"
        )
        
        # Create second family blocked event with different origin
        event2 = FamilyBlockedEvent(
            event_id=uuid4(),
            run_id=run_id,
            timestamp=now,
            family_id=family_id,
            origin="caught"  # Higher priority than first_encounter
        )
        
        # Apply first event
        envelope1 = EventEnvelope(event1, 1, now)
        projection_engine.apply_event(envelope1)
        
        # Check that blocklist entry was created
        blocklist1 = db.execute(
            text("SELECT * FROM blocklist WHERE run_id = :run_id AND family_id = :family_id"),
            {"run_id": str(run_id), "family_id": family_id}
        ).fetchone()
        
        assert blocklist1 is not None
        assert blocklist1.origin == "first_encounter"
        
        # Apply second event - should update origin to higher priority
        envelope2 = EventEnvelope(event2, 2, now)
        projection_engine.apply_event(envelope2)
        
        # Check that origin was updated to the higher priority one
        blocklist2 = db.execute(
            text("SELECT * FROM blocklist WHERE run_id = :run_id AND family_id = :family_id"),
            {"run_id": str(run_id), "family_id": family_id}
        ).fetchone()
        
        assert blocklist2 is not None
        assert blocklist2.origin == "caught"  # Updated to higher priority
        
        # Verify only one blocklist entry exists
        count = db.execute(
            text("SELECT COUNT(*) as count FROM blocklist WHERE run_id = :run_id AND family_id = :family_id"),
            {"run_id": str(run_id), "family_id": family_id}
        ).scalar()
        
        assert count == 1
    
    def test_concurrent_route_progress_updates(self, test_db):
        """Test that concurrent route progress updates don't cause issues."""
        db = test_db()
        projection_engine = ProjectionEngine(db)
        
        run_id = uuid4()
        player_id = uuid4()
        route_id = 31
        now = datetime.now(timezone.utc)
        
        # Create route progress with initial non-finalized encounter
        initial_event = EncounterEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            timestamp=now,
            route_id=route_id,
            species_id=25,
            family_id=25,
            level=5,
            shiny=False,
            method="grass",
            fe_finalized=False
        )
        
        envelope1 = EventEnvelope(initial_event, 1, now)
        projection_engine.apply_event(envelope1)
        
        # Create finalization event
        finalize_event = EncounterEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            timestamp=now,
            route_id=route_id,
            species_id=25,
            family_id=25,
            level=5,
            shiny=False,
            method="grass",
            fe_finalized=True
        )
        
        envelope2 = EventEnvelope(finalize_event, 2, now)
        projection_engine.apply_event(envelope2)
        
        # Verify finalization worked
        route_progress = db.execute(
            text("SELECT * FROM route_progress WHERE run_id = :run_id AND player_id = :player_id AND route_id = :route_id"),
            {"run_id": str(run_id), "player_id": str(player_id), "route_id": route_id}
        ).fetchone()
        
        assert route_progress is not None
        assert route_progress.fe_finalized is True


@pytest.mark.unit
class TestConstraintIntegrity:
    """Test that database constraints are properly enforced."""
    
    def test_route_progress_unique_constraint_enforcement(self, test_db):
        """Test that the unique constraint on route progress is enforced by the database."""
        db = test_db()
        
        run_id = uuid4()
        route_id = 31
        player1_id = uuid4()
        player2_id = uuid4()
        
        # Create route progress for player 1 with fe_finalized=True
        
        progress1 = RouteProgress(
            run_id=run_id,
            player_id=player1_id,
            route_id=route_id,
            fe_finalized=True
        )
        db.add(progress1)
        db.commit()
        
        # Try to create route progress for player 2 with fe_finalized=True on same route
        progress2 = RouteProgress(
            run_id=run_id,
            player_id=player2_id,
            route_id=route_id,
            fe_finalized=True
        )
        db.add(progress2)
        
        # This should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db.commit()
    
    def test_blocklist_unique_constraint_enforcement(self, test_db):
        """Test that the unique constraint on blocklist is enforced."""
        db = test_db()
        
        run_id = uuid4()
        family_id = 25
        
        # Create blocklist entry
        
        entry1 = Blocklist(
            run_id=run_id,
            family_id=family_id,
            origin="first_encounter"
        )
        db.add(entry1)
        db.commit()
        
        # Try to create another entry for same run_id and family_id
        entry2 = Blocklist(
            run_id=run_id,
            family_id=family_id,
            origin="caught"
        )
        db.add(entry2)
        
        # This should raise IntegrityError due to primary key constraint
        with pytest.raises(IntegrityError):
            db.commit()