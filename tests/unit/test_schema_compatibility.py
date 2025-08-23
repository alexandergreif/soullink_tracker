"""
Tests for V2/V3 event schema compatibility layer.

This module tests the backward compatibility features added to API schemas,
including field aliasing, enum coercion, and conditional validation.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from src.soullink_tracker.api.schemas import EventEncounter, EventCatchResult
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus, RodKind


class TestEventEncounterCompatibility:
    """Test encounter event V2/V3 compatibility."""

    def test_v3_format_standard_encounter(self):
        """Test V3 format with canonical field names."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.GRASS
        assert encounter.type == "encounter"
        assert encounter.shiny is False

    def test_v2_format_encounter_method_field(self):
        """Test V2 legacy format with encounter_method field."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 40,
            "species_id": 54,
            "level": 20,
            "shiny": False,
            "encounter_method": "surf"  # V2 field name
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.SURF
        assert encounter.route_id == 40
        assert encounter.species_id == 54

    def test_enum_string_coercion(self):
        """Test that string values are coerced to enums."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 32,
            "species_id": 129,
            "level": 10,
            "shiny": False,
            "method": "FISH",  # Uppercase string
            "rod_kind": "OLD"  # Uppercase string
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.FISH
        assert encounter.rod_kind == RodKind.OLD

    def test_fishing_encounter_validation(self):
        """Test that fishing encounters require rod_kind."""
        # Valid fishing encounter
        valid_fishing = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 32,
            "species_id": 129,
            "level": 10,
            "shiny": False,
            "method": "fish",
            "rod_kind": "good"
        }
        
        encounter = EventEncounter(**valid_fishing)
        assert encounter.method == EncounterMethod.FISH
        assert encounter.rod_kind == RodKind.GOOD

        # Invalid: fishing without rod_kind
        invalid_fishing = valid_fishing.copy()
        del invalid_fishing["rod_kind"]
        
        with pytest.raises(ValidationError) as exc_info:
            EventEncounter(**invalid_fishing)
        
        assert "rod_kind" in str(exc_info.value)

    def test_non_fishing_encounter_no_rod_kind(self):
        """Test that non-fishing encounters don't require rod_kind."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 1,
            "species_id": 144,
            "level": 50,
            "shiny": True,
            "method": "static"
            # No rod_kind - should be valid
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.STATIC
        assert encounter.rod_kind is None
        assert encounter.shiny is True

    def test_invalid_method_enum_value(self):
        """Test validation fails for invalid method values."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "invalid_method"
        }
        
        with pytest.raises(ValidationError):
            EventEncounter(**event_data)

    def test_missing_method_field(self):
        """Test validation fails when method field is missing."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False
            # Missing method field
        }
        
        with pytest.raises(ValidationError):
            EventEncounter(**event_data)


class TestEventCatchResultCompatibility:
    """Test catch result event V2/V3 compatibility."""

    def test_v3_format_with_encounter_id(self):
        """Test V3 format with encounter_id."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_id": str(uuid4()),
            "result": "caught"
        }
        
        catch_result = EventCatchResult(**event_data)
        assert catch_result.result == EncounterStatus.CAUGHT
        assert catch_result.encounter_id is not None

    def test_v2_format_with_encounter_ref(self):
        """Test V2 legacy format with encounter_ref."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_ref": {
                "route_id": 32,
                "species_id": 129
            },
            "status": "fled"  # V2 field name
        }
        
        catch_result = EventCatchResult(**event_data)
        assert catch_result.status == EncounterStatus.FLED
        assert catch_result.encounter_ref is not None
        assert catch_result.encounter_ref["route_id"] == 32
        assert catch_result.encounter_ref["species_id"] == 129

    def test_status_result_field_synchronization(self):
        """Test that status and result fields are synchronized."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_ref": {"route_id": 1, "species_id": 1},
            "status": "caught"
        }
        
        catch_result = EventCatchResult(**event_data)
        # Both fields should be populated
        assert catch_result.status == EncounterStatus.CAUGHT
        assert catch_result.result == EncounterStatus.CAUGHT

    def test_enum_string_coercion_status(self):
        """Test that string status values are coerced to enums."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_id": str(uuid4()),
            "result": "KO"  # Uppercase string
        }
        
        catch_result = EventCatchResult(**event_data)
        assert catch_result.result == EncounterStatus.KO

    def test_missing_encounter_reference_validation(self):
        """Test validation fails without encounter reference."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "result": "caught"
            # Missing both encounter_id and encounter_ref
        }
        
        with pytest.raises(ValidationError) as exc_info:
            EventCatchResult(**event_data)
        
        assert "encounter_id or encounter_ref" in str(exc_info.value)

    def test_missing_status_result_validation(self):
        """Test validation fails without status/result field."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_id": str(uuid4())
            # Missing both result and status
        }
        
        with pytest.raises(ValidationError) as exc_info:
            EventCatchResult(**event_data)
        
        assert "result or status" in str(exc_info.value)

    def test_invalid_status_enum_value(self):
        """Test validation fails for invalid status values."""
        event_data = {
            "type": "catch_result",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "encounter_id": str(uuid4()),
            "result": "invalid_status"
        }
        
        with pytest.raises(ValidationError):
            EventCatchResult(**event_data)


class TestMixedFormatCompatibility:
    """Test edge cases and mixed format scenarios."""

    def test_both_v2_and_v3_fields_provided(self):
        """Test behavior when both V2 and V3 fields are provided."""
        # For encounter: both method and encounter_method
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass",  # V3
            "encounter_method": "surf"  # V2 - should be ignored
        }
        
        encounter = EventEncounter(**event_data)
        # V3 field (method) should take precedence
        assert encounter.method == EncounterMethod.GRASS

    def test_case_insensitive_enum_coercion(self):
        """Test that enum coercion is case-insensitive."""
        test_cases = [
            ("grass", EncounterMethod.GRASS),
            ("GRASS", EncounterMethod.GRASS),
            ("Grass", EncounterMethod.GRASS),
            ("sUrF", EncounterMethod.SURF)
        ]
        
        for method_value, expected_enum in test_cases:
            event_data = {
                "type": "encounter",
                "run_id": str(uuid4()),
                "player_id": str(uuid4()),
                "time": datetime.now(timezone.utc),
                "route_id": 29,
                "species_id": 1,
                "level": 5,
                "shiny": False,
                "method": method_value
            }
            
            encounter = EventEncounter(**event_data)
            assert encounter.method == expected_enum

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "  grass  "  # Whitespace around value
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.GRASS

    def test_comprehensive_v2_fishing_event(self):
        """Test complete V2 fishing event with all transformations."""
        event_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc),
            "route_id": 32,
            "species_id": 129,
            "level": 10,
            "shiny": False,
            "encounter_method": " FISH ",  # V2 field with whitespace
            "rod_kind": "SUPER"  # Uppercase
        }
        
        encounter = EventEncounter(**event_data)
        assert encounter.method == EncounterMethod.FISH
        assert encounter.rod_kind == RodKind.SUPER
        assert encounter.route_id == 32
        assert encounter.level == 10