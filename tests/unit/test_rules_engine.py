"""Unit tests for the SoulLink rules engine.

Tests both the pure function rules engine and the legacy compatibility layer.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch

from soullink_tracker.core.rules_engine import RulesEngine
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from soullink_tracker.db.models import Encounter, Blocklist, RouteProgress
from soullink_tracker.domain.rules import (
    RunState, PlayerRouteState, evaluate_encounter, apply_catch_result
)
from soullink_tracker.domain.events import EncounterEvent, CatchResultEvent


@pytest.mark.unit
class TestPureRulesEngine:
    """Test the pure function rules engine."""

    def setup_method(self):
        """Set up test data."""
        self.run_id = uuid4()
        self.player1_id = uuid4()
        self.player2_id = uuid4()
        self.player3_id = uuid4()
    
    def test_evaluate_encounter_first_encounter(self):
        """Test evaluate_encounter for a first encounter."""
        state = RunState(blocked_families=set(), player_routes={})
        
        event = EncounterEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player1_id,
            timestamp=datetime.now(timezone.utc),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        decision = evaluate_encounter(state, event)
        
        assert decision.status == EncounterStatus.FIRST_ENCOUNTER
        assert decision.fe_finalized is False
        assert decision.dupes_skip is False
        assert decision.should_create_route_progress is True
    
    def test_evaluate_encounter_blocked_family(self):
        """Test evaluate_encounter for a blocked family."""
        state = RunState(blocked_families={1}, player_routes={})
        
        event = EncounterEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player1_id,
            timestamp=datetime.now(timezone.utc),
            route_id=31,
            species_id=1,
            family_id=1,  # This family is blocked
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        decision = evaluate_encounter(state, event)
        
        assert decision.status == EncounterStatus.DUPE_SKIP
        assert decision.dupes_skip is True
        assert decision.should_create_route_progress is False
    
    def test_apply_catch_result_caught(self):
        """Test apply_catch_result for a caught Pokemon."""
        state = RunState(blocked_families=set(), player_routes={})
        encounter_id = uuid4()
        
        catch_event = CatchResultEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player1_id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter_id,
            result=EncounterStatus.CAUGHT
        )
        
        # Mock encounter lookup
        def mock_lookup(enc_id):
            if enc_id == encounter_id:
                return self.player1_id, 31, 1  # player_id, route_id, family_id
            raise ValueError("Not found")
        
        decision = apply_catch_result(state, catch_event, mock_lookup)
        
        assert decision.fe_finalized is True
        assert decision.blocklist_add == (1, "caught")
    
    def test_apply_catch_result_fled(self):
        """Test apply_catch_result for a Pokemon that fled."""
        state = RunState(blocked_families=set(), player_routes={})
        encounter_id = uuid4()
        
        catch_event = CatchResultEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player1_id,
            timestamp=datetime.now(timezone.utc),
            encounter_id=encounter_id,
            result=EncounterStatus.FLED
        )
        
        # Mock encounter lookup
        def mock_lookup(enc_id):
            if enc_id == encounter_id:
                return self.player1_id, 31, 1  # player_id, route_id, family_id
            raise ValueError("Not found")
        
        decision = apply_catch_result(state, catch_event, mock_lookup)
        
        assert decision.fe_finalized is True
        assert decision.blocklist_add is None  # No family blocking on flee
    
    def test_run_state_with_blocked_family(self):
        """Test RunState immutable operations."""
        state = RunState(blocked_families={1, 2}, player_routes={})
        
        new_state = state.with_blocked_family(3)
        
        # Original state unchanged
        assert state.blocked_families == {1, 2}
        
        # New state has additional blocked family
        assert new_state.blocked_families == {1, 2, 3}
    
    def test_run_state_get_route_state(self):
        """Test getting route state from RunState."""
        route_state = PlayerRouteState(fe_finalized=True, first_encounter_family_id=1)
        state = RunState(
            blocked_families=set(),
            player_routes={(self.player1_id, 31): route_state}
        )
        
        # Get existing route state
        result = state.get_route_state(self.player1_id, 31)
        assert result.fe_finalized is True
        assert result.first_encounter_family_id == 1
        
        # Get non-existent route state (returns default)
        result = state.get_route_state(self.player2_id, 32)
        assert result.fe_finalized is False
        assert result.first_encounter_family_id is None


@pytest.mark.unit
class TestLegacyRulesEngine:
    """Test the legacy RulesEngine compatibility layer."""

    def setup_method(self):
        """Set up test data with mocked database session."""
        self.run_id = uuid4()
        self.player1_id = uuid4()
        self.player2_id = uuid4()
        self.player3_id = uuid4()
        
        # Create mock database session
        self.mock_db = Mock()
        self.rules_engine = RulesEngine(self.mock_db)
    
    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_rules_engine_creation(self, mock_get_config):
        """Test creating a rules engine with database session."""
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = True  # v3-only architecture
        mock_get_config.return_value = mock_config
        
        assert self.rules_engine is not None
        assert self.rules_engine.db == self.mock_db

    def test_rules_engine_creation(self):
        """Test creating a rules engine."""
        assert self.rules_engine is not None

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_is_family_blocked_empty_blocklist(self, mock_get_config):
        """Test family blocking check with empty blocklist using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries for empty blocklist and route progress
        mock_execute = Mock()
        mock_execute.scalars().all.return_value = []
        self.mock_db.execute.return_value = mock_execute
        
        blocklist = []
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is False

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_is_family_blocked_with_blocked_family(self, mock_get_config):
        """Test family blocking check with blocked family using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries with blocked family
        blocked_family = Blocklist(
            run_id=self.run_id,
            family_id=1,
            origin="caught",
            created_at=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = [blocked_family]
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = []
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
        blocklist = [blocked_family]
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is True

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_is_family_blocked_different_family(self, mock_get_config):
        """Test family blocking check with different family using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries with different blocked family
        blocked_family = Blocklist(
            run_id=self.run_id,
            family_id=2,  # Different family
            origin="caught",
            created_at=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = [blocked_family]
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = []
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
        blocklist = [blocked_family]
        
        result = self.rules_engine.is_family_blocked(
            run_id=self.run_id,
            family_id=1,  # Checking for family 1
            blocklist=blocklist
        )
        
        assert result is False

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_should_skip_dupe_encounter_no_previous_encounters(self, mock_get_config):
        """Test dupe skip logic with no previous encounters using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries for empty state
        mock_execute = Mock()
        mock_execute.scalars().all.return_value = []
        self.mock_db.execute.return_value = mock_execute
        
        previous_encounters = []
        
        result = self.rules_engine.should_skip_dupe_encounter(
            run_id=self.run_id,
            route_id=31,
            family_id=1,
            player_id=self.player1_id,
            previous_encounters=previous_encounters
        )
        
        assert result is False

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_should_skip_dupe_encounter_same_family_same_route(self, mock_get_config):
        """Test dupe skip logic with same family on same route using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries - player2 has finalized encounter on route 31
        route_progress = RouteProgress(
            run_id=self.run_id,
            player_id=self.player2_id,
            route_id=31,
            fe_finalized=True,
            last_update=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = []  # No blocked families
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = [route_progress]
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
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

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_should_skip_dupe_encounter_different_route(self, mock_get_config):
        """Test dupe skip logic with same family on different route using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries - player2 has finalized encounter on different route (32)
        mock_config.app.feature_v3_eventstore = True  # v3-only architecture
            run_id=self.run_id,
            player_id=self.player2_id,
            route_id=32,  # Different route
            fe_finalized=True,
            last_update=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = []  # No blocked families
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = [route_progress]
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
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
            route_id=31,  # Looking for route 31
            family_id=1,
            player_id=self.player1_id,
            previous_encounters=previous_encounters
        )
        
        assert result is False

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_determine_encounter_status_first_encounter(self, mock_get_config):
        """Test encounter status determination for first encounter using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries for clean state
        mock_execute = Mock()
        mock_execute.scalars().all.return_value = []
        self.mock_db.execute.return_value = mock_execute
        
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

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_determine_encounter_status_dupe_skip(self, mock_get_config):
        """Test encounter status determination for dupe skip using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries for route collision
        route_progress = RouteProgress(
            run_id=self.run_id,
            player_id=self.player2_id,
            route_id=31,
            fe_finalized=True,
            last_update=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = []  # No blocked families
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = [route_progress]
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
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

    @patch('soullink_tracker.core.rules_engine.get_config')
    def test_determine_encounter_status_blocked_family(self, mock_get_config):
        """Test encounter status determination for blocked family using legacy compatibility."""
        # Mock config to use legacy DB
        mock_config = Mock()
        mock_config.app.feature_v3_eventstore = False
        mock_get_config.return_value = mock_config
        
        # Mock database queries with blocked family
        blocked_family = Blocklist(
            run_id=self.run_id,
            family_id=1,
            origin="caught",
            created_at=datetime.now(timezone.utc)
        )
        
        mock_blocklist_execute = Mock()
        mock_blocklist_execute.scalars().all.return_value = [blocked_family]
        
        mock_route_execute = Mock()
        mock_route_execute.scalars().all.return_value = []
        
        self.mock_db.execute.side_effect = [mock_blocklist_execute, mock_route_execute]
        
        blocklist = [blocked_family]
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
        """Test first encounter finalization when allowed using legacy compatibility."""
        blocklist = []
        
        result = self.rules_engine.can_finalize_first_encounter(
            family_id=1,
            blocklist=blocklist
        )
        
        assert result is True

    def test_can_finalize_first_encounter_false_blocked(self):
        """Test first encounter finalization when family is blocked using legacy compatibility."""
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
        mock_config.app.feature_v3_eventstore = True  # v3-only architecture
        assert result is False

    def test_create_soul_link_members(self):
        """Test creating soul link members using legacy compatibility (no changes needed)."""
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
    
    def test_cache_functionality(self):
        """Test caching and cache invalidation."""
        # Test cache clearing
        self.rules_engine._state_cache[self.run_id] = RunState(blocked_families={1}, player_routes={})
        assert len(self.rules_engine._state_cache) == 1
        
        self.rules_engine.clear_cache()
        assert len(self.rules_engine._state_cache) == 0
        
        # Test single run cache invalidation
        self.rules_engine._state_cache[self.run_id] = RunState(blocked_families={1}, player_routes={})
        self.rules_engine._state_cache[uuid4()] = RunState(blocked_families={2}, player_routes={})
        assert len(self.rules_engine._state_cache) == 2
        
        self.rules_engine._invalidate_cache(self.run_id)
        assert len(self.rules_engine._state_cache) == 1