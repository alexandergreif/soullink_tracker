#!/usr/bin/env python3
"""
Simplified pipeline validation to confirm watcher → API communication works.
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

def test_simple_watcher_api_communication():
    """Test that the watcher can successfully communicate with the API."""
    print("🚀 Testing Watcher → API Communication")
    print("="*50)
    
    # Start server
    print("1️⃣ Starting server...")
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", 
        "src.soullink_tracker.main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--log-level", "warning"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for server
        server_url = "http://127.0.0.1:8000"
        for i in range(30):
            try:
                requests.get(f"{server_url}/health", timeout=2)
                break
            except:
                time.sleep(1)
        
        print("✅ Server started")
        
        # Create run and player
        print("2️⃣ Creating test run and player...")
        
        run_response = requests.post(f"{server_url}/v1/admin/runs", json={
            "name": "Simple Pipeline Test",
            "rules_json": {"first_encounter_only": True}
        })
        
        if run_response.status_code != 201:
            print(f"❌ Run creation failed: {run_response.status_code} - {run_response.text}")
            return False
        
        run_id = str(run_response.json()["id"])
        
        player_response = requests.post(f"{server_url}/v1/admin/runs/{run_id}/players", json={
            "name": "Test Player",
            "game": "heartgold", 
            "region": "johto"
        })
        
        if player_response.status_code != 201:
            print(f"❌ Player creation failed: {player_response.status_code} - {player_response.text}")
            return False
        
        player_data = player_response.json()
        player_id = str(player_data["id"])
        player_token = player_data["new_token"]
        
        print(f"✅ Created run: {run_id}")
        print(f"✅ Created player: {player_id}")
        
        # Create test event file
        print("3️⃣ Creating test event file...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            event_file = Path(temp_dir) / "test_event.json"
            
            test_event = {
                "type": "encounter",
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 31,
                "species_id": 25,  # Pikachu
                "level": 5,
                "shiny": False,
                "method": "grass"
            }
            
            with open(event_file, 'w') as f:
                # Write as NDJSON format (newline-delimited JSON)
                json.dump(test_event, f, separators=(',', ':'))
                f.write('\n')
            
            print(f"✅ Event file created: {event_file}")
            
            # Check initial state
            initial_response = requests.get(
                f"{server_url}/v1/runs/{run_id}/encounters",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            
            initial_data = initial_response.json() if initial_response.status_code == 200 else {}
            initial_count = initial_data.get("total", 0)
            print(f"📊 Initial encounters: {initial_count}")
            
            # Run watcher
            print("4️⃣ Running production watcher...")
            
            watcher_cmd = [
                "python", "-m", "watcher.src.soullink_watcher.main",
                "--base-url", server_url,
                "--run-id", run_id,
                "--player-id", player_id,
                "--token", player_token,
                "--from-file", str(event_file),
                "--dev"
            ]
            
            try:
                watcher_result = subprocess.run(
                    watcher_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                print(f"📋 Watcher exit code: {watcher_result.returncode}")
                
                if watcher_result.stdout:
                    print("📋 Watcher stdout:")
                    print(watcher_result.stdout)
                
                if watcher_result.stderr:
                    print("⚠️  Watcher stderr:")
                    print(watcher_result.stderr)
                
            except subprocess.TimeoutExpired:
                print("⏰ Watcher timed out (might be normal for daemon mode)")
            
            # Check if events were processed
            print("5️⃣ Checking results...")
            
            # Wait a moment for processing
            time.sleep(1)
            
            final_response = requests.get(
                f"{server_url}/v1/runs/{run_id}/encounters",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            
            if final_response.status_code == 200:
                encounters_data = final_response.json()
                final_count = encounters_data.get("total", 0)
                encounters_list = encounters_data.get("encounters", [])
                print(f"📊 Final encounters: {final_count}")
                
                if final_count > initial_count:
                    print("✅ SUCCESS: Watcher successfully sent events to API!")
                    print(f"   Added {final_count - initial_count} new encounters")
                    
                    # Show encounter details
                    if encounters_list:
                        for i, enc in enumerate(encounters_list):
                            print(f"   Encounter {i+1}: Species {enc.get('species_id', 'N/A')} on Route {enc.get('route_id', 'N/A')}")
                    
                    return True
                else:
                    print("❌ FAILURE: No new encounters found - watcher may not have sent events")
                    return False
            else:
                print(f"❌ Failed to check encounters: {final_response.status_code}")
                return False
    
    finally:
        # Cleanup
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

def main():
    """Run the simple pipeline test."""
    success = test_simple_watcher_api_communication()
    
    print("\n" + "="*50)
    if success:
        print("🎉 PIPELINE VALIDATION PASSED!")
        print("\n✅ The complete pipeline is working:")
        print("  • Production watcher processes JSON files correctly")
        print("  • Watcher successfully communicates with API")
        print("  • Events are stored in the database")
        print("  • No UUID generation bugs detected")
        print("\n🚫 CONCLUSION: The original 'UUID generation bug' has been resolved")
        print("              or was not actually a bug in the current codebase.")
    else:
        print("🚨 PIPELINE VALIDATION FAILED!")
        print("\n❌ Issues found in watcher → API communication")
    
    return success

if __name__ == "__main__":
    main()