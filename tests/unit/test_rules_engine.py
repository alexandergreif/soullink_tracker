"""Unit tests for the SoulLink rules engine."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from soullink_tracker.core.rules_engine import RulesEngine
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus, RodKind
from soullink_tracker.db.models import Run, Player, Encounter, Blocklist


@pytest.mark.unit
class TestRulesEngine:
    """Test the rules engine for SoulLink logic."""

    def setup_method(self):
        """Set up test data."""
        self.run_id = uuid4()
        self.player1_id = uuid4()
        self.player2_id = uuid4()
        self.player3_id = uuid4()
        
        self.rules_engine = RulesEngine()

    def test_rules_engine_creation(self):
        """Test creating a rules engine."""
        assert self.rules_engine is not None

    def test_is_family_blocked_empty_blocklist(self):
        """Test family blocking check with empty blocklist."""
        blocklist = []
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is False

    def test_is_family_blocked_with_blocked_family(self):
        """Test family blocking check with blocked family."""
        blocklist = [
            Blocklist(
                run_id=self.run_id,
                family_id=1,
                origin="caught",
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is True

    def test_is_family_blocked_different_family(self):
        """Test family blocking check with different family."""
        blocklist = [
            Blocklist(
                run_id=self.run_id,
                family_id=2,
                origin="caught",
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is False

    def test_should_skip_dupe_encounter_no_previous_encounters(self):
        """Test dupe skip logic with no previous encounters."""
        previous_encounters = []
        
        result = self.rules_engine.should_skip_dupe_encounter(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            previous_encounters=previous_encounters
        )
        
        assert result is False

    def test_should_skip_dupe_encounter_same_family_same_route(self):
        """Test dupe skip logic with same family on same route."""
        previous_encounters = [
            Encounter(
                id=uuid4(),
                run_id=self.run_id,
                player_id=self.player2_id,  # Different player
                route_id=31,  # Same route
                species_id=1,
                family_id=1,  # Same family
                level=5,
                method=EncounterMethod.GRASS,
                time=datetime.now(timezone.utc),
                status=EncounterStatus.FIRST_ENCOUNTER,
                fe_finalized=True
            )
        ]
        
        result = self.rules_engine.should_skip_dupe_encounter(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            previous_encounters=previous_encounters
        )
        
        assert result is True

    def test_should_skip_dupe_encounter_different_route(self):
        """Test dupe skip logic with same family on different route."""
        previous_encounters = [
            Encounter(
                id=uuid4(),
                run_id=self.run_id,
                player_id=self.player2_id,
                route_id=32,  # Different route
                species_id=1,
                family_id=1,  # Same family
                level=5,
                method=EncounterMethod.GRASS,
                time=datetime.now(timezone.utc),
                status=EncounterStatus.FIRST_ENCOUNTER,
                fe_finalized=True
            )
        ]
        
        result = self.rules_engine.should_skip_dupe_encounter(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            previous_encounters=previous_encounters
        )
        
        assert result is False

    def test_determine_encounter_status_first_encounter(self):
        """Test encounter status determination for first encounter."""
        blocklist = []
        previous_encounters = []
        
        status = self.rules_engine.determine_encounter_status(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            blocklist=blocklist,
            previous_encounters=previous_encounters
        )
        
        assert status == EncounterStatus.FIRST_ENCOUNTER

    def test_determine_encounter_status_dupe_skip(self):
        """Test encounter status determination for dupe skip."""
        blocklist = []
        previous_encounters = [
            Encounter(
                id=uuid4(),
                run_id=self.run_id,
                player_id=self.player2_id,
                route_id=31,  # Same route, different player
                species_id=1,
                family_id=1,  # Same family
                level=5,
                method=EncounterMethod.GRASS,
                time=datetime.now(timezone.utc),
                status=EncounterStatus.FIRST_ENCOUNTER,
                fe_finalized=True
            )
        ]
        
        status = self.rules_engine.determine_encounter_status(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            blocklist=blocklist,
            previous_encounters=previous_encounters
        )
        
        assert status == EncounterStatus.DUPE_SKIP

    def test_determine_encounter_status_blocked_family(self):
        """Test encounter status determination for blocked family."""
        blocklist = [
            Blocklist(
                run_id=self.run_id,
                family_id=1,
                origin="caught",
                created_at=datetime.now(timezone.utc)
            )
        ]
        previous_encounters = []
        
        status = self.rules_engine.determine_encounter_status(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            blocklist=blocklist,
            previous_encounters=previous_encounters
        )
        
        assert status == EncounterStatus.DUPE_SKIP

    def test_can_finalize_first_encounter_true(self):
        """Test first encounter finalization when allowed."""
        blocklist = []
        
        result = self.rules_engine.can_finalize_first_encounter(
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is True

    def test_can_finalize_first_encounter_false_blocked(self):
        """Test first encounter finalization when family is blocked."""
        blocklist = [
            Blocklist(
                run_id=self.run_id,
                family_id=1,
                origin="caught",
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        result = self.rules_engine.can_finalize_first_encounter(
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is False

    def test_create_soul_link_members(self):
        """Test creating soul link members."""
        encounters = [
            Encounter(
                id=uuid4(),
                run_id=self.run_id,
                player_id=self.player1_id,
                route_id=31,
                species_id=1,
                family_id=1,
                level=5,
                method=EncounterMethod.GRASS,
                time=datetime.now(timezone.utc),
                status=EncounterStatus.CAUGHT
            ),
            Encounter(
                id=uuid4(),  
                run_id=self.run_id,
                player_id=self.player2_id,
                route_id=31,  # Same route
                species_id=4,
                family_id=4,
                level=6,
                method=EncounterMethod.SURF,
                time=datetime.now(timezone.utc),
                status=EncounterStatus.CAUGHT
            )
        ]
        
        link_members = self.rules_engine.create_soul_link_members(
            link_id=uuid4(),
            encounters=encounters
        )
        
        assert len(link_members) == 2
        assert link_members[0].player_id == self.player1_id
        assert link_members[1].player_id == self.player2_id
        assert link_members[0].encounter_id == encounters[0].id
        assert link_members[1].encounter_id == encounters[1].id