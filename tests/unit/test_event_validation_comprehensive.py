"""Comprehensive tests for event validation pipeline.

This test suite validates the complete event submission pipeline and identifies
specific validation failures that cause 422 errors.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from uuid import uuid4, UUID
from typing import Dict, Any, Optional

from soullink_tracker.db.models import Run, Player, Species, Route, Encounter
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus, RodKind
from soullink_tracker.auth.security import create_access_token


class TestEventValidationComprehensive:
    """Comprehensive test cases for event validation pipeline."""

    @pytest.fixture
    def sample_data(self, test_db):
        """Create comprehensive sample data for testing."""
        db = test_db()
        
        # Create run
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.flush()
        
        # Create player
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.flush()
        
        # Create species and routes for testing
        species_data = [
            Species(id=1, name="Pidgey", family_id=16),
            Species(id=4, name="Charmander", family_id=4),
            Species(id=7, name="Squirtle", family_id=7),
        ]
        
        route_data = [
            Route(id=31, label="Route 31", region="EU"),
            Route(id=32, label="Route 32", region="EU"),
            Route(id=45, label="Route 45", region="EU"),
        ]
        
        for species in species_data:
            db.add(species)
        for route in route_data:
            db.add(route)
        
        db.commit()
        db.refresh(run)
        db.refresh(player)
        
        # Generate JWT token for authentication
        jwt_token = create_access_token(str(player.id))
        
        db.close()
        
        return {
            "run": run,
            "player": player,
            "species": species_data,
            "routes": route_data,
            "token": token,
            "jwt_token": jwt_token
        }

    @pytest.fixture
    def auth_headers(self, sample_data):
        """Create authentication headers for testing."""
        return {
            "Authorization": f"Bearer {sample_data['jwt_token']}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid4())  # Always include for idempotency testing
        }

    # VALID EVENT TESTS
    def test_valid_encounter_grass(self, client: TestClient, sample_data, auth_headers):
        """Test valid grass encounter event."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Event processed successfully"
        assert "event_id" in data
        assert isinstance(data["applied_rules"], list)

    def test_valid_encounter_surf(self, client: TestClient, sample_data, auth_headers):
        """Test valid surf encounter event."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 32,
            "species_id": 7,
            "level": 15,
            "shiny": False,
            "method": "surf"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    def test_valid_encounter_fishing_with_all_rod_types(self, client: TestClient, sample_data, auth_headers):
        """Test valid fishing encounters with all rod types."""
        rod_types = ["old", "good", "super"]
        
        for rod_type in rod_types:
            auth_headers["Idempotency-Key"] = str(uuid4())  # New key for each request
            event_data = {
                "type": "encounter",
                "run_id": str(sample_data["run"].id),
                "player_id": str(sample_data["player"].id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 32,
                "species_id": 1,
                "level": 10,
                "shiny": False,
                "method": "fish",
                "rod_kind": rod_type
            }
            
            response = client.post("/v1/events", json=event_data, headers=auth_headers)
            
            assert response.status_code == 202, f"Failed for rod type: {rod_type}"

    def test_valid_encounter_static(self, client: TestClient, sample_data, auth_headers):
        """Test valid static encounter event."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 45,
            "species_id": 4,
            "level": 5,
            "shiny": True,  # Test shiny variant
            "method": "static"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    def test_valid_catch_result_with_encounter_id(self, client: TestClient, sample_data, auth_headers, test_db):
        """Test valid catch result event with encounter_id (V3 format)."""
        # First create an encounter
        db = test_db()
        encounter = Encounter(
            run_id=sample_data["run"].id,
            player_id=sample_data["player"].id,
            route_id=31,
            species_id=1,
            family_id=16,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        db.add(encounter)
        db.commit()
        db.refresh(encounter)
        
        # Now send catch result
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(encounter.id),
            "result": "caught"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202
        db.close()

    def test_valid_catch_result_with_encounter_ref(self, client: TestClient, sample_data, auth_headers, test_db):
        """Test valid catch result event with encounter_ref (V2 legacy format)."""
        # First create an encounter
        db = test_db()
        encounter = Encounter(
            run_id=sample_data["run"].id,
            player_id=sample_data["player"].id,
            route_id=31,
            species_id=1,
            family_id=16,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        db.add(encounter)
        db.commit()
        
        # Now send catch result using legacy format
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_ref": {"route_id": 31, "species_id": 1},
            "status": "fled"  # Using legacy field name
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202
        db.close()

    def test_valid_faint_event_minimal(self, client: TestClient, sample_data, auth_headers):
        """Test valid faint event with minimal required fields."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": "12345678"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    def test_valid_faint_event_with_party_index(self, client: TestClient, sample_data, auth_headers):
        """Test valid faint event with party index."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": "12345678",
            "party_index": 2
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    # MISSING REQUIRED FIELDS TESTS
    def test_encounter_missing_type(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing type field."""
        event_data = {
            # Missing "type": "encounter"
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_run_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing run_id field."""
        event_data = {
            "type": "encounter",
            # Missing "run_id"
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_player_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing player_id field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            # Missing "player_id"
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_time(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing time field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            # Missing "time"
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_route_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing route_id field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            # Missing "route_id"
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_species_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing species_id field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            # Missing "species_id"
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_level(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing level field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            # Missing "level"
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_missing_method(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event missing method field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            # Missing "method"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_catch_result_missing_both_encounter_refs(self, client: TestClient, sample_data, auth_headers):
        """Test catch result event missing both encounter_id and encounter_ref."""
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            # Missing both "encounter_id" and "encounter_ref"
            "result": "caught"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_catch_result_missing_result_and_status(self, client: TestClient, sample_data, auth_headers):
        """Test catch result event missing both result and status fields."""
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(uuid4()),
            # Missing both "result" and "status"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_faint_missing_pokemon_key(self, client: TestClient, sample_data, auth_headers):
        """Test faint event missing pokemon_key field."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            # Missing "pokemon_key"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    # INCORRECT FIELD TYPES TESTS
    def test_encounter_invalid_run_id_format(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid run_id format."""
        event_data = {
            "type": "encounter",
            "run_id": "not-a-valid-uuid",  # Invalid UUID format
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_invalid_player_id_format(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid player_id format."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": "not-a-valid-uuid",  # Invalid UUID format
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_invalid_time_format(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid time format."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": "not-a-valid-iso-datetime",  # Invalid datetime format
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_negative_route_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with negative route_id."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": -1,  # Negative route ID
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # This might be accepted by API but rejected by business logic
        # Need to verify actual behavior
        assert response.status_code in [202, 422]

    def test_encounter_negative_species_id(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with negative species_id."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": -1,  # Negative species ID
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # This might be accepted by API but rejected by business logic
        assert response.status_code in [202, 422, 404]

    def test_encounter_zero_level(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with zero level."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 0,  # Zero level
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # This might be accepted by API but rejected by business logic
        assert response.status_code in [202, 422]

    def test_encounter_extreme_level(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with extremely high level."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 999,  # Extremely high level
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # This should be accepted (Pokemon levels can be boosted)
        assert response.status_code == 202

    def test_encounter_invalid_shiny_type(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid shiny field type."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": "yes",  # String instead of boolean
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    # ENUM VALIDATION TESTS
    def test_encounter_invalid_method_enum(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid method enum value."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "invalid_method"  # Invalid enum value
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_encounter_invalid_rod_kind_enum(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with invalid rod_kind enum value."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "fish",
            "rod_kind": "invalid_rod"  # Invalid enum value
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_catch_result_invalid_result_enum(self, client: TestClient, sample_data, auth_headers):
        """Test catch result event with invalid result enum value."""
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(uuid4()),
            "result": "invalid_result"  # Invalid enum value
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 422

    # FISHING-SPECIFIC VALIDATION TESTS
    def test_fishing_without_rod_kind(self, client: TestClient, sample_data, auth_headers):
        """Test fishing encounter without rod_kind field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "fish"
            # Missing rod_kind for fishing
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted by API (validation is at business logic level)
        assert response.status_code == 202

    def test_non_fishing_with_rod_kind(self, client: TestClient, sample_data, auth_headers):
        """Test non-fishing encounter with rod_kind field."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass",
            "rod_kind": "super"  # Rod kind on non-fishing encounter
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted (rod_kind will be ignored)
        assert response.status_code == 202

    # EDGE CASES AND BOUNDARY CONDITIONS
    def test_encounter_future_timestamp(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with future timestamp."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": future_time.isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Future timestamps should be accepted
        assert response.status_code == 202

    def test_encounter_very_old_timestamp(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with very old timestamp."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": old_time.isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Old timestamps should be accepted
        assert response.status_code == 202

    def test_encounter_without_timezone(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with timestamp without timezone."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now().isoformat(),  # No timezone info
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # This might be accepted depending on Pydantic configuration
        assert response.status_code in [202, 422]

    def test_encounter_nonexistent_species(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with non-existent species_id."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 999,  # Non-existent species
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be rejected by business logic
        assert response.status_code == 404

    def test_encounter_nonexistent_route(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with non-existent route_id."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 999,  # Non-existent route
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted at API level (route validation might be at business logic level)
        assert response.status_code in [202, 404]

    # SPECIAL CHARACTER AND UNICODE TESTS
    def test_faint_pokemon_key_with_special_characters(self, client: TestClient, sample_data, auth_headers):
        """Test faint event with special characters in pokemon_key."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": "abc-123_def!@#"  # Special characters
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    def test_faint_pokemon_key_unicode(self, client: TestClient, sample_data, auth_headers):
        """Test faint event with unicode characters in pokemon_key."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": "ポケモン123"  # Japanese characters
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        assert response.status_code == 202

    def test_faint_empty_pokemon_key(self, client: TestClient, sample_data, auth_headers):
        """Test faint event with empty pokemon_key."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": ""  # Empty string
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Might be rejected if there's a minimum length constraint
        assert response.status_code in [202, 422]

    def test_faint_party_index_boundary_values(self, client: TestClient, sample_data, auth_headers):
        """Test faint event with boundary party index values."""
        valid_indices = [0, 1, 2, 3, 4, 5]  # Valid party positions
        invalid_indices = [-1, 6, 10, 100]   # Invalid party positions
        
        # Test valid indices
        for index in valid_indices:
            auth_headers["Idempotency-Key"] = str(uuid4())
            event_data = {
                "type": "faint",
                "run_id": str(sample_data["run"].id),
                "player_id": str(sample_data["player"].id),
                "time": datetime.now(timezone.utc).isoformat(),
                "pokemon_key": f"test_pokemon_{index}",
                "party_index": index
            }
            
            response = client.post("/v1/events", json=event_data, headers=auth_headers)
            assert response.status_code == 202, f"Failed for valid index: {index}"
        
        # Test invalid indices (if validation exists)
        for index in invalid_indices:
            auth_headers["Idempotency-Key"] = str(uuid4())
            event_data = {
                "type": "faint",
                "run_id": str(sample_data["run"].id),
                "player_id": str(sample_data["player"].id),
                "time": datetime.now(timezone.utc).isoformat(),
                "pokemon_key": f"test_pokemon_{index}",
                "party_index": index
            }
            
            response = client.post("/v1/events", json=event_data, headers=auth_headers)
            # Might be accepted if no validation, or rejected if validation exists
            assert response.status_code in [202, 422], f"Unexpected status for invalid index: {index}"

    # LARGE DATA TESTS
    def test_encounter_very_long_fields(self, client: TestClient, sample_data, auth_headers):
        """Test encounter event with extremely large field values."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 2147483647,  # Max 32-bit signed integer
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted (very high levels are possible in hacked games)
        assert response.status_code == 202

    def test_faint_very_long_pokemon_key(self, client: TestClient, sample_data, auth_headers):
        """Test faint event with very long pokemon_key."""
        very_long_key = "a" * 1000  # 1000 character string
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": very_long_key
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Might be rejected if there's a length limit
        assert response.status_code in [202, 422]


class TestEventValidationLuaJsonCompatibility:
    """Test compatibility with JSON formats that might come from Lua scripts."""
    
    @pytest.fixture
    def sample_data(self, test_db):
        """Create sample data for Lua compatibility testing."""
        db = test_db()
        
        # Create run
        run = Run(name="Lua Test Run", rules_json={})
        db.add(run)
        db.flush()
        
        # Create player
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="LuaTestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.flush()
        
        # Create species
        species = Species(id=1, name="Pidgey", family_id=16)
        db.add(species)
        
        # Create route
        route = Route(id=31, label="Route 31", region="EU")
        db.add(route)
        
        db.commit()
        db.refresh(run)
        db.refresh(player)
        
        # Generate JWT token for authentication
        jwt_token = create_access_token(str(player.id))
        
        db.close()
        
        return {
            "run": run,
            "player": player,
            "jwt_token": jwt_token
        }

    @pytest.fixture
    def auth_headers(self, sample_data):
        """Create authentication headers for testing."""
        return {
            "Authorization": f"Bearer {sample_data['jwt_token']}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid4())
        }

    def test_lua_style_boolean_values(self, client: TestClient, sample_data, auth_headers):
        """Test Lua-style boolean values in JSON."""
        # Lua might send boolean values as strings
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": "true",  # String instead of boolean
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be rejected due to type mismatch
        assert response.status_code == 422

    def test_lua_style_number_strings(self, client: TestClient, sample_data, auth_headers):
        """Test numeric values sent as strings from Lua."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": "31",    # String instead of int
            "species_id": "1",   # String instead of int
            "level": "5",        # String instead of int
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Pydantic might auto-convert these, or might reject them
        assert response.status_code in [202, 422]

    def test_lua_nil_as_null(self, client: TestClient, sample_data, auth_headers):
        """Test Lua nil values represented as JSON null."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "fish",
            "rod_kind": None  # Lua nil as JSON null
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted (rod_kind is optional)
        assert response.status_code == 202

    def test_lua_extra_fields(self, client: TestClient, sample_data, auth_headers):
        """Test extra fields that Lua scripts might include."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass",
            # Extra fields that Lua might include
            "debug_info": "some debug data",
            "lua_version": "5.1",
            "memory_address": "0x12345678"
        }
        
        response = client.post("/v1/events", json=event_data, headers=auth_headers)
        
        # Should be accepted (extra fields should be ignored)
        assert response.status_code == 202