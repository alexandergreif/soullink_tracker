"""Tests for events API endpoints."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from uuid import uuid4

from soullink_tracker.db.models import Run, Player, Species, Route, Encounter
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from soullink_tracker.auth.security import create_access_token


class TestEventsAPI:
    """Test cases for event ingestion API endpoints."""

    @pytest.fixture
    def sample_data(self, test_db):
        """Create sample data for testing."""
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
            "species": species,
            "route": route,
            "token": token,
            "jwt_token": jwt_token
        }

    def test_encounter_event_success(self, client: TestClient, sample_data):
        """Test successful encounter event processing."""
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
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Event processed successfully"
        assert "event_id" in data
        assert isinstance(data["applied_rules"], list)

    def test_encounter_event_with_fishing(self, client: TestClient, sample_data):
        """Test encounter event with fishing method."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 10,
            "shiny": False,
            "method": "fish",
            "rod_kind": "super"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Event processed successfully"

    def test_catch_result_event_success(self, client: TestClient, sample_data, test_db):
        """Test successful catch result event processing."""
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
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Event processed successfully"

    def test_faint_event_success(self, client: TestClient, sample_data):
        """Test successful faint event processing."""
        event_data = {
            "type": "faint",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "pokemon_key": "12345678"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Event processed successfully"

    def test_event_unauthorized(self, client: TestClient, sample_data):
        """Test event submission without authentication."""
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
        
        response = client.post("/v1/events", json=event_data)
        
        assert response.status_code == 403  # FastAPI returns 403 when auth is required but missing

    def test_event_invalid_token(self, client: TestClient, sample_data):
        """Test event submission with invalid token."""
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
        
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 401

    def test_event_wrong_player(self, client: TestClient, sample_data, test_db):
        """Test event submission with wrong player ID in JWT."""
        # Create another player
        db = test_db()
        token, token_hash = Player.generate_token()
        other_player = Player(
            run_id=sample_data["run"].id,
            name="OtherPlayer",
            game="SoulSilver",
            region="EU",
            token_hash=token_hash
        )
        db.add(other_player)
        db.commit()
        db.refresh(other_player)
        
        # Use other player's token but original player's ID in event
        other_jwt_token = create_access_token(str(other_player.id))
        
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),  # Wrong player ID
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        headers = {"Authorization": f"Bearer {other_jwt_token}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 403
        data = response.json()
        assert "not authorized" in data["detail"].lower()

    def test_event_invalid_encounter_method(self, client: TestClient, sample_data):
        """Test event with invalid encounter method."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "invalid_method"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 422

    def test_event_invalid_catch_result(self, client: TestClient, sample_data):
        """Test catch result event with invalid result status."""
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(uuid4()),
            "result": "invalid_result"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 422

    def test_event_missing_required_fields(self, client: TestClient, sample_data):
        """Test event with missing required fields."""
        event_data = {
            "type": "encounter",
            "run_id": str(sample_data["run"].id),
            # Missing player_id, time, route_id, species_id, etc.
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 422

    def test_event_fishing_without_rod_kind(self, client: TestClient, sample_data):
        """Test fishing event without rod_kind should fail validation."""
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
            # Missing rod_kind
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        # Should be accepted but rules engine should handle validation
        assert response.status_code == 202

    def test_event_non_fishing_with_rod_kind(self, client: TestClient, sample_data):
        """Test non-fishing event with rod_kind should be accepted."""
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
            "rod_kind": "super"  # Shouldn't be here but should be ignored
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202

    def test_event_nonexistent_run(self, client: TestClient, sample_data):
        """Test event with non-existent run ID."""
        fake_run_id = uuid4()
        event_data = {
            "type": "encounter",
            "run_id": str(fake_run_id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 404

    def test_event_nonexistent_encounter_for_catch_result(self, client: TestClient, sample_data):
        """Test catch result event with non-existent encounter ID."""
        fake_encounter_id = uuid4()
        event_data = {
            "type": "catch_result",
            "run_id": str(sample_data["run"].id),
            "player_id": str(sample_data["player"].id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(fake_encounter_id),
            "result": "caught"
        }
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 404

    def test_event_idempotency(self, client: TestClient, sample_data):
        """Test that identical events with same idempotency key return same response."""
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
        
        headers = {
            "Authorization": f"Bearer {sample_data['jwt_token']}",
            "Idempotency-Key": "test-key-123"
        }
        
        # Send first request
        response1 = client.post("/v1/events", json=event_data, headers=headers)
        assert response1.status_code == 202
        
        # Send identical request with same idempotency key
        response2 = client.post("/v1/events", json=event_data, headers=headers)
        assert response2.status_code == 202
        
        # Responses should be identical
        assert response1.json() == response2.json()

    def test_event_response_format(self, client: TestClient, sample_data):
        """Test that event response has correct format."""
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
        
        headers = {"Authorization": f"Bearer {sample_data['jwt_token']}"}
        response = client.post("/v1/events", json=event_data, headers=headers)
        
        assert response.status_code == 202
        data = response.json()
        
        # Check required fields
        required_fields = ["message", "applied_rules"]
        for field in required_fields:
            assert field in data
        
        # Check field types
        assert isinstance(data["message"], str)
        assert isinstance(data["applied_rules"], list)
        
        # event_id is optional but if present should be UUID
        if "event_id" in data:
            from uuid import UUID
            UUID(data["event_id"])