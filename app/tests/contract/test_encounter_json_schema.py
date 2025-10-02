"""
Contract Test: Encounter JSON Schema Validation

Tests JSON files exported by Lua script against the contract schema.
These tests MUST FAIL initially (TDD red phase) until Lua script is implemented.

Test Strategy:
- Load encounter_json_schema.json
- Validate sample JSON data against schema
- Test valid cases (wild Pokemon, legendary)
- Test invalid cases (out of range, missing fields, constraint violations)

Expected: All tests FAIL (no JSON files or validation exists yet)
"""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError, Draft7Validator


@pytest.fixture
def schema():
    """Load the encounter JSON schema from contracts directory."""
    # Navigate from app/tests/contract/ up to repo root, then to specs
    schema_path = Path(__file__).parent.parent.parent.parent / "specs" / "001-anything-we-still" / "contracts" / "encounter_json_schema.json"

    with open(schema_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def validator(schema):
    """Create a Draft7Validator instance."""
    return Draft7Validator(schema)


class TestValidEncounters:
    """Test cases for valid encounter JSON data."""

    def test_valid_wild_encounter(self, validator):
        """Valid wild Pokemon encounter should pass validation."""
        valid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "species_name": "Pikachu",
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "location_id": None,
            "location_name": "Unknown",
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        # Should not raise ValidationError
        validator.validate(valid_encounter)

    def test_valid_legendary_encounter(self, validator):
        """Valid legendary Pokemon encounter should pass validation."""
        valid_legendary = {
            "timestamp": "2025-10-01T15:45:10Z",
            "player_name": "Bob",
            "species_id": 249,
            "species_name": "Lugia",
            "level": 45,
            "current_hp": 200,
            "max_hp": 200,
            "location_id": 142,
            "location_name": "Whirl Islands",
            "encounter_type": "legendary",
            "status": "encountered",
            "personality_value": 2847561293
        }

        validator.validate(valid_legendary)

    def test_valid_encounter_with_null_optional_fields(self, validator):
        """Encounter with null optional fields should be valid."""
        minimal_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Charlie",
            "species_id": 1,
            "species_name": None,
            "level": 5,
            "current_hp": 20,
            "max_hp": 20,
            "location_id": None,
            "location_name": None,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 123456789
        }

        validator.validate(minimal_encounter)

    def test_valid_encounter_zero_current_hp(self, validator):
        """Encounter with 0 current HP (fainted) should be valid."""
        fainted_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 0,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "ko",
            "personality_value": 3849273841
        }

        validator.validate(fainted_encounter)


class TestInvalidEncounters:
    """Test cases for invalid encounter JSON data."""

    def test_invalid_species_id_too_low(self, validator):
        """Species ID of 0 should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 0,  # Invalid: must be >= 1
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(invalid_encounter)
        assert "species_id" in str(exc_info.value).lower()

    def test_invalid_species_id_too_high(self, validator):
        """Species ID of 494 should fail validation (Gen 4 max is 493)."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 494,  # Invalid: must be <= 493
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_level_too_low(self, validator):
        """Level of 0 should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 0,  # Invalid: must be >= 1
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_level_too_high(self, validator):
        """Level of 101 should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 101,  # Invalid: must be <= 100
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_missing_required_field_timestamp(self, validator):
        """Missing timestamp should fail validation."""
        invalid_encounter = {
            # Missing "timestamp"
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_missing_required_field_species_id(self, validator):
        """Missing species_id should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            # Missing "species_id"
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_status_not_in_enum(self, validator):
        """Status value not in enum should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "invalid_status",  # Invalid: must be one of [encountered, caught, ko, run]
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_encounter_type_not_in_enum(self, validator):
        """Encounter type not in enum should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "trainer",  # Invalid: must be "wild" or "legendary"
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_max_hp_zero(self, validator):
        """Max HP of 0 should fail validation (minimum is 1)."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 0,
            "max_hp": 0,  # Invalid: must be >= 1
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_current_hp_negative(self, validator):
        """Negative current HP should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": -1,  # Invalid: must be >= 0
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_personality_value_negative(self, validator):
        """Negative personality value should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": -1  # Invalid: must be >= 0
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)

    def test_invalid_personality_value_too_large(self, validator):
        """Personality value exceeding 32-bit max should fail validation."""
        invalid_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 4294967296  # Invalid: max is 2^32 - 1 = 4294967295
        }

        with pytest.raises(ValidationError):
            validator.validate(invalid_encounter)


class TestSchemaConstraints:
    """Test schema-level constraints and metadata."""

    def test_schema_is_draft7(self, schema):
        """Schema should declare Draft 7 compatibility."""
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"

    def test_schema_no_additional_properties(self, schema):
        """Schema should not allow additional properties."""
        assert schema["additionalProperties"] is False

    def test_schema_required_fields_count(self, schema):
        """Schema should have exactly 9 required fields."""
        expected_required = [
            "timestamp",
            "player_name",
            "species_id",
            "level",
            "current_hp",
            "max_hp",
            "encounter_type",
            "status",
            "personality_value"
        ]
        assert sorted(schema["required"]) == sorted(expected_required)
