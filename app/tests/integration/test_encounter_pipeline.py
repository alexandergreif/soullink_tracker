"""
Integration Test: Encounter Pipeline (JSON → Database)

Tests the full encounter processing pipeline:
1. JSON file created (simulating Lua export)
2. File watcher detects new file
3. JSON parsed and validated
4. Data inserted into SQLite database
5. Soullink rules enforced (duplicate detection)
6. Legendary exemptions handled

These tests MUST FAIL initially (TDD red phase) until implementation exists.

Expected: All tests FAIL (no database, file watcher, or models exist yet)
"""

import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from datetime import datetime


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    # Initialize database schema (will fail until database.py exists)
    # This import will fail initially - expected TDD red phase
    try:
        from app.src.services.database import init_database
        init_database(db_path)
    except ImportError:
        pytest.fail("Database service not implemented yet (expected TDD failure)")

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_encounters_dir():
    """Create a temporary directory for encounter JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_encounter_wild():
    """Sample wild Pokemon encounter data."""
    return {
        "timestamp": "2025-10-01T14:30:52Z",
        "player_name": "Alice",
        "species_id": 25,
        "species_name": "Pikachu",
        "level": 12,
        "current_hp": 35,
        "max_hp": 35,
        "location_id": None,
        "location_name": "Route 29",
        "encounter_type": "wild",
        "status": "encountered",
        "personality_value": 3849273841
    }


@pytest.fixture
def sample_encounter_legendary():
    """Sample legendary Pokemon encounter data."""
    return {
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


class TestSinglePlayerEncounterTracking:
    """Test basic encounter tracking for a single player."""

    def test_process_single_encounter_json_to_database(self, temp_db, temp_encounters_dir, sample_encounter_wild):
        """Single encounter JSON should be inserted into database."""
        # This will fail until file_watcher.py and database.py exist
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import query_encounters
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Create JSON file
        json_file = temp_encounters_dir / "encounter_20251001_143052_Alice.json"
        with open(json_file, 'w') as f:
            json.dump(sample_encounter_wild, f)

        # Process file
        process_encounter_file(str(json_file), temp_db)

        # Query database
        encounters = query_encounters(temp_db, player_name="Alice")

        assert len(encounters) == 1
        assert encounters[0]["species_id"] == 25
        assert encounters[0]["species_name"] == "Pikachu"
        assert encounters[0]["level"] == 12
        assert encounters[0]["status"] == "encountered"

    def test_process_multiple_encounters_same_player(self, temp_db, temp_encounters_dir):
        """Multiple encounters from same player should all be inserted."""
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import query_encounters
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Create multiple encounter files
        encounters = [
            {"timestamp": "2025-10-01T14:30:52Z", "player_name": "Alice", "species_id": 25, "level": 12,
             "current_hp": 35, "max_hp": 35, "encounter_type": "wild", "status": "encountered",
             "personality_value": 3849273841},
            {"timestamp": "2025-10-01T14:35:10Z", "player_name": "Alice", "species_id": 19, "level": 5,
             "current_hp": 20, "max_hp": 20, "encounter_type": "wild", "status": "encountered",
             "personality_value": 1234567890},
            {"timestamp": "2025-10-01T14:40:22Z", "player_name": "Alice", "species_id": 16, "level": 8,
             "current_hp": 28, "max_hp": 28, "encounter_type": "wild", "status": "encountered",
             "personality_value": 9876543210}
        ]

        for i, encounter in enumerate(encounters):
            json_file = temp_encounters_dir / f"encounter_{i}.json"
            with open(json_file, 'w') as f:
                json.dump(encounter, f)
            process_encounter_file(str(json_file), temp_db)

        # Query all encounters for Alice
        results = query_encounters(temp_db, player_name="Alice")
        assert len(results) == 3


class TestSoulinkDuplicateDetection:
    """Test Soullink rule enforcement (one species per all players)."""

    def test_alice_catches_pikachu_bob_blocked(self, temp_db, temp_encounters_dir):
        """When Alice catches Pikachu, Bob should be blocked from catching it."""
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import check_duplicate_species, query_encounters
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Alice catches Pikachu (species_id = 25)
        alice_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "caught",  # Status = caught triggers soullink rule
            "personality_value": 3849273841
        }

        json_file = temp_encounters_dir / "encounter_alice_pikachu.json"
        with open(json_file, 'w') as f:
            json.dump(alice_encounter, f)
        process_encounter_file(str(json_file), temp_db)

        # Bob encounters Pikachu
        bob_encounter = {
            "timestamp": "2025-10-01T15:00:00Z",
            "player_name": "Bob",
            "species_id": 25,
            "level": 10,
            "current_hp": 30,
            "max_hp": 30,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 9999999999
        }

        # Check if duplicate
        is_duplicate = check_duplicate_species(temp_db, 25)
        assert is_duplicate is True

        # Bob's encounter should still be inserted, but marked as duplicate
        json_file2 = temp_encounters_dir / "encounter_bob_pikachu.json"
        with open(json_file2, 'w') as f:
            json.dump(bob_encounter, f)
        process_encounter_file(str(json_file2), temp_db)

        # Both encounters should exist in database
        all_encounters = query_encounters(temp_db, species_id=25)
        assert len(all_encounters) == 2

        # But only Alice's should have triggered soullink rule
        alice_records = [e for e in all_encounters if e["player_name"] == "Alice"]
        assert alice_records[0]["status"] == "caught"

    def test_soullink_rule_prevents_second_catch(self, temp_db, temp_encounters_dir):
        """Attempting to insert second catch of same species should fail or log error."""
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import insert_soullink_rule
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Alice catches Rattata
        alice_encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 19,
            "level": 5,
            "current_hp": 20,
            "max_hp": 20,
            "encounter_type": "wild",
            "status": "caught",
            "personality_value": 1111111111
        }

        json_file = temp_encounters_dir / "encounter_alice_rattata.json"
        with open(json_file, 'w') as f:
            json.dump(alice_encounter, f)
        process_encounter_file(str(json_file), temp_db)

        # Bob tries to catch Rattata (should fail soullink rule insertion)
        bob_encounter = {
            "timestamp": "2025-10-01T15:00:00Z",
            "player_name": "Bob",
            "species_id": 19,
            "level": 7,
            "current_hp": 25,
            "max_hp": 25,
            "encounter_type": "wild",
            "status": "caught",
            "personality_value": 2222222222
        }

        json_file2 = temp_encounters_dir / "encounter_bob_rattata.json"
        with open(json_file2, 'w') as f:
            json.dump(bob_encounter, f)

        # Should log IntegrityError but not crash
        # Implementation should handle gracefully
        process_encounter_file(str(json_file2), temp_db)


class TestLegendaryExemption:
    """Test that legendary Pokemon are exempt from Soullink duplicate rule."""

    def test_multiple_players_catch_same_legendary(self, temp_db, temp_encounters_dir, sample_encounter_legendary):
        """Both Alice and Bob should be able to catch Lugia (legendary exemption)."""
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import query_encounters, check_duplicate_species
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Alice catches Lugia
        alice_lugia = sample_encounter_legendary.copy()
        alice_lugia["player_name"] = "Alice"
        alice_lugia["status"] = "caught"
        alice_lugia["timestamp"] = "2025-10-01T14:00:00Z"
        alice_lugia["personality_value"] = 1111111111

        json_file1 = temp_encounters_dir / "encounter_alice_lugia.json"
        with open(json_file1, 'w') as f:
            json.dump(alice_lugia, f)
        process_encounter_file(str(json_file1), temp_db)

        # Bob catches Lugia (should succeed - legendary exemption)
        bob_lugia = sample_encounter_legendary.copy()
        bob_lugia["player_name"] = "Bob"
        bob_lugia["status"] = "caught"
        bob_lugia["timestamp"] = "2025-10-01T15:00:00Z"
        bob_lugia["personality_value"] = 2222222222

        json_file2 = temp_encounters_dir / "encounter_bob_lugia.json"
        with open(json_file2, 'w') as f:
            json.dump(bob_lugia, f)
        process_encounter_file(str(json_file2), temp_db)

        # Both encounters should exist
        lugia_encounters = query_encounters(temp_db, species_id=249)
        assert len(lugia_encounters) == 2

        # Lugia should NOT be in soullink_rules table (legendary exemption)
        is_duplicate = check_duplicate_species(temp_db, 249)
        assert is_duplicate is False


class TestStatusTransitions:
    """Test encounter status lifecycle (encountered → caught/ko/run)."""

    def test_encounter_status_transitions(self, temp_db, temp_encounters_dir):
        """Encounter status should update from encountered to caught/ko/run."""
        try:
            from app.src.services.file_watcher import process_encounter_file
            from app.src.services.database import query_encounters
        except ImportError:
            pytest.fail("Services not implemented yet (expected TDD failure)")

        # Initial encounter (status = encountered)
        encounter = {
            "timestamp": "2025-10-01T14:30:52Z",
            "player_name": "Alice",
            "species_id": 25,
            "level": 12,
            "current_hp": 35,
            "max_hp": 35,
            "encounter_type": "wild",
            "status": "encountered",
            "personality_value": 3849273841
        }

        json_file = temp_encounters_dir / "encounter_pikachu.json"
        with open(json_file, 'w') as f:
            json.dump(encounter, f)
        process_encounter_file(str(json_file), temp_db)

        # Verify initial status
        results = query_encounters(temp_db, player_name="Alice")
        assert results[0]["status"] == "encountered"

        # Note: Status update logic will be tested in API layer (Phase 5)
        # This test validates initial insertion only
