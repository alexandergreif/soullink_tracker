"""
Unit Test: Encounter Pydantic Model

Tests the Encounter model field validation and constraints.
These tests MUST FAIL initially (TDD red phase) until model is implemented.

Expected: All tests FAIL (Encounter model does not exist yet)
"""

import pytest
from datetime import datetime
from pydantic import ValidationError


class TestEncounterModelValidation:
    """Test Encounter model field validation."""

    def test_valid_encounter_model_instantiation(self):
        """Valid encounter data should create model instance successfully."""
        # This import will fail initially - expected TDD red phase
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        encounter = Encounter(
            timestamp="2025-10-01T14:30:52Z",
            player_name="Alice",
            species_id=25,
            species_name="Pikachu",
            level=12,
            current_hp=35,
            max_hp=35,
            location_id=None,
            location_name="Route 29",
            encounter_type="wild",
            status="encountered",
            personality_value=3849273841
        )

        assert encounter.species_id == 25
        assert encounter.player_name == "Alice"
        assert encounter.level == 12
        assert encounter.status == "encountered"

    def test_species_id_range_validation_too_low(self):
        """Species ID below 1 should raise ValidationError."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError) as exc_info:
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=0,  # Invalid
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

        assert "species_id" in str(exc_info.value).lower()

    def test_species_id_range_validation_too_high(self):
        """Species ID above 493 should raise ValidationError."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=494,  # Invalid (Gen 4 max is 493)
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

    def test_level_range_validation_too_low(self):
        """Level below 1 should raise ValidationError."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=0,  # Invalid
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

    def test_level_range_validation_too_high(self):
        """Level above 100 should raise ValidationError."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=101,  # Invalid
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

    def test_hp_constraint_current_exceeds_max(self):
        """Current HP exceeding max HP should raise ValidationError."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError) as exc_info:
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=50,  # Invalid (exceeds max_hp)
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

        assert "hp" in str(exc_info.value).lower()

    def test_hp_constraint_max_hp_zero(self):
        """Max HP of 0 should raise ValidationError (minimum is 1)."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=0,
                max_hp=0,  # Invalid
                encounter_type="wild",
                status="encountered",
                personality_value=3849273841
            )

    def test_hp_constraint_current_hp_zero_allowed(self):
        """Current HP of 0 should be allowed (fainted Pokemon)."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        encounter = Encounter(
            timestamp="2025-10-01T14:30:52Z",
            player_name="Alice",
            species_id=25,
            level=12,
            current_hp=0,  # Valid (fainted)
            max_hp=35,
            encounter_type="wild",
            status="ko",
            personality_value=3849273841
        )

        assert encounter.current_hp == 0

    def test_encounter_type_enum_validation(self):
        """Encounter type must be 'wild' or 'legendary'."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="trainer",  # Invalid
                status="encountered",
                personality_value=3849273841
            )

    def test_status_enum_validation(self):
        """Status must be one of: encountered, caught, ko, run."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="invalid_status",  # Invalid
                personality_value=3849273841
            )

    def test_optional_fields_can_be_none(self):
        """Optional fields (location_id, location_name, species_name) can be None."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        encounter = Encounter(
            timestamp="2025-10-01T14:30:52Z",
            player_name="Alice",
            species_id=25,
            species_name=None,  # Optional
            level=12,
            current_hp=35,
            max_hp=35,
            location_id=None,  # Optional
            location_name=None,  # Optional
            encounter_type="wild",
            status="encountered",
            personality_value=3849273841
        )

        assert encounter.species_name is None
        assert encounter.location_id is None
        assert encounter.location_name is None

    def test_timestamp_type_coercion(self):
        """String timestamp should be accepted and parseable."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        encounter = Encounter(
            timestamp="2025-10-01T14:30:52Z",
            player_name="Alice",
            species_id=25,
            level=12,
            current_hp=35,
            max_hp=35,
            encounter_type="wild",
            status="encountered",
            personality_value=3849273841
        )

        # Timestamp should be stored as string (ISO 8601 format)
        assert isinstance(encounter.timestamp, str)
        assert "2025-10-01" in encounter.timestamp

    def test_personality_value_range_validation(self):
        """Personality value must be valid 32-bit unsigned integer."""
        try:
            from src.models.encounter import Encounter
        except ImportError:
            pytest.fail("Encounter model not implemented yet (expected TDD failure)")

        # Valid: Max 32-bit value (2^32 - 1 = 4294967295)
        encounter = Encounter(
            timestamp="2025-10-01T14:30:52Z",
            player_name="Alice",
            species_id=25,
            level=12,
            current_hp=35,
            max_hp=35,
            encounter_type="wild",
            status="encountered",
            personality_value=4294967295
        )
        assert encounter.personality_value == 4294967295

        # Invalid: Exceeds 32-bit max
        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=4294967296  # Too large
            )

        # Invalid: Negative value
        with pytest.raises(ValidationError):
            Encounter(
                timestamp="2025-10-01T14:30:52Z",
                player_name="Alice",
                species_id=25,
                level=12,
                current_hp=35,
                max_hp=35,
                encounter_type="wild",
                status="encountered",
                personality_value=-1  # Negative
            )
