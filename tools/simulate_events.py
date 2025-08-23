#!/usr/bin/env python3
"""
Event Pipeline Simulator for SoulLink Tracker

This tool simulates the complete event flow pipeline:
1. Generate JSON files (as Lua script would)
2. Monitor and process them with watcher
3. Send to API endpoint 
4. Monitor WebSocket broadcasts
5. Validate complete pipeline

Usage:
  python tools/simulate_events.py --mode full    # Complete pipeline test
  python tools/simulate_events.py --mode events  # Just generate test events  
  python tools/simulate_events.py --mode watch   # Monitor WebSocket
"""

import json
import argparse
import asyncio
import time
import uuid
import tempfile
import websockets
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import requests
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_watcher import SimpleWatcher


class EventSimulator:
    """Simulates Lua script generating event JSON files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.event_counter = 0
        
    def generate_encounter_scenario(self, run_id: str, player_id: str) -> List[Path]:
        """Generate a realistic encounter scenario with multiple events."""
        scenarios = [
            # Grass encounter - caught
            {
                "encounter": {
                    "species_id": 25, "route_id": 31, "level": 5, "method": "grass"
                },
                "result": {"status": "caught"}
            },
            # Surf encounter - fled  
            {
                "encounter": {
                    "species_id": 54, "route_id": 40, "level": 20, "method": "surf"  
                },
                "result": {"status": "fled"}
            },
            # Fishing encounter - caught
            {
                "encounter": {
                    "species_id": 129, "route_id": 32, "level": 10, "method": "fish", 
                    "rod_kind": "old"
                },
                "result": {"status": "caught"}
            },
            # Shiny static encounter - caught
            {
                "encounter": {
                    "species_id": 144, "route_id": 1, "level": 50, "method": "static",
                    "shiny": True
                },
                "result": {"status": "caught"}
            },
        ]
        
        generated_files = []
        
        for scenario in scenarios:
            # Generate encounter event
            encounter_data = {
                "type": "encounter",
                "run_id": run_id,
                "player_id": player_id,
                "time": datetime.now(timezone.utc).isoformat(),
                **scenario["encounter"]
            }
            
            # Set shiny flag if not specified
            if "shiny" not in encounter_data:
                encounter_data["shiny"] = False
                
            encounter_file = self._write_event(encounter_data)
            generated_files.append(encounter_file)
            
            # Small delay to ensure different timestamps
            time.sleep(0.1)
            
            # Generate corresponding catch result
            result_data = {
                "type": "catch_result", 
                "run_id": run_id,
                "player_id": player_id,
                "time": datetime.now(timezone.utc).isoformat(),
                "encounter_ref": {
                    "route_id": scenario["encounter"]["route_id"],
                    "species_id": scenario["encounter"]["species_id"]
                },
                **scenario["result"]
            }
            
            result_file = self._write_event(result_data)
            generated_files.append(result_file)
            
            time.sleep(0.1)
            
        return generated_files
        
    def _write_event(self, event_data: Dict[str, Any]) -> Path:
        """Write event data to JSON file."""
        self.event_counter += 1
        timestamp = int(time.time() * 1000)
        filename = f"event_{self.event_counter:03d}_{event_data['type']}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(event_data, f, indent=2)
            
        print(f"=Ä Generated: {filename}")
        return filepath


class WebSocketMonitor:
    """Monitors WebSocket broadcasts during testing."""
    
    def __init__(self):
        self.messages_received = []
        self.connection_established = False
        
    async def monitor_websocket(self, ws_url: str, timeout: float = 30.0):
        """Connect to WebSocket and monitor messages."""
        print(f"= Connecting to WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print(" WebSocket connected successfully")
                
                # Wait for messages with timeout
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(message)
                        self.messages_received.append(data)
                        
                        if data.get("type") == "connection_established":
                            self.connection_established = True
                            print("> WebSocket connection established")
                        else:
                            print(f"=è Received: {data.get('type', 'unknown')} - seq:{data.get('sequence_number', 'N/A')}")
                            
                    except asyncio.TimeoutError:
                        # No message received, continue monitoring
                        continue
                        
        except Exception as e:
            print(f"L WebSocket error: {e}")
            return False
            
        return True


class PipelineValidator:
    """Validates the complete event pipeline."""
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8000"):
        self.api_base_url = api_base_url
        self.run_id = None
        self.player_id = None
        self.player_token = None
        
    def setup_test_environment(self) -> bool:
        """Setup test run and player for pipeline testing."""
        try:
            # Get available runs
            response = requests.get(f"{self.api_base_url}/v1/admin/runs", timeout=10)
            if response.status_code != 200:
                print(f"L Failed to fetch runs: {response.status_code}")
                return False
                
            runs = response.json()
            if not runs:
                print("L No runs available for testing")
                return False
                
            # Use first available run
            run = runs[0]
            self.run_id = run["id"]
            print(f"<® Using run: {run['name']} ({self.run_id})")
            
            # Get players for this run
            response = requests.get(f"{self.api_base_url}/v1/admin/runs/{self.run_id}/players")
            if response.status_code != 200:
                print(f"L Failed to fetch players: {response.status_code}")
                return False
                
            players = response.json()
            if not players:
                print("L No players available for testing")
                return False
                
            # Use first available player
            player = players[0] 
            self.player_id = player["id"]
            self.player_token = player.get("token", "test-token")
            print(f"=d Using player: {player['name']} ({self.player_id})")
            
            return True
            
        except Exception as e:
            print(f"L Setup failed: {e}")
            return False
            
    def validate_api_connectivity(self) -> bool:
        """Test basic API connectivity."""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                print(" API server is healthy")
                return True
            else:
                print(f"L API health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"L API connectivity failed: {e}")
            return False


async def run_complete_pipeline_test(api_base_url: str, event_dir: Path):
    """Run the complete pipeline validation test."""
    print("=€ Starting Complete Pipeline Test")
    print("=" * 60)
    
    # Setup validator
    validator = PipelineValidator(api_base_url)
    
    # Step 1: Validate API connectivity
    print("\n=á Step 1: Testing API Connectivity")
    if not validator.validate_api_connectivity():
        return False
        
    # Step 2: Setup test environment
    print("\n=' Step 2: Setting up Test Environment")  
    if not validator.setup_test_environment():
        return False
        
    # Step 3: Generate event files
    print("\n=Ý Step 3: Generating Event Files")
    simulator = EventSimulator(event_dir)
    event_files = simulator.generate_encounter_scenario(
        validator.run_id, validator.player_id
    )
    print(f"Generated {len(event_files)} event files")
    
    # Step 4: Setup WebSocket monitor
    print("\n<§ Step 4: Setting up WebSocket Monitor")
    monitor = WebSocketMonitor()
    ws_url = f"ws://127.0.0.1:8000/v1/ws?run_id={validator.run_id}&token={validator.player_token}"
    
    # Step 5: Start WebSocket monitoring in background
    print("\n= Step 5: Starting Pipeline Processing")
    monitor_task = asyncio.create_task(monitor.monitor_websocket(ws_url, timeout=60))
    
    # Give WebSocket time to connect
    await asyncio.sleep(2)
    
    # Step 6: Process events through watcher
    print("™  Processing events through watcher...")
    watcher = SimpleWatcher() 
    watcher.run_id = validator.run_id
    watcher.player_id = validator.player_id
    watcher.player_token = validator.player_token
    
    processed_count = 0
    failed_count = 0
    
    for event_file in event_files:
        print(f"=ä Processing: {event_file.name}")
        try:
            result = watcher.process_json_file(event_file)
            if result:
                processed_count += 1
                print(f"    Success")
            else:
                failed_count += 1
                print(f"   L Failed")
        except Exception as e:
            failed_count += 1
            print(f"   L Error: {e}")
            
        # Small delay between processing
        await asyncio.sleep(1)
    
    # Step 7: Wait for WebSocket messages
    print("\nó Step 6: Waiting for WebSocket Messages...")
    await asyncio.sleep(5)  # Give time for messages to arrive
    
    # Cancel WebSocket monitor
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
        
    # Step 8: Validate results
    print("\n=Ê Step 7: Validation Results")
    print("=" * 40)
    print(f"Events generated: {len(event_files)}")
    print(f"Events processed: {processed_count}")
    print(f"Events failed: {failed_count}")
    print(f"WebSocket messages: {len(monitor.messages_received)}")
    print(f"Connection established: {monitor.connection_established}")
    
    # Detailed WebSocket message analysis
    if monitor.messages_received:
        print("\n=è WebSocket Messages Received:")
        for i, msg in enumerate(monitor.messages_received):
            msg_type = msg.get("type", "unknown")
            seq = msg.get("sequence_number", "N/A")
            print(f"  {i+1}. {msg_type} (seq: {seq})")
    
    # Determine overall success
    expected_ws_messages = processed_count  # Should get 1 WS message per processed event
    success = (
        processed_count > 0 and
        failed_count == 0 and 
        monitor.connection_established and
        len(monitor.messages_received) >= expected_ws_messages
    )
    
    print(f"\n<Á Pipeline Test: {' PASSED' if success else 'L FAILED'}")
    return success


def main():
    parser = argparse.ArgumentParser(description="SoulLink Event Pipeline Simulator")
    parser.add_argument("--mode", choices=["full", "events", "watch"], 
                       default="full", help="Simulation mode")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000",
                       help="API base URL")
    parser.add_argument("--event-dir", default="C:/temp/soullink_events/",
                       help="Event directory path")
    parser.add_argument("--run-id", help="Specific run ID to use")
    parser.add_argument("--player-id", help="Specific player ID to use") 
    
    args = parser.parse_args()
    
    event_dir = Path(args.event_dir)
    
    if args.mode == "events":
        # Just generate events
        print("=Ý Generating test events...")
        simulator = EventSimulator(event_dir)
        run_id = args.run_id or str(uuid.uuid4())
        player_id = args.player_id or str(uuid.uuid4())
        
        event_files = simulator.generate_encounter_scenario(run_id, player_id)
        print(f" Generated {len(event_files)} event files in {event_dir}")
        
    elif args.mode == "watch":
        # Just monitor WebSocket
        print("<§ Starting WebSocket monitor...")
        monitor = WebSocketMonitor()
        
        # Need run_id and token for WebSocket
        if not args.run_id:
            print("L --run-id required for watch mode")
            return 1
            
        ws_url = f"ws://127.0.0.1:8000/v1/ws?run_id={args.run_id}&token=test-token"
        asyncio.run(monitor.monitor_websocket(ws_url, timeout=300))
        
    else:
        # Full pipeline test
        success = asyncio.run(run_complete_pipeline_test(args.api_url, event_dir))
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())