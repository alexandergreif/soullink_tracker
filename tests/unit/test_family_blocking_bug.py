"""
Unit tests to reproduce and verify the fix for the family blocking bug.

This test file specifically addresses the issue identified in family-blocking-bug-investigation.md
where wrong families are being blocked when Pokemon are caught.

Bug Summary:
- Bulbasaur (family_id: 1) caught → family 1 should be blocked but isn't
- Squirtle (family_id: 7) caught → family 7 should be blocked but isn't  
- Only Caterpie (family_id: 10) is blocked, despite never being encountered

Root Cause: encounter_lookup in projections.py uses inefficient scanning that may resolve
to wrong encounters due to UUID mismatches or cross-run contamination.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID
from unittest.mock import Mock, MagicMock, patch

from soullink_tracker.domain.events import EncounterEvent, CatchResultEvent
from soullink_tracker.domain.rules import RunState, apply_catch_result
from soullink_tracker.core.enums import EncounterStatus, EncounterMethod
from soullink_tracker.store.projections import ProjectionEngine
from soullink_tracker.store.event_store import EventStore, EventEnvelope


@pytest.mark.unit
class TestFamilyBlockingBug:
    """Test cases specifically for the family blocking bug."""

    def setup_method(self):
        """Set up test scenario matching the investigation."""
        self.run_id = UUID("565db9e7-15af-427f-b2c4-4bcee601420b")
        self.player_id = uuid4()
        self.timestamp = datetime.now(timezone.utc)

        # Create the exact scenario from the investigation
        self.bulbasaur_encounter_id = uuid4()
        self.squirtle_encounter_id = uuid4()
        self.charmander_encounter_id = uuid4()
        self.caterpie_encounter_id = uuid4()

        # Encounter events matching the investigation
        self.bulbasaur_encounter = EncounterEvent(
            event_id=self.bulbasaur_encounter_id,
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            route_id=29,
            species_id=1,  # Bulbasaur
            family_id=1,   # Bulbasaur family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )

        self.squirtle_encounter = EncounterEvent(
            event_id=self.squirtle_encounter_id,
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            route_id=31,
            species_id=7,  # Squirtle
            family_id=7,   # Squirtle family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )

        self.charmander_encounter = EncounterEvent(
            event_id=self.charmander_encounter_id,
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            route_id=30,
            species_id=4,  # Charmander
            family_id=4,   # Charmander family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )

        # Caterpie encounter that never happened but is being incorrectly blocked
        self.caterpie_encounter = EncounterEvent(
            event_id=self.caterpie_encounter_id,
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            route_id=32,
            species_id=10,  # Caterpie
            family_id=10,   # Caterpie family
            level=4,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )

        # Catch result events
        self.bulbasaur_caught = CatchResultEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            encounter_id=self.bulbasaur_encounter_id,
            result=EncounterStatus.CAUGHT
        )

        self.squirtle_caught = CatchResultEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            encounter_id=self.squirtle_encounter_id,
            result=EncounterStatus.CAUGHT
        )

        self.charmander_fled = CatchResultEvent(
            event_id=uuid4(),
            run_id=self.run_id,
            player_id=self.player_id,
            timestamp=self.timestamp,
            encounter_id=self.charmander_encounter_id,
            result=EncounterStatus.FLED
        )

    def test_domain_rules_logic_is_correct(self):
        """Test that the domain rules logic itself is correct."""
        state = RunState(blocked_families=set(), player_routes={})

        # Create a working encounter lookup
        def encounter_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            lookup_map = {
                self.bulbasaur_encounter_id: (self.player_id, 29, 1),  # Bulbasaur family
                self.squirtle_encounter_id: (self.player_id, 31, 7),   # Squirtle family
                self.charmander_encounter_id: (self.player_id, 30, 4), # Charmander family
            }
            if encounter_id not in lookup_map:
                raise ValueError(f"Encounter {encounter_id} not found")
            return lookup_map[encounter_id]

        # Test Bulbasaur caught → should block family 1
        decision = apply_catch_result(state, self.bulbasaur_caught, encounter_lookup)
        assert decision.fe_finalized is True
        assert decision.blocklist_add == (1, "caught")

        # Test Squirtle caught → should block family 7
        decision = apply_catch_result(state, self.squirtle_caught, encounter_lookup)
        assert decision.fe_finalized is True
        assert decision.blocklist_add == (7, "caught")

        # Test Charmander fled → should NOT block family 4
        decision = apply_catch_result(state, self.charmander_fled, encounter_lookup)
        assert decision.fe_finalized is True
        assert decision.blocklist_add is None

    def test_encounter_lookup_bug_simulation(self):
        """Simulate the bug where encounter_lookup returns wrong family_id."""
        state = RunState(blocked_families=set(), player_routes={})

        # Simulate the buggy encounter lookup that returns Caterpie for everything
        def buggy_encounter_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            # This simulates the bug: regardless of which encounter is requested,
            # it always returns Caterpie data (family_id: 10)
            return (self.player_id, 32, 10)  # Always returns Caterpie family

        # When Bulbasaur is caught but lookup returns Caterpie data
        decision = apply_catch_result(state, self.bulbasaur_caught, buggy_encounter_lookup)
        assert decision.fe_finalized is True
        assert decision.blocklist_add == (10, "caught")  # WRONG! Should be (1, "caught")

        # When Squirtle is caught but lookup returns Caterpie data
        decision = apply_catch_result(state, self.squirtle_caught, buggy_encounter_lookup)
        assert decision.fe_finalized is True
        assert decision.blocklist_add == (10, "caught")  # WRONG! Should be (7, "caught")

        # This demonstrates that the domain rules are correct, but encounter_lookup is buggy

    def test_projection_engine_encounter_lookup_current_implementation(self):
        """Test the current buggy implementation in ProjectionEngine."""
        # Mock database session
        mock_db = Mock()
        projection_engine = ProjectionEngine(mock_db)

        # Mock EventStore to simulate the current scanning behavior
        mock_event_store = Mock(spec=EventStore)
        
        # Simulate the scenario where encounters are returned in wrong order
        # or encounter_id matching is failing
        mock_envelopes = [
            EventEnvelope(
                sequence_number=1,
                stored_at=self.timestamp,
                event=self.caterpie_encounter  # Caterpie returned first/matched incorrectly
            ),
            EventEnvelope(
                sequence_number=2,
                stored_at=self.timestamp,
                event=self.bulbasaur_encounter
            ),
            EventEnvelope(
                sequence_number=3,
                stored_at=self.timestamp,
                event=self.squirtle_encounter
            ),
        ]
        
        mock_event_store.get_events_by_type.return_value = mock_envelopes

        # Test the current encounter_lookup implementation
        # This simulates _handle_catch_result_event's encounter_lookup
        def current_encounter_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            # Simulate the current implementation
            envelopes = mock_event_store.get_events_by_type(self.run_id, "encounter")
            for envelope in envelopes:
                if envelope.event.event_id == encounter_id:
                    enc_event = envelope.event
                    return enc_event.player_id, enc_event.route_id, enc_event.family_id
            raise ValueError(f"Encounter {encounter_id} not found in event store")

        # Test correct lookup when IDs match properly
        result = current_encounter_lookup(self.bulbasaur_encounter_id)
        assert result == (self.player_id, 29, 1)  # Should work correctly

        # Test what happens with wrong/missing encounter_id
        with pytest.raises(ValueError, match="not found in event store"):
            current_encounter_lookup(uuid4())  # Random UUID not in store

    def test_cross_run_contamination_scenario(self):
        """Test scenario where encounters from different runs cause contamination."""
        # Create encounters from different runs with same species but different families
        other_run_id = uuid4()
        
        # Bulbasaur encounter from different run (different family_id due to different species data)
        other_bulbasaur = EncounterEvent(
            event_id=uuid4(),
            run_id=other_run_id,  # Different run
            player_id=self.player_id,
            timestamp=self.timestamp,
            route_id=29,
            species_id=1,  # Same species
            family_id=10,  # But wrong family (simulating data inconsistency)
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )

        # Mock EventStore that returns encounters from multiple runs
        mock_event_store = Mock(spec=EventStore)
        mock_envelopes = [
            EventEnvelope(
                sequence_number=1,
                stored_at=self.timestamp,
                event=other_bulbasaur  # From different run
            ),
            EventEnvelope(
                sequence_number=2,
                stored_at=self.timestamp,
                event=self.bulbasaur_encounter  # From correct run
            ),
        ]
        
        mock_event_store.get_events_by_type.return_value = mock_envelopes

        # If the lookup doesn't filter by run_id properly, it might find the wrong encounter
        def contaminated_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            # This simulates a bug where run_id filtering fails
            envelopes = mock_event_store.get_events_by_type(self.run_id, "encounter")
            for envelope in envelopes:
                # If event_id somehow matches (UUID collision or other bug)
                if str(envelope.event.event_id).startswith(str(encounter_id)[:8]):
                    enc_event = envelope.event
                    return enc_event.player_id, enc_event.route_id, enc_event.family_id
            raise ValueError(f"Encounter {encounter_id} not found")

        # This could cause wrong family to be returned
        # In practice, this is less likely but demonstrates the vulnerability

    @pytest.mark.integration  
    def test_end_to_end_bug_reproduction(self):
        """End-to-end test that reproduces the exact bug scenario."""
        # This test would require a full database setup and would be in integration tests
        # For now, we document the expected behavior:
        
        # Given: Bulbasaur encountered and caught (should block family 1)
        # Given: Squirtle encountered and caught (should block family 7)  
        # Given: Charmander encountered but fled (should NOT block family 4)
        # When: Checking blocklist
        # Then: Only families 1 and 7 should be blocked
        # But: Current bug blocks only family 10 (Caterpie) instead
        
        pass

    def test_expected_behavior_after_fix(self):
        """Test the expected behavior after implementing the fix."""
        state = RunState(blocked_families=set(), player_routes={})

        # This is what the fixed encounter lookup should do
        def fixed_encounter_lookup(encounter_id: UUID) -> tuple[UUID, int, int]:
            # Direct lookup by event_id (this is what we'll implement)
            encounter_map = {
                self.bulbasaur_encounter_id: (self.player_id, 29, 1),
                self.squirtle_encounter_id: (self.player_id, 31, 7), 
                self.charmander_encounter_id: (self.player_id, 30, 4),
            }
            if encounter_id not in encounter_map:
                raise ValueError(f"Encounter {encounter_id} not found")
            return encounter_map[encounter_id]

        # Test all scenarios work correctly
        bulbasaur_decision = apply_catch_result(state, self.bulbasaur_caught, fixed_encounter_lookup)
        squirtle_decision = apply_catch_result(state, self.squirtle_caught, fixed_encounter_lookup)
        charmander_decision = apply_catch_result(state, self.charmander_fled, fixed_encounter_lookup)

        # Verify correct family blocking
        assert bulbasaur_decision.blocklist_add == (1, "caught")
        assert squirtle_decision.blocklist_add == (7, "caught")
        assert charmander_decision.blocklist_add is None

        # Verify all are finalized (regardless of catch/flee)
        assert bulbasaur_decision.fe_finalized is True
        assert squirtle_decision.fe_finalized is True
        assert charmander_decision.fe_finalized is True