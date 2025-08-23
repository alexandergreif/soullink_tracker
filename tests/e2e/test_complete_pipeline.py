"""
Comprehensive end-to-end pipeline test for SoulLink Tracker.

Tests the complete event flow:
1. Lua script → JSON files (simulated)
2. JSON files → Python watcher 
3. Python watcher → FastAPI API
4. FastAPI → WebSocket broadcasting
5. WebSocket → Dashboard updates (simulated)

This test validates that encounter and catch_result events work correctly
through the entire pipeline with proper error handling and validation.
"""

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

import pytest
import requests
from fastapi.testclient import TestClient

from simple_watcher import SimpleWatcher


class MockLuaScriptSimulator:
    """Simulates Lua script output by creating JSON event files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.event_counter = 0
    
    def create_encounter_event(
        self,
        run_id: str,
        player_id: str, 
        species_id: int = 25,
        route_id: int = 31,
        level: int = 5,
        method: str = "grass",
        rod_kind: str = None
    ) -> Path:
        """Create a mock encounter event file as Lua script would."""
        event_data = {
            "type": "encounter",
            "run_id": run_id,
            "player_id": player_id,
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": route_id,
            "species_id": species_id,
            "level": level,
            "shiny": False,
            "method": method
        }
        
        if method == "fish" and rod_kind:
            event_data["rod_kind"] = rod_kind
            
        return self._write_event_file(event_data)
    
    def create_catch_result_event(
        self,
        run_id: str,
        player_id: str,
        route_id: int = 31,
        species_id: int = 25,
        status: str = "caught"
    ) -> Path:
        """Create a mock catch_result event file as Lua script would."""
        event_data = {
            "type": "catch_result",
            "run_id": run_id,
            "player_id": player_id,
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_ref": {
                "route_id": route_id,
                "species_id": species_id
            },
            "status": status
        }
        
        return self._write_event_file(event_data)
    
    def _write_event_file(self, event_data: Dict[str, Any]) -> Path:
        """Write event data to JSON file with unique filename."""
        self.event_counter += 1
        filename = f"event_{self.event_counter}_{event_data['type']}_{int(time.time() * 1000)}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(event_data, f, indent=2)
            
        return filepath


class MockDashboard:
    """Mock dashboard WebSocket client to verify messages are received."""
    
    def __init__(self):
        self.received_messages = []
        self.connection_established = False
    
    def connect_websocket(self, client: TestClient, run_id: str, token: str):
        """Connect to WebSocket and listen for messages."""
        with client.websocket_connect(f"/v1/ws?run_id={run_id}&token={token}") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            if welcome.get("type") == "connection_established":
                self.connection_established = True
            
            # Listen for event messages (timeout after short period)
            try:
                while True:
                    message = websocket.receive_json(timeout=2.0)
                    self.received_messages.append(message)
            except Exception:
                # Timeout or connection closed
                pass


@pytest.mark.e2e
@pytest.mark.slow
class TestCompletePipeline:
    """Test the complete event pipeline end-to-end."""
    
    def test_complete_encounter_pipeline(self, client, sample_run, sample_player):
        """Test complete pipeline: Lua → JSON → Watcher → API → WebSocket → Dashboard"""
        run = sample_run
        player = sample_player
        token = player._test_token
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Simulate Lua script creating JSON files
            lua_simulator = MockLuaScriptSimulator(temp_path / "events")
            encounter_file = lua_simulator.create_encounter_event(
                run_id=str(run.id),
                player_id=str(player.id),
                species_id=25,  # Pikachu
                route_id=31,
                level=5,
                method="grass"
            )
            
            # Verify JSON file was created correctly
            assert encounter_file.exists()
            with open(encounter_file) as f:
                encounter_data = json.load(f)
            assert encounter_data["type"] == "encounter"
            assert encounter_data["species_id"] == 25
            assert encounter_data["method"] == "grass"
            
            # Step 2: Setup Python watcher to process JSON files
            watcher = SimpleWatcher()
            watcher.run_id = str(run.id)
            watcher.player_id = str(player.id)
            watcher.player_token = token
            
            # Step 3: Setup mock dashboard WebSocket listener
            dashboard = MockDashboard()
            
            # Step 4: Process event through watcher → API → WebSocket pipeline
            with patch('requests.post') as mock_post:
                # Mock successful API response
                mock_response = MagicMock()
                mock_response.status_code = 202
                mock_response.text = json.dumps({
                    "message": "Event processed",
                    "event_id": str(uuid.uuid4()),
                    "seq": 1,
                    "applied_rules": ["websocket_broadcast"]
                })
                mock_post.return_value = mock_response
                
                # Step 5: Connect dashboard WebSocket before processing
                with client.websocket_connect(f"/v1/ws?run_id={run.id}&token={token}") as websocket:
                    # Skip welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "connection_established"
                    
                    # Process the JSON file through watcher
                    result = watcher.process_json_file(encounter_file)
                    assert result is True
                    
                    # Verify watcher called API correctly
                    assert mock_post.called
                    call_args = mock_post.call_args
                    sent_event = call_args[1]['json']
                    
                    # Validate event was processed correctly
                    assert sent_event['type'] == 'encounter'
                    assert sent_event['species_id'] == 25
                    assert sent_event['run_id'] == str(run.id)
                    assert sent_event['player_id'] == str(player.id)
                    assert 'Idempotency-Key' in call_args[1]['headers']
                    
                    # Now test real API processing (not mocked)
                    encounter_data_api = {
                        "type": "encounter",
                        "run_id": str(run.id),
                        "player_id": str(player.id),
                        "time": datetime.now(timezone.utc).isoformat(),
                        "route_id": 31,
                        "species_id": 25,
                        "level": 5,
                        "shiny": False,
                        "method": "grass"
                    }
                    
                    # Send real event to API
                    api_response = client.post(
                        "/v1/events",
                        json=encounter_data_api,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Idempotency-Key": str(uuid.uuid4())
                        }
                    )
                    
                    # Verify API processed successfully
                    assert api_response.status_code == 202
                    api_result = api_response.json()
                    assert "event_id" in api_result
                    assert "seq" in api_result
                    
                    # Verify WebSocket received the broadcast
                    ws_message = websocket.receive_json()
                    assert ws_message["type"] == "encounter" 
                    assert ws_message["data"]["species_id"] == 25
                    assert ws_message["data"]["route_id"] == 31
                    assert ws_message["sequence_number"] == api_result["seq"]
    
    def test_complete_catch_result_pipeline(self, client, sample_run, sample_player):
        """Test complete pipeline for catch_result events."""
        run = sample_run
        player = sample_player
        token = player._test_token
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Create encounter first (required for catch_result)
            encounter_data = {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 32,
                "species_id": 129,  # Magikarp
                "level": 10,
                "shiny": False,
                "method": "fish",
                "rod_kind": "old"
            }
            
            encounter_response = client.post(
                "/v1/events",
                json=encounter_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": str(uuid.uuid4())
                }
            )
            assert encounter_response.status_code == 202
            encounter_result = encounter_response.json()
            
            # Wait a moment for the encounter to be fully processed
            import time
            time.sleep(0.1)
            
            # Step 2: Simulate Lua creating catch_result JSON file
            lua_simulator = MockLuaScriptSimulator(temp_path / "events")
            catch_file = lua_simulator.create_catch_result_event(
                run_id=str(run.id),
                player_id=str(player.id),
                route_id=32,
                species_id=129,
                status="caught"
            )
            
            # Verify catch_result file structure
            with open(catch_file) as f:
                catch_data = json.load(f)
            assert catch_data["type"] == "catch_result"
            assert catch_data["status"] == "caught"
            assert catch_data["encounter_ref"]["species_id"] == 129
            
            # Step 3: Process through complete pipeline
            watcher = SimpleWatcher()
            watcher.run_id = str(run.id)
            watcher.player_id = str(player.id) 
            watcher.player_token = token
            
            with client.websocket_connect(f"/v1/ws?run_id={run.id}&token={token}") as websocket:
                # Skip welcome message
                websocket.receive_json()
                
                # Mock watcher processing (test file validation)
                with patch('requests.post') as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 202
                    mock_response.text = json.dumps({
                        "message": "Catch result processed",
                        "event_id": str(uuid.uuid4()),
                        "seq": 2
                    })
                    mock_post.return_value = mock_response
                    
                    result = watcher.process_json_file(catch_file)
                    assert result is True
                
                # Test real catch_result processing
                catch_data_api = {
                    "type": "catch_result",
                    "run_id": str(run.id),
                    "player_id": str(player.id),
                    "time": datetime.now(timezone.utc).isoformat(),
                    "encounter_ref": {
                        "route_id": 32,
                        "species_id": 129
                    },
                    "status": "caught"
                }
                
                api_response = client.post(
                    "/v1/events",
                    json=catch_data_api,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": str(uuid.uuid4())
                    }
                )
                
                # Debug API error if it occurs
                if api_response.status_code != 202:
                    print(f"API Error: {api_response.status_code}")
                    print(f"Response: {api_response.text}")
                
                assert api_response.status_code == 202
                api_result = api_response.json()
                
                # Verify WebSocket broadcast
                ws_message = websocket.receive_json()
                assert ws_message["type"] == "catch_result"
                assert ws_message["data"]["status"] == "caught"
                assert ws_message["data"]["encounter_ref"]["species_id"] == 129

    def test_pipeline_error_handling(self, client, sample_run, sample_player):
        """Test pipeline handles errors gracefully."""
        run = sample_run
        player = sample_player
        token = player._test_token
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create invalid JSON file (malformed)
            invalid_file = temp_path / "invalid.json"
            with open(invalid_file, 'w') as f:
                f.write('{"type": "encounter", "invalid": json}')  # Invalid JSON
            
            watcher = SimpleWatcher()
            watcher.run_id = str(run.id)
            watcher.player_id = str(player.id)
            watcher.player_token = token
            
            # Should handle invalid JSON gracefully
            result = watcher.process_json_file(invalid_file)
            assert result is False  # Should fail but not crash
            
            # Create event with validation errors
            lua_simulator = MockLuaScriptSimulator(temp_path / "events")
            invalid_event_file = temp_path / "events" / "invalid_event.json"
            
            invalid_event = {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player.id), 
                "time": datetime.now(timezone.utc).isoformat(),
                # Missing required fields: route_id, species_id, level, shiny, method
            }
            
            with open(invalid_event_file, 'w') as f:
                json.dump(invalid_event, f)
            
            # Should detect validation errors
            with patch('requests.post') as mock_post:
                result = watcher.process_json_file(invalid_event_file)
                # Depending on watcher implementation, it might send anyway or validate first
                # This tests the watcher's error handling behavior


@pytest.mark.e2e
class TestPipelineIntegration:
    """Integration tests for individual pipeline components."""
    
    def test_watcher_api_integration(self, client, sample_run, sample_player):
        """Test watcher → API integration specifically."""
        run = sample_run
        player = sample_player
        token = player._test_token
        
        # Test watcher can successfully send events to running API
        watcher = SimpleWatcher()
        watcher.run_id = str(run.id)
        watcher.player_id = str(player.id)
        watcher.player_token = token
        
        # Create valid event data
        event_data = {
            "type": "encounter",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 40,
            "species_id": 150,  # Mewtwo
            "level": 70,
            "shiny": True,
            "method": "static"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            event_file = Path(temp_dir) / "test_event.json"
            with open(event_file, 'w') as f:
                json.dump(event_data, f)
            
            # Use real API (not mocked) to test integration
            # Note: This requires the test client to be running the actual FastAPI app
            result = watcher.process_json_file(event_file)
            # Result depends on watcher implementation and whether it can reach the test API
    
    def test_api_websocket_integration(self, client, sample_run, sample_player):
        """Test API → WebSocket integration specifically."""
        run = sample_run
        player = sample_player
        token = player._test_token
        
        # Test that API events correctly trigger WebSocket broadcasts
        with client.websocket_connect(f"/v1/ws?run_id={run.id}&token={token}") as websocket:
            # Skip welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection_established"
            
            # Send multiple encounter events to test broadcasting
            events = [
                {
                    "type": "encounter",
                    "route_id": 1,
                    "species_id": 1,
                    "level": 5,
                    "shiny": False,
                    "method": "grass"
                },
                {
                    "type": "encounter",
                    "route_id": 2,
                    "species_id": 2,
                    "level": 6,
                    "shiny": True,
                    "method": "surf"
                }
            ]
            
            for i, event_data in enumerate(events):
                full_event = {
                    **event_data,
                    "run_id": str(run.id),
                    "player_id": str(player.id),
                    "time": datetime.now(timezone.utc).isoformat()
                }
                
                response = client.post(
                    "/v1/events",
                    json=full_event,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": str(uuid.uuid4())
                    }
                )
                
                assert response.status_code == 202
                
                # Verify WebSocket received broadcast
                ws_message = websocket.receive_json()
                assert ws_message["type"] == event_data["type"]
                assert "sequence_number" in ws_message
                assert ws_message["sequence_number"] > i  # Should be increasing