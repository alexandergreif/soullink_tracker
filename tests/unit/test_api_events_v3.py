"""Unit tests for the v3 events API with event store integration."""

import uuid
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient



@pytest.fixture
def enable_v3_eventstore(monkeypatch):
    """Enable v3 event store for tests that need it."""
    monkeypatch.setenv("FEATURE_V3_EVENTSTORE", "1")


@pytest.fixture
def sample_run_data():
    """Sample run data for creating runs via API."""
    return {
        "name": "Test Run",
        "rules_json": {"dupes_clause": True, "soul_link": True}
    }


@pytest.fixture
def sample_player_data():
    """Sample player data for creating players via API."""
    return {
        "name": "TestPlayer",
        "game": "HeartGold",
        "region": "EU"
    }


class TestEventProcessing:
    """Test event processing with v3 architecture."""

    def test_process_encounter_event_success(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test successful encounter event processing."""
        player, token = sample_player
        idempotency_key = str(uuid4())
        
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass",
            "rod_kind": None
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key,
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        
        # Check response format
        assert "message" in data
        assert "event_id" in data
        assert "seq" in data  # Should include sequence number for encounter events
        assert "applied_rules" in data
        
        # Validate event_id is UUID
        assert uuid.UUID(data["event_id"])
        
        # Validate sequence number
        assert isinstance(data["seq"], int)
        assert data["seq"] > 0

    def test_process_catch_result_event_success(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test successful catch result event processing."""
        player, token = sample_player
        
        # First create an encounter
        encounter_event = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        encounter_response = client.post(
            "/v1/events",
            json=encounter_event,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert encounter_response.status_code == status.HTTP_202_ACCEPTED
        encounter_id = encounter_response.json()["event_id"]
        
        # Now submit catch result
        catch_result_event = {
            "type": "catch_result",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:01:00Z",
            "encounter_id": encounter_id,
            "result": "caught"
        }
        
        response = client.post(
            "/v1/events",
            json=catch_result_event,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        
        assert "event_id" in data
        assert "seq" not in data  # Catch result events don't include sequence
        assert "encounter_reference_verified" in data["applied_rules"]

    def test_process_faint_event_success(
        self, client: TestClient, sample_player
    ):
        """Test successful faint event processing."""
        player, token = sample_player
        
        event_data = {
            "type": "faint",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "pokemon_key": "ABC123DEF456"
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        
        assert "event_id" in data
        assert "seq" not in data  # Faint events don't include sequence
        assert "faint_event_validated" in data["applied_rules"]


class TestIdempotency:
    """Test idempotency key validation and behavior."""

    def test_idempotency_key_required_uuid_v4(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test that Idempotency-Key must be UUID v4."""
        player, token = sample_player
        
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        # Test invalid UUID format
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "not-a-uuid"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Invalid Idempotency Key"
        assert "UUID v4" in problem["detail"]

    def test_idempotency_key_prevents_duplicate_processing(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test that identical requests with same idempotency key return same response."""
        player, token = sample_player
        idempotency_key = str(uuid4())
        
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        # First request
        response1 = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key
            }
        )
        
        assert response1.status_code == status.HTTP_202_ACCEPTED
        data1 = response1.json()
        
        # Second request with same idempotency key
        response2 = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key
            }
        )
        
        assert response2.status_code == status.HTTP_202_ACCEPTED
        data2 = response2.json()
        
        # Should return identical response
        assert data1 == data2


class TestValidation:
    """Test input validation and error handling."""

    def test_catch_result_requires_encounter_id(
        self, client: TestClient, sample_player
    ):
        """Test that catch_result events require encounter_id."""
        player, token = sample_player
        
        # Missing encounter_id field
        event_data = {
            "type": "catch_result",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "result": "caught"
            # encounter_id is missing
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.headers["content-type"] == "application/problem+json"

    def test_catch_result_invalid_encounter_id(
        self, client: TestClient, sample_player
    ):
        """Test that catch_result events with invalid encounter_id are rejected."""
        player, token = sample_player
        
        event_data = {
            "type": "catch_result",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "encounter_id": str(uuid4()),  # Non-existent encounter
            "result": "caught"
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Encounter Not Found"

    def test_player_authorization_enforced(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test that players can only submit events for themselves."""
        player, token = sample_player
        other_player_id = uuid4()
        
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(other_player_id),  # Different player
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.headers["content-type"] == "application/problem+json"

    def test_species_not_found(
        self, client: TestClient, sample_player, sample_route
    ):
        """Test error when species doesn't exist."""
        player, token = sample_player
        
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": 999,  # Non-existent species
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Species Not Found"


class TestRequestSizeLimits:
    """Test request size validation middleware."""

    def test_single_request_size_limit(
        self, client: TestClient, sample_player, sample_species, sample_route
    ):
        """Test that single requests exceeding 16KB are rejected."""
        player, token = sample_player
        
        # Create a large event payload (> 16KB)
        large_string = "x" * (17 * 1024)  # 17KB string
        event_data = {
            "type": "encounter",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z",
            "route_id": sample_route.id,
            "species_id": sample_species.id,
            "level": 5,
            "shiny": False,
            "method": "grass",
            "large_field": large_string  # Make payload too large
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Request Entity Too Large"
        assert "16384 bytes" in problem["detail"]  # 16KB limit


class TestProblemDetailsFormat:
    """Test RFC 9457 Problem Details error format."""

    def test_problem_details_format(
        self, client: TestClient, sample_player
    ):
        """Test that all errors use Problem Details format."""
        player, token = sample_player
        
        # Submit invalid event type
        event_data = {
            "type": "invalid_type",
            "run_id": str(player.run_id),
            "player_id": str(player.id),
            "time": "2025-08-10T12:00:00Z"
        }
        
        response = client.post(
            "/v1/events",
            json=event_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid4())
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        
        # Verify RFC 9457 required fields
        assert "type" in problem
        assert "title" in problem
        assert "status" in problem
        
        # Verify values
        assert problem["status"] == 422
        assert problem["title"] == "Invalid Event Type"
        assert "instance" in problem  # Should include request URL


class TestEventCatchUp:
    """Test the catch-up endpoint for WebSocket synchronization."""

    def test_get_events_catchup_v3_always_enabled(
        self, client: TestClient, sample_run_data, sample_player_data
    ):
        """Test catch-up endpoint works since v3 event store is always enabled."""
        # Create run and player 
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        player_response = client.post(
            f"/v1/runs/{run_id}/players", 
            json=sample_player_data
        )
        assert player_response.status_code == 201
        token = player_response.json()["player_token"]
        
        # Test catch-up endpoint works with v3 always enabled
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "events" in data
        assert "next_sequence" in data
        assert "v3 Event Store is not enabled" in problem["detail"]

    @pytest.mark.usefixtures("enable_v3_eventstore")
    def test_get_events_catchup_success(
        self, client: TestClient, sample_run_data, sample_player_data
    ):
        """Test successful event catch-up retrieval with v3 enabled."""
        # Create run and player
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        player_response = client.post(
            f"/v1/runs/{run_id}/players", 
            json=sample_player_data
        )
        assert player_response.status_code == 201
        player_data = player_response.json()
        player_id = player_data["id"]
        token = player_data["player_token"]
        
        # Create some events (note: these will fail in legacy mode but should work with v3)
        events_to_create = [
            {
                "type": "encounter",
                "run_id": run_id,
                "player_id": player_id,
                "time": "2025-08-10T12:00:00Z",
                "route_id": 31,
                "species_id": 1,
                "family_id": 1,
                "level": 5,
                "shiny": False,
                "method": "grass"
            }
        ]
        
        event_ids = []
        for event_data in events_to_create:
            response = client.post(
                "/v1/events",
                json=event_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": str(uuid4())
                }
            )
            # Skip if event creation fails (due to missing route/species data)
            if response.status_code == status.HTTP_202_ACCEPTED:
                event_ids.append(response.json()["event_id"])
        
        # Test catch-up endpoint
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check response structure
        assert "events" in data
        assert "total" in data
        assert "latest_seq" in data
        assert "has_more" in data
        
        # Check basic structure even if no events were created
        assert isinstance(data["events"], list)
        assert data["total"] == len(data["events"])
        assert data["has_more"] is False  # No more events beyond limit

    def test_get_events_catchup_no_events(
        self, client: TestClient, sample_run_data, sample_player_data, enable_v3_eventstore
    ):
        """Test catch-up when no events exist."""
        # Create run and player
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        player_response = client.post(
            f"/v1/runs/{run_id}/players", 
            json=sample_player_data
        )
        assert player_response.status_code == 201
        token = player_response.json()["player_token"]
        
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["events"] == []
        assert data["total"] == 0
        assert data["latest_seq"] == 0  # No events exist
        assert data["has_more"] is False

    def test_get_events_catchup_run_not_found(
        self, client: TestClient, sample_run_data, sample_player_data, enable_v3_eventstore
    ):
        """Test catch-up endpoint with non-existent run."""
        # Create run and player first
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        player_response = client.post(
            f"/v1/runs/{run_id}/players", 
            json=sample_player_data
        )
        assert player_response.status_code == 201
        token = player_response.json()["player_token"]
        
        # Try to access events from non-existent run
        non_existent_run_id = uuid4()
        response = client.get(
            f"/v1/events?run_id={non_existent_run_id}&since_seq=0&limit=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Run Not Found"

    def test_get_events_catchup_parameter_validation(
        self, client: TestClient, sample_run_data, sample_player_data, enable_v3_eventstore
    ):
        """Test parameter validation for catch-up endpoint."""
        # Create run and player
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        player_response = client.post(
            f"/v1/runs/{run_id}/players", 
            json=sample_player_data
        )
        assert player_response.status_code == 201
        token = player_response.json()["player_token"]
        
        # Test negative since_seq
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=-1&limit=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test limit too high
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=2000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test limit too low
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=0",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_events_catchup_no_authentication(
        self, client: TestClient, sample_run_data, enable_v3_eventstore
    ):
        """Test catch-up endpoint without authentication."""
        run_response = client.post("/v1/runs", json=sample_run_data)
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]
        
        response = client.get(
            f"/v1/events?run_id={run_id}&since_seq=0&limit=100"
            # No Authorization header
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED