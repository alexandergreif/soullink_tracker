#!/usr/bin/env python3
"""
Direct test of the production watcher to see detailed output.
"""

import json
import tempfile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

def test_watcher_direct():
    """Test the watcher directly with verbose output."""
    print("🔍 Testing Production Watcher Directly")
    print("="*50)
    
    # Create test event
    with tempfile.TemporaryDirectory() as temp_dir:
        event_file = Path(temp_dir) / "test_event.json"
        
        test_event = {
            "type": "encounter",
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 99,
            "species_id": 150,  # Mewtwo
            "level": 70,
            "shiny": True,
            "method": "static"
        }
        
        with open(event_file, 'w') as f:
            # Write as NDJSON (newline-delimited JSON), not pretty-printed JSON
            json.dump(test_event, f, separators=(',', ':'))
            f.write('\n')  # Add newline for NDJSON format
        
        print(f"📄 Event file: {event_file}")
        print(f"📄 Event content: {json.dumps(test_event, indent=2)}")
        
        # Test UUIDs
        test_run_id = str(uuid4())
        test_player_id = str(uuid4())
        test_token = "fake-token-for-testing"
        
        print(f"🎯 Run ID: {test_run_id}")
        print(f"🎯 Player ID: {test_player_id}")
        
        # Run watcher with verbose output
        watcher_cmd = [
            "python", "-m", "watcher.src.soullink_watcher.main",
            "--base-url", "http://httpbin.org/status/404",  # This will fail, which is fine
            "--run-id", test_run_id,
            "--player-id", test_player_id,
            "--token", test_token,
            "--from-file", str(event_file),
            "--dev"
        ]
        
        print("🚀 Running watcher command:")
        print(f"   {' '.join(watcher_cmd)}")
        print("\n📋 Watcher output:")
        print("-" * 30)
        
        try:
            result = subprocess.run(
                watcher_cmd,
                capture_output=True,
                text=True,
                timeout=10  # Shorter timeout since we expect it to fail quickly
            )
            
            print("STDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("\nSTDERR:")
                print(result.stderr)
            
            print(f"\nExit code: {result.returncode}")
            
        except subprocess.TimeoutExpired:
            print("⏰ Command timed out")
            return False
        except Exception as e:
            print(f"❌ Error running watcher: {e}")
            return False
        
        print("-" * 30)
        
        # Analyze the output
        if "Ingestion complete" in result.stdout:
            print("✅ Watcher completed file ingestion")
        else:
            print("❌ Watcher did not complete file ingestion")
            
        if "Error processing event" in result.stdout:
            print("❌ Watcher had errors processing events")
        else:
            print("✅ No event processing errors detected")
            
        if test_run_id in result.stdout and test_player_id in result.stdout:
            print("✅ UUIDs were correctly used in watcher")
        else:
            print("❌ UUIDs not found in watcher output")
            
        # Look for HTTP errors
        if "Connection error" in result.stdout or "Request error" in result.stdout:
            print("✅ Expected network errors occurred (httpbin.org should fail)")
        else:
            print("⚠️  No network errors found - this is unexpected")

if __name__ == "__main__":
    test_watcher_direct()