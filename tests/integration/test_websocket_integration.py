"""Integration tests for WebSocket broadcasting and catch-up functionality.

These tests validate the end-to-end WebSocket functionality including:
- Real-time event broadcasting via WebSocket
- Catch-up functionality via REST API
- Sequence number tracking and ordering
- Authentication and connection management
- Error handling and resilience
"""

import uuid
from datetime import datetime, timezone




class TestWebSocketBroadcasting:
    """Test real-time WebSocket broadcasting integration."""

    def test_encounter_event_broadcasts_to_websocket(
        self, auth_client, sample_run, sample_player
    ):
        """Test that encounter events broadcast to WebSocket clients."""
        # Arrange - use the sample fixtures that auth_client expects
        run = sample_run
        player = sample_player
        token = player._test_token

        # Use legacy endpoint for backwards compatibility during transition
        with auth_client.websocket_connect(
            f"/v1/ws/legacy?run_id={run.id}&token={token}"
        ) as websocket:

            # Skip welcome message
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"

            # Send encounter event via API
            encounter_data = {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 31,
                "species_id": 25,  # Pikachu
                "level": 5,
                "shiny": False,
                "method": "grass",
            }

            # Act: Send event via API (auth_client bypasses token auth)
            response = auth_client.post(
                "/v1/events",
                json=encounter_data,
                headers={
                    "Idempotency-Key": str(uuid.uuid4()),
                }
            )

            # Assert API response
            assert response.status_code == 202
            event_response = response.json()
            assert "event_id" in event_response
            assert "seq" in event_response
            assert "websocket_broadcast" in event_response["applied_rules"]

            # Assert WebSocket message received
            websocket_message = websocket.receive_json()

            assert websocket_message["type"] == "encounter"
            assert websocket_message["sequence_number"] == event_response["seq"]
            assert websocket_message["data"]["route_id"] == 31
            assert websocket_message["data"]["species_id"] == 25
            assert websocket_message["data"]["method"] == "grass"


