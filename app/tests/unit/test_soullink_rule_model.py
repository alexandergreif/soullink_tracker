"""
Unit Test: SoulinkRule Pydantic Model

Tests the SoulinkRule model field validation and constraints.
These tests MUST FAIL initially (TDD red phase) until model is implemented.

Expected: All tests FAIL (SoulinkRule model does not exist yet)
"""

import pytest
from pydantic import ValidationError


class TestSoulinkRuleModelValidation:
    """Test SoulinkRule model field validation."""

    def test_valid_soullink_rule_model_instantiation(self):
        """Valid soullink rule data should create model instance successfully."""
        # This import will fail initially - expected TDD red phase
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        rule = SoulinkRule(
            species_id=25,
            caught_by_player="Alice",
            caught_at="2025-10-01T14:30:52Z"
        )

        assert rule.species_id == 25
        assert rule.caught_by_player == "Alice"
        assert "2025-10-01" in rule.caught_at

    def test_species_id_required_field(self):
        """Species ID is a required field."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError) as exc_info:
            SoulinkRule(
                # Missing species_id
                caught_by_player="Alice",
                caught_at="2025-10-01T14:30:52Z"
            )

        assert "species_id" in str(exc_info.value).lower()

    def test_caught_by_player_required_field(self):
        """Caught by player is a required field."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError) as exc_info:
            SoulinkRule(
                species_id=25,
                # Missing caught_by_player
                caught_at="2025-10-01T14:30:52Z"
            )

        assert "caught_by_player" in str(exc_info.value).lower()

    def test_caught_at_required_field(self):
        """Caught at timestamp is a required field."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError) as exc_info:
            SoulinkRule(
                species_id=25,
                caught_by_player="Alice"
                # Missing caught_at
            )

        assert "caught_at" in str(exc_info.value).lower()

    def test_species_id_range_validation_too_low(self):
        """Species ID below 1 should raise ValidationError."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            SoulinkRule(
                species_id=0,  # Invalid
                caught_by_player="Alice",
                caught_at="2025-10-01T14:30:52Z"
            )

    def test_species_id_range_validation_too_high(self):
        """Species ID above 493 should raise ValidationError."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            SoulinkRule(
                species_id=494,  # Invalid (Gen 4 max is 493)
                caught_by_player="Alice",
                caught_at="2025-10-01T14:30:52Z"
            )

    def test_species_id_valid_range(self):
        """Species ID within valid range [1, 493] should be accepted."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        # Test boundary values
        rule_min = SoulinkRule(
            species_id=1,  # Min valid
            caught_by_player="Alice",
            caught_at="2025-10-01T14:30:52Z"
        )
        assert rule_min.species_id == 1

        rule_max = SoulinkRule(
            species_id=493,  # Max valid (Gen 4)
            caught_by_player="Bob",
            caught_at="2025-10-01T14:30:52Z"
        )
        assert rule_max.species_id == 493

    def test_timestamp_format_validation(self):
        """Timestamp should be valid ISO 8601 format."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        # Valid ISO 8601 formats
        valid_formats = [
            "2025-10-01T14:30:52Z",
            "2025-10-01T14:30:52+00:00",
            "2025-10-01T14:30:52.123Z"
        ]

        for timestamp in valid_formats:
            rule = SoulinkRule(
                species_id=25,
                caught_by_player="Alice",
                caught_at=timestamp
            )
            assert rule.caught_at == timestamp

    def test_player_name_non_empty_string(self):
        """Player name should be non-empty string."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        # Empty string should fail
        with pytest.raises(ValidationError):
            SoulinkRule(
                species_id=25,
                caught_by_player="",  # Invalid
                caught_at="2025-10-01T14:30:52Z"
            )

    def test_player_name_max_length(self):
        """Player name should respect max length constraint (50 chars)."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        # 50 chars should be valid
        valid_name = "A" * 50
        rule = SoulinkRule(
            species_id=25,
            caught_by_player=valid_name,
            caught_at="2025-10-01T14:30:52Z"
        )
        assert len(rule.caught_by_player) == 50

        # 51 chars should fail
        with pytest.raises(ValidationError):
            SoulinkRule(
                species_id=25,
                caught_by_player="A" * 51,  # Too long
                caught_at="2025-10-01T14:30:52Z"
            )

    def test_type_validation_species_id_not_integer(self):
        """Species ID must be an integer."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        with pytest.raises(ValidationError):
            SoulinkRule(
                species_id="25",  # String instead of int
                caught_by_player="Alice",
                caught_at="2025-10-01T14:30:52Z"
            )

    def test_model_immutability_optional(self):
        """Test that model fields can be accessed after creation."""
        try:
            from src.models.soullink_rule import SoulinkRule
        except ImportError:
            pytest.fail("SoulinkRule model not implemented yet (expected TDD failure)")

        rule = SoulinkRule(
            species_id=25,
            caught_by_player="Alice",
            caught_at="2025-10-01T14:30:52Z"
        )

        # Should be able to read all fields
        assert rule.species_id == 25
        assert rule.caught_by_player == "Alice"
        assert isinstance(rule.caught_at, str)
