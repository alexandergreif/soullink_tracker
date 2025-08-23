#!/usr/bin/env python3
"""
Test watcher behavior and check spool directory to understand what's happening.
"""

import json
import os
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

def test_watcher_with_spool_inspection():
    """Test watcher and inspect spool directory."""
    print("🔍 Testing Watcher with Spool Inspection")
    print("="*50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        spool_dir = temp_path / "spool"
        
        # Create NDJSON event file
        event_file = temp_path / "test_event.json"
        test_event = {
            "type": "encounter", 
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 42,
            "species_id": 25,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        with open(event_file, 'w') as f:
            json.dump(test_event, f, separators=(',', ':'))
            f.write('\n')
        
        print(f"📄 Event file: {event_file}")
        print(f"📂 Spool dir: {spool_dir}")
        
        # Test UUIDs
        test_run_id = str(uuid4())
        test_player_id = str(uuid4()) 
        
        watcher_cmd = [
            "python", "-m", "watcher.src.soullink_watcher.main",
            "--base-url", "http://httpbin.org/status/500",  # This will fail and spool
            "--run-id", test_run_id,
            "--player-id", test_player_id,
            "--token", "test-token",
            "--from-file", str(event_file),
            "--spool-dir", str(spool_dir),
            "--dev"
        ]
        
        print("🚀 Starting watcher process...")
        print(f"Command: {' '.join(watcher_cmd)}")
        
        # Start watcher process
        process = subprocess.Popen(
            watcher_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid  # Create new process group for clean termination
        )
        
        # Let it run for a few seconds
        time.sleep(5)
        
        print("🔍 Inspecting spool directory...")
        
        # Check spool directory structure
        if spool_dir.exists():
            print(f"✅ Spool directory exists: {spool_dir}")
            
            # Walk the spool directory
            spool_files = []
            for root, dirs, files in os.walk(spool_dir):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(spool_dir)
                    spool_files.append((relative_path, file_path))
            
            print(f"📊 Found {len(spool_files)} files in spool:")
            for rel_path, full_path in spool_files:
                file_size = full_path.stat().st_size
                print(f"   - {rel_path} ({file_size} bytes)")
                
                # If it's a JSON file, show contents
                if full_path.suffix == '.json' and file_size < 2000:
                    try:
                        with open(full_path, 'r') as f:
                            data = json.load(f)
                        print(f"     Content: {data.get('request_json', {}).get('type', 'unknown')} event")
                        print(f"     Idempotency key: {data.get('idempotency_key', 'N/A')}")
                        print(f"     Attempt: {data.get('attempt', 'N/A')}")
                    except Exception as e:
                        print(f"     Error reading: {e}")
        else:
            print(f"❌ Spool directory does not exist: {spool_dir}")
        
        # Terminate the watcher process
        print("🛑 Terminating watcher process...")
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for termination
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                print("⚠️  Process didn't terminate gracefully, killing...")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                stdout, stderr = process.communicate()
            
            print(f"📋 Process exit code: {process.returncode}")
            
            if stdout:
                print("📋 STDOUT:")
                print(stdout[:1000])  # Limit output
            
            if stderr:
                print("📋 STDERR:")  
                print(stderr[:1000])  # Limit output
                
        except Exception as e:
            print(f"❌ Error terminating process: {e}")
        
        # Final spool inspection
        print("\n🔍 Final spool inspection...")
        if spool_dir.exists():
            final_files = list(spool_dir.rglob('*'))
            print(f"📊 Final spool contents: {len(final_files)} files")
            
            for file_path in final_files:
                if file_path.is_file():
                    rel_path = file_path.relative_to(spool_dir)
                    print(f"   - {rel_path}")

if __name__ == "__main__":
    test_watcher_with_spool_inspection()