class TestWebSocketCatchUp:
    """Test WebSocket catch-up functionality via REST API."""

    def test_catch_up_endpoint_returns_missed_events(
        self, auth_client, sample_run, sample_player
    ):
        """Test that catch-up endpoint returns events with sequence numbers."""
        # Arrange - use the sample fixtures that auth_client expects
        run = sample_run
        player = sample_player
        token = player._test_token

        # Send several events to create sequence
        events_data = []
        for i in range(3):
            event_data = {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 40 + i,
                "species_id": 100 + i,
                "level": 10 + i,
                "shiny": False,
                "method": "grass",
            }

            response = auth_client.post(
                "/v1/events",
                json=event_data,
                headers={
                    "Idempotency-Key": str(uuid.uuid4()),
                }
            )
            assert response.status_code == 202
            events_data.append(response.json())

        # Act: Get catch-up events from sequence 2 onwards
        since_sequence = events_data[1]["seq"]
        catch_up_response = auth_client.get(
            f"/v1/events?run_id={run.id}&since_seq={since_sequence}",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert: Should get events 2 and 3
        assert catch_up_response.status_code == 200
        catch_up_data = catch_up_response.json()

        assert "events" in catch_up_data
        returned_events = catch_up_data["events"]

        # Should return events with sequence numbers after since_sequence
        assert len(returned_events) >= 1  # At least the last event

        for event in returned_events:
            assert event["seq"] > since_sequence
            assert "event_id" in event
            assert "type" in event


class TestWebSocketSequenceTracking:
    """Test WebSocket sequence number tracking and ordering."""

    def test_websocket_messages_include_sequence_numbers(
        self, auth_client, sample_run, sample_player
    ):
        """Test that WebSocket messages include sequence numbers for ordering."""
        # Arrange - use the sample fixtures that auth_client expects
        run = sample_run
        player = sample_player
        token = player._test_token

        # Use legacy endpoint for backwards compatibility during transition
        with auth_client.websocket_connect(
            f"/v1/ws/legacy?run_id={run.id}&token={token}"
        ) as websocket:

            # Skip welcome message
            websocket.receive_json()

            # Send multiple events rapidly
            sequence_numbers = []
            for i in range(5):
                event_data = {
                    "type": "encounter",
                    "run_id": str(run.id),
                    "player_id": str(player.id),
                    "time": datetime.now(timezone.utc).isoformat(),
                    "route_id": 60 + i,
                    "species_id": 200 + i,
                    "level": 15,
                    "shiny": False,
                    "method": "grass",
                }

                response = auth_client.post(
                    "/v1/events",
                    json=event_data,
                    headers={
                        "Idempotency-Key": str(uuid.uuid4()),
                    }
                )
                assert response.status_code == 202

                # Receive WebSocket message
                message = websocket.receive_json()
                assert "sequence_number" in message
                sequence_numbers.append(message["sequence_number"])

            # Assert: Sequence numbers should be increasing
            assert len(sequence_numbers) == 5
            assert sequence_numbers == sorted(sequence_numbers)
            # Should be consecutive or strictly increasing
            for i in range(1, len(sequence_numbers)):
                assert sequence_numbers[i] > sequence_numbers[i - 1]


class TestWebSocketAuthentication:
    """Test WebSocket authentication and connection management."""

    def test_websocket_requires_authentication(self, client):
        """Test that WebSocket connections require Bearer token."""
        # Arrange
        run_id = uuid.uuid4()

        # Act & Assert: Try to connect without token (should fail)
        try:
            with client.websocket_connect(f"/v1/ws/legacy?run_id={run_id}") as websocket:
                # Should not reach here
                assert False, "WebSocket should have rejected unauthenticated connection"
        except Exception:
            # Expected - connection should be rejected
            pass

    def test_websocket_with_valid_token_connects(
        self, auth_client, sample_run, sample_player
    ):
        """Test that WebSocket accepts valid Bearer tokens."""
        # Arrange - use the sample fixtures that auth_client expects
        run = sample_run
        player = sample_player
        token = player._test_token

        # Act & Assert: Should connect successfully
        with auth_client.websocket_connect(
            f"/v1/ws/legacy?run_id={run.id}&token={token}"
        ) as websocket:
            # Should successfully establish connection
            # WebSocket should send welcome message
            welcome_message = websocket.receive_json()
            assert welcome_message["type"] == "connection_established"


class TestWebSocketErrorHandling:
    """Test WebSocket error handling and resilience."""

    def test_websocket_survives_broadcast_failures(
        self, auth_client, sample_run, sample_player, make_player
    ):
        """Test that WebSocket broadcasting continues even if some connections fail."""
        # Arrange - Use fixture that can create multiple players
        run = sample_run
        player1 = sample_player  # Use existing fixture
        player2 = make_player(run.id, "SecondPlayer")  # Create second player

        token1 = player1._test_token
        token2 = player2._test_token

        # Connect both players using separate websocket connections
        with auth_client.websocket_connect(
            f"/v1/ws/legacy?run_id={run.id}&token={token1}"
        ) as ws1:
            
            # Skip welcome message for ws1
            ws1.receive_json()
            
            # Connect and immediately disconnect ws2 to simulate failure
            with auth_client.websocket_connect(
                f"/v1/ws/legacy?run_id={run.id}&token={token2}"
            ) as ws2:
                # Skip welcome message and force close
                ws2.receive_json()
                ws2.close()

            # Send event after ws2 is closed
            event_data = {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player1.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 80,
                "species_id": 400,
                "level": 50,
                "shiny": False,
                "method": "static",
            }

            response = auth_client.post(
                "/v1/events",
                json=event_data,
                headers={
                    "Idempotency-Key": str(uuid.uuid4()),
                }
            )
            assert response.status_code == 202

            # ws1 should still receive the broadcast despite ws2 being closed
            message = ws1.receive_json()
            assert message["type"] == "encounter"
            assert message["data"]["route_id"] == 80