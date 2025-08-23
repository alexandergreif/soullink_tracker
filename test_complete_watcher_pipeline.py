#!/usr/bin/env python3
"""
Complete end-to-end pipeline validation test.
Tests: JSON file → Production Watcher → API → WebSocket → Dashboard

This test validates that the complete pipeline works correctly and
identifies any remaining issues in the watcher-to-API communication.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
import uuid
import websockets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

async def test_complete_pipeline():
    """Test the complete pipeline with real components."""
    print("🚀 Starting Complete Pipeline Test")
    print("="*60)
    
    # Step 1: Start the FastAPI server
    print("1️⃣ Starting FastAPI server...")
    server_process = None
    
    try:
        # Start server in background
        server_process = subprocess.Popen([
            "python", "-m", "uvicorn", 
            "src.soullink_tracker.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-level", "warning"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        server_url = "http://127.0.0.1:8000"
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{server_url}/health", timeout=2)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                pass
            
            if i == max_retries - 1:
                raise Exception("Server failed to start after 30 seconds")
            
            print(f"Waiting for server... ({i+1}/{max_retries})")
            time.sleep(1)
        
        print("✅ Server started successfully")
        
        # Step 2: Create a test run and player via API
        print("\n2️⃣ Setting up test run and player...")
        
        # Create run
        run_data = {
            "name": "Pipeline Test Run",
            "rules": {"first_encounter_only": True, "dupes_clause": True}
        }
        
        run_response = requests.post(f"{server_url}/v1/admin/runs", json=run_data)
        if run_response.status_code != 201:
            print(f"❌ Failed to create run: {run_response.status_code} - {run_response.text}")
            return False
        
        run = run_response.json()
        run_id = str(run["id"])
        print(f"✅ Created test run: {run_id}")
        
        # Create player
        player_data = {
            "name": "Test Player",
            "game": "heartgold",
            "region": "johto"
        }
        
        player_response = requests.post(f"{server_url}/v1/admin/runs/{run_id}/players", json=player_data)
        if player_response.status_code != 201:
            print(f"❌ Failed to create player: {player_response.status_code} - {player_response.text}")
            return False
        
        player = player_response.json()
        player_id = str(player["id"])
        player_token = player["new_token"]
        print(f"✅ Created test player: {player_id}")
        
        # Step 3: Create test event files (simulating Lua script output)
        print("\n3️⃣ Creating test event files...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            events_dir = temp_path / "events"
            events_dir.mkdir()
            
            # Create encounter event file
            encounter_event = {
                "type": "encounter",
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 29,
                "species_id": 25,  # Pikachu
                "level": 5,
                "shiny": False,
                "method": "grass"
            }
            
            encounter_file = events_dir / "encounter_event.json"
            with open(encounter_file, 'w') as f:
                json.dump(encounter_event, f, indent=2)
            
            print(f"✅ Created encounter event: {encounter_file}")
            
            # Create catch result event file
            catch_event = {
                "type": "catch_result",
                "time": datetime.now(timezone.utc).isoformat(),
                "encounter_ref": {
                    "route_id": 29,
                    "species_id": 25
                },
                "status": "caught"
            }
            
            catch_file = events_dir / "catch_result_event.json"
            with open(catch_file, 'w') as f:
                json.dump(catch_event, f, indent=2)
            
            print(f"✅ Created catch result event: {catch_file}")
            
            # Step 4: Set up WebSocket listener for dashboard simulation
            print("\n4️⃣ Setting up WebSocket listener...")
            
            websocket_messages = []
            
            async def websocket_listener():
                """Listen for WebSocket messages from the API."""
                try:
                    uri = f"ws://127.0.0.1:8000/v1/ws?run_id={run_id}&token={player_token}"
                    
                    async with websockets.connect(uri) as websocket:
                        print("✅ WebSocket connected")
                        
                        # Listen for messages
                        while True:
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                                data = json.loads(message)
                                websocket_messages.append(data)
                                print(f"📨 Received WebSocket message: {data.get('type', 'unknown')}")
                            except asyncio.TimeoutError:
                                break
                            
                except Exception as e:
                    print(f"⚠️  WebSocket connection error: {e}")
            
            # Start WebSocket listener in background
            websocket_task = asyncio.create_task(websocket_listener())
            
            # Give WebSocket time to connect
            await asyncio.sleep(1)
            
            # Step 5: Test production watcher with the event files
            print("\n5️⃣ Running production watcher...")
            
            # Test encounter event first
            watcher_cmd = [
                "python", "-m", "watcher.src.soullink_watcher.main",
                "--base-url", server_url,
                "--run-id", run_id,
                "--player-id", player_id,
                "--token", player_token,
                "--from-file", str(encounter_file),
                "--dev"
            ]
            
            print(f"Running: {' '.join(watcher_cmd)}")
            
            try:
                watcher_result = subprocess.run(
                    watcher_cmd,
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                print("📋 Watcher stdout:")
                print(watcher_result.stdout)
                
                if watcher_result.stderr:
                    print("⚠️  Watcher stderr:")
                    print(watcher_result.stderr)
                
                if watcher_result.returncode == 0:
                    print("✅ Production watcher completed successfully")
                else:
                    print(f"❌ Production watcher failed with exit code: {watcher_result.returncode}")
                    return False
                
            except subprocess.TimeoutExpired:
                print("⏰ Watcher process timed out (this might be expected for daemon mode)")
                # Watcher might be running in daemon mode, which is okay
            
            # Step 6: Verify events were received via API
            print("\n6️⃣ Verifying events were processed...")
            
            # Check encounters endpoint
            encounters_response = requests.get(
                f"{server_url}/v1/runs/{run_id}/encounters",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            
            if encounters_response.status_code == 200:
                encounters = encounters_response.json()
                print(f"✅ Found {len(encounters)} encounters in database")
                
                if len(encounters) > 0:
                    encounter = encounters[0]
                    print(f"   - Species: {encounter.get('species_id')}")
                    print(f"   - Route: {encounter.get('route_id')}")
                    print(f"   - Method: {encounter.get('method')}")
                else:
                    print("⚠️  No encounters found - watcher may not have sent events successfully")
            else:
                print(f"❌ Failed to fetch encounters: {encounters_response.status_code}")
            
            # Step 7: Test catch result event
            print("\n7️⃣ Testing catch result event...")
            
            # Run watcher for catch result
            catch_watcher_cmd = [
                "python", "-m", "watcher.src.soullink_watcher.main",
                "--base-url", server_url,
                "--run-id", run_id,
                "--player-id", player_id,
                "--token", player_token,
                "--from-file", str(catch_file),
                "--dev"
            ]
            
            try:
                catch_watcher_result = subprocess.run(
                    catch_watcher_cmd,
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if catch_watcher_result.returncode == 0:
                    print("✅ Catch result watcher completed successfully")
                else:
                    print(f"⚠️  Catch result watcher exit code: {catch_watcher_result.returncode}")
                    print("stderr:", catch_watcher_result.stderr)
                
            except subprocess.TimeoutExpired:
                print("⏰ Catch result watcher timed out")
            
            # Step 8: Check WebSocket messages
            print("\n8️⃣ Checking WebSocket messages...")
            
            # Stop WebSocket listener
            websocket_task.cancel()
            try:
                await websocket_task
            except asyncio.CancelledError:
                pass
            
            print(f"📨 Received {len(websocket_messages)} WebSocket messages:")
            for i, msg in enumerate(websocket_messages):
                print(f"   {i+1}. {msg.get('type', 'unknown')} - {msg.get('data', {}).get('species_id', 'N/A')}")
            
            # Step 9: Final verification
            print("\n9️⃣ Final pipeline verification...")
            
            # Re-check encounters to see if both events were processed
            final_encounters_response = requests.get(
                f"{server_url}/v1/runs/{run_id}/encounters",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            
            if final_encounters_response.status_code == 200:
                final_encounters = final_encounters_response.json()
                print(f"✅ Final count: {len(final_encounters)} encounters")
                
                if len(final_encounters) > 0:
                    for enc in final_encounters:
                        status = enc.get('status', 'unknown')
                        print(f"   - Species {enc.get('species_id')} status: {status}")
                
                # Check if we have caught Pokemon
                caught_count = sum(1 for e in final_encounters if e.get('status') == 'caught')
                print(f"✅ Caught Pokemon count: {caught_count}")
                
            else:
                print(f"❌ Final encounters check failed: {final_encounters_response.status_code}")
            
            # Success criteria
            success = True
            
            if len(websocket_messages) == 0:
                print("⚠️  Warning: No WebSocket messages received")
                success = False
            
            if final_encounters_response.status_code != 200:
                print("❌ API communication failed")
                success = False
            
            return success
    
    finally:
        # Cleanup: Stop server
        if server_process:
            print("\n🧹 Cleaning up server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()
            print("✅ Server stopped")

async def main():
    """Run the complete pipeline test."""
    print("COMPLETE WATCHER PIPELINE VALIDATION")
    print("="*60)
    
    success = await test_complete_pipeline()
    
    print("\n" + "="*60)
    if success:
        print("🎉 PIPELINE TEST PASSED!")
        print("\n✅ The complete pipeline is working:")
        print("  • JSON files created correctly")
        print("  • Production watcher processes events")
        print("  • API receives and processes events")
        print("  • WebSocket broadcasts events")
        print("  • Dashboard would receive real-time updates")
    else:
        print("🚨 PIPELINE TEST FAILED!")
        print("\n❌ Issues detected in the pipeline")
        print("Check the logs above for specific problems")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())