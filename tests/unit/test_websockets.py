"""Unit tests for WebSocket real-time updates."""

import pytest
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from soullink_tracker.events.websocket_manager import WebSocketManager
from soullink_tracker.events.schemas import (
    WebSocketMessage, EncounterEventMessage, CatchResultEventMessage, 
    FaintEventMessage, AdminOverrideEventMessage
)
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus


@pytest.mark.unit
@pytest.mark.asyncio
class TestWebSocketManager:
    """Test the WebSocket connection manager."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WebSocketManager()
        self.run_id = uuid4()
        self.player_id = uuid4()

    async def test_websocket_manager_creation(self):
        """Test creating a WebSocket manager."""
        assert self.manager is not None
        assert len(self.manager.active_connections) == 0

    async def test_connect_websocket(self):
        """Test connecting a WebSocket."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        
        await self.manager.connect(websocket, self.run_id)
        
        websocket.accept.assert_called_once()
        assert self.run_id in self.manager.active_connections
        assert websocket in self.manager.active_connections[self.run_id]

    async def test_disconnect_websocket(self):
        """Test disconnecting a WebSocket."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        
        # Connect first
        await self.manager.connect(websocket, self.run_id)
        assert websocket in self.manager.active_connections[self.run_id]
        
        # Then disconnect
        self.manager.disconnect(websocket, self.run_id)
        # After disconnecting the last connection, the run_id is removed entirely
        assert self.run_id not in self.manager.active_connections or websocket not in self.manager.active_connections[self.run_id]

    async def test_disconnect_nonexistent_websocket(self):
        """Test disconnecting a non-existent WebSocket."""
        websocket = AsyncMock()
        
        # Should not raise an error
        self.manager.disconnect(websocket, self.run_id)

    async def test_broadcast_to_run_single_connection(self):
        """Test broadcasting message to a single connection."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        
        await self.manager.connect(websocket, self.run_id)
        
        message = WebSocketMessage(
            type="encounter",
            data={"test": "data"}
        )
        
        await self.manager.broadcast_to_run(self.run_id, message)
        
        expected_json = message.json()
        websocket.send_text.assert_called_once_with(expected_json)

    async def test_broadcast_to_run_multiple_connections(self):
        """Test broadcasting message to multiple connections."""
        websocket1 = AsyncMock()
        websocket2 = AsyncMock()
        
        for ws in [websocket1, websocket2]:
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            await self.manager.connect(ws, self.run_id)
        
        message = WebSocketMessage(
            type="encounter",
            data={"test": "data"}
        )
        
        await self.manager.broadcast_to_run(self.run_id, message)
        
        expected_json = message.json()
        websocket1.send_text.assert_called_once_with(expected_json)
        websocket2.send_text.assert_called_once_with(expected_json)

    async def test_broadcast_to_nonexistent_run(self):
        """Test broadcasting to a run with no connections."""
        nonexistent_run_id = uuid4()
        
        message = WebSocketMessage(
            type="encounter",
            data={"test": "data"}
        )
        
        # Should not raise an error
        await self.manager.broadcast_to_run(nonexistent_run_id, message)

    async def test_broadcast_handles_connection_error(self):
        """Test broadcasting handles connection errors gracefully."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock(side_effect=Exception("Connection closed"))
        
        await self.manager.connect(websocket, self.run_id)
        
        message = WebSocketMessage(
            type="encounter", 
            data={"test": "data"}
        )
        
        # Should not raise an error
        await self.manager.broadcast_to_run(self.run_id, message)
        
        # Connection should be removed after error (run_id may be removed entirely)
        assert self.run_id not in self.manager.active_connections or websocket not in self.manager.active_connections[self.run_id]

    async def test_get_connection_count(self):
        """Test getting connection count for a run."""
        websocket1 = AsyncMock()
        websocket2 = AsyncMock()
        
        for ws in [websocket1, websocket2]:
            ws.accept = AsyncMock()
            await self.manager.connect(ws, self.run_id)
        
        count = self.manager.get_connection_count(self.run_id)
        assert count == 2
        
        # Test nonexistent run
        count = self.manager.get_connection_count(uuid4())
        assert count == 0


@pytest.mark.unit
class TestWebSocketMessageSchemas:
    """Test WebSocket message schemas."""

    def test_websocket_message_creation(self):
        """Test creating a WebSocket message."""
        message = WebSocketMessage(
            type="encounter",
            data={"species_id": 1, "level": 5}
        )
        
        assert message.type == "encounter"
        assert message.data["species_id"] == 1
        assert message.timestamp is not None

    def test_encounter_event_message(self):
        """Test encounter event message schema."""
        message = EncounterEventMessage(
            run_id=uuid4(),
            player_id=uuid4(),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER
        )
        
        assert message.type == "encounter"
        assert message.data["route_id"] == 31
        assert message.data["species_id"] == 1
        assert message.data["method"] == "grass"

    def test_catch_result_event_message(self):
        """Test catch result event message schema."""
        message = CatchResultEventMessage(
            run_id=uuid4(),
            player_id=uuid4(),
            encounter_ref={"route_id": 31, "species_id": 1},
            status="caught"
        )
        
        assert message.type == "catch_result"
        assert message.data["encounter_ref"]["route_id"] == 31
        assert message.data["status"] == "caught"

    def test_faint_event_message(self):
        """Test faint event message schema."""
        message = FaintEventMessage(
            run_id=uuid4(),
            player_id=uuid4(),
            pokemon_key="personality_123",
            party_index=2
        )
        
        assert message.type == "faint"
        assert message.data["pokemon_key"] == "personality_123"
        assert message.data["party_index"] == 2

    def test_admin_override_event_message(self):
        """Test admin override event message schema."""
        message = AdminOverrideEventMessage(
            run_id=uuid4(),
            action="manual_link_creation",
            details={"route_id": 31, "player_ids": ["uuid1", "uuid2"]}
        )
        
        assert message.type == "admin_override"
        assert message.data["action"] == "manual_link_creation"
        assert message.data["details"]["route_id"] == 31

    def test_message_serialization(self):
        """Test message can be serialized to JSON."""
        message = EncounterEventMessage(
            run_id=uuid4(),
            player_id=uuid4(),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER
        )
        
        json_str = message.json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "encounter"
        assert parsed["data"]["route_id"] == 31


@pytest.mark.unit
@pytest.mark.asyncio
class TestWebSocketIntegration:
    """Test WebSocket integration with event processing."""

    def setup_method(self):
        """Set up test data."""
        self.manager = WebSocketManager()
        self.run_id = uuid4()

    async def test_event_triggers_websocket_broadcast(self):
        """Test that processing an event triggers WebSocket broadcast."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        
        await self.manager.connect(websocket, self.run_id)
        
        # Simulate an encounter event being processed
        from soullink_tracker.events.websocket_manager import broadcast_encounter_event
        
        await broadcast_encounter_event(
            manager=self.manager,
            run_id=self.run_id,
            player_id=uuid4(),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER
        )
        
        # Verify WebSocket was called
        websocket.send_text.assert_called_once()
        
        # Verify message format
        call_args = websocket.send_text.call_args[0][0]
        message_data = json.loads(call_args)
        
        assert message_data["type"] == "encounter"
        assert message_data["data"]["route_id"] == 31
        assert message_data["data"]["species_id"] == 1

    async def test_multiple_event_types_broadcast(self):
        """Test that different event types can be broadcast."""
        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        
        await self.manager.connect(websocket, self.run_id)
        
        from soullink_tracker.events.websocket_manager import (
            broadcast_encounter_event, broadcast_catch_result_event, broadcast_faint_event
        )
        
        # Test encounter event
        await broadcast_encounter_event(
            manager=self.manager,
            run_id=self.run_id,
            player_id=uuid4(),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            status=EncounterStatus.FIRST_ENCOUNTER
        )
        
        # Test catch result event
        await broadcast_catch_result_event(
            manager=self.manager,
            run_id=self.run_id,
            player_id=uuid4(),
            encounter_ref={"route_id": 31, "species_id": 1},
            status="caught"
        )
        
        # Test faint event
        await broadcast_faint_event(
            manager=self.manager,
            run_id=self.run_id,
            player_id=uuid4(),
            pokemon_key="personality_123",
            party_index=2
        )
        
        # Should have been called 3 times
        assert websocket.send_text.call_count == 3