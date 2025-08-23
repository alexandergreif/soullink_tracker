#!/usr/bin/env python3
"""
Direct API test to verify event processing works.
"""

import json
import requests
import subprocess
import time
from datetime import datetime, timezone
from uuid import uuid4

def test_api_direct():
    """Test the API directly to isolate the issue."""
    print("🎯 Testing API Event Processing Directly")
    print("="*50)
    
    # Start server
    print("1️⃣ Starting server...")
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", 
        "src.soullink_tracker.main:app",
        "--host", "127.0.0.1",
        "--port", "8002",
        "--log-level", "info"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for server
        server_url = "http://127.0.0.1:8002"
        for i in range(15):
            try:
                requests.get(f"{server_url}/health", timeout=2)
                break
            except:
                time.sleep(1)
        
        print("✅ Server started")
        
        # Create run and player
        print("2️⃣ Creating test run and player...")
        
        run_response = requests.post(f"{server_url}/v1/admin/runs", json={
            "name": "Direct API Test",
            "rules_json": {"first_encounter_only": True}
        })
        
        if run_response.status_code != 201:
            print(f"❌ Run creation failed: {run_response.status_code} - {run_response.text}")
            return False
        
        run_id = str(run_response.json()["id"])
        
        player_response = requests.post(f"{server_url}/v1/admin/runs/{run_id}/players", json={
            "name": "Direct Test Player",
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
        
        # Check initial state
        print("3️⃣ Checking initial state...")
        
        initial_response = requests.get(
            f"{server_url}/v1/runs/{run_id}/encounters",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        
        if initial_response.status_code != 200:
            print(f"❌ Initial check failed: {initial_response.status_code} - {initial_response.text}")
            return False
        
        initial_data = initial_response.json()
        initial_count = initial_data.get("total", 0)
        print(f"📊 Initial encounters: {initial_count}")
        
        # Send event directly to API
        print("4️⃣ Sending encounter event to API...")
        
        test_event = {
            "type": "encounter",
            "run_id": run_id,
            "player_id": player_id,
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 25,  # Pikachu
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        idempotency_key = str(uuid4())
        
        event_response = requests.post(
            f"{server_url}/v1/events",
            json=test_event,
            headers={
                "Authorization": f"Bearer {player_token}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key
            }
        )
        
        print(f"📋 Event API response: {event_response.status_code}")
        print(f"📋 Response body: {event_response.text}")
        
        if event_response.status_code == 202:
            print("✅ API accepted the event")
            event_result = event_response.json()
            print(f"   Event ID: {event_result.get('event_id', 'N/A')}")
            print(f"   Sequence: {event_result.get('seq', 'N/A')}")
        else:
            print("❌ API rejected the event")
            return False
        
        # Check final state
        print("5️⃣ Checking final state...")
        
        # Wait a moment for processing
        time.sleep(1)
        
        final_response = requests.get(
            f"{server_url}/v1/runs/{run_id}/encounters",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        
        if final_response.status_code == 200:
            final_data = final_response.json()
            final_count = final_data.get("total", 0)
            encounters_list = final_data.get("encounters", [])
            
            print(f"📊 Final encounters: {final_count}")
            
            if final_count > initial_count:
                print("✅ SUCCESS: Event was processed and stored!")
                print(f"   Added {final_count - initial_count} new encounters")
                
                # Show encounter details
                if encounters_list:
                    for i, enc in enumerate(encounters_list):
                        print(f"   Encounter {i+1}: Species {enc.get('species_id', 'N/A')} on Route {enc.get('route_id', 'N/A')}")
                
                return True
            else:
                print("❌ FAILURE: Event was not processed/stored")
                return False
        else:
            print(f"❌ Failed to check final encounters: {final_response.status_code}")
            return False
    
    finally:
        # Cleanup
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

def main():
    """Run the direct API test."""
    success = test_api_direct()
    
    print("\n" + "="*50)
    if success:
        print("🎉 DIRECT API TEST PASSED!")
        print("The API event processing is working correctly.")
    else:
        print("🚨 DIRECT API TEST FAILED!")
        print("There's an issue with the API event processing.")
    
    return success

if __name__ == "__main__":
    main()