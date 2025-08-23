#!/usr/bin/env python3
"""
Debug the watcher issue to understand why it's hanging.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

def test_watcher_components():
    """Test individual watcher components to isolate the issue."""
    print("🔧 Testing Watcher Components")
    print("="*40)
    
    # Test 1: Import watcher modules
    print("1️⃣ Testing watcher imports...")
    try:
        from watcher.src.soullink_watcher.main import main
        from watcher.src.soullink_watcher.config import WatcherConfig
        from watcher.src.soullink_watcher.ndjson_reader import validate_event_minimal
        print("✅ All watcher imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return
    
    # Test 2: Create config
    print("\n2️⃣ Testing config creation...")
    test_run_id = str(uuid4())
    test_player_id = str(uuid4())
    
    try:
        from argparse import Namespace
        args = Namespace(
            base_url="http://httpbin.org/status/200",
            run_id=test_run_id,
            player_id=test_player_id,
            token="test-token",
            from_file=None,
            spool_dir=None,
            poll_interval=1.0,
            backoff_base=1.0,
            backoff_max=60.0,
            backoff_jitter=0.1,
            http_timeout=5.0,
            dev=True
        )
        
        from watcher.src.soullink_watcher.cli import build_config
        config = build_config(args)
        print("✅ Config creation successful")
        print(f"   Base URL: {config.base_url}")
        print(f"   Run ID: {config.run_id}")
        print(f"   Player ID: {config.player_id}")
    except Exception as e:
        print(f"❌ Config creation failed: {e}")
        return
    
    # Test 3: Event validation
    print("\n3️⃣ Testing event validation...")
    try:
        test_event = {
            "type": "encounter",
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 1,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        validated = validate_event_minimal(test_event, test_run_id, test_player_id)
        print("✅ Event validation successful")
        print(f"   Validated event has run_id: {validated.get('run_id') == test_run_id}")
        print(f"   Validated event has player_id: {validated.get('player_id') == test_player_id}")
    except Exception as e:
        print(f"❌ Event validation failed: {e}")
        return
    
    # Test 4: File reading
    print("\n4️⃣ Testing file reading...")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.json"
            
            with open(test_file, 'w') as f:
                json.dump(test_event, f)
            
            from watcher.src.soullink_watcher.ndjson_reader import iter_ndjson, count_events_in_file
            
            event_count = count_events_in_file(test_file)
            print(f"✅ File reading successful, found {event_count} events")
            
            events = list(iter_ndjson(test_file))
            print(f"✅ Event parsing successful, parsed {len(events)} events")
            
    except Exception as e:
        print(f"❌ File reading failed: {e}")
        return
    
    # Test 5: Check if the main function signature has issues
    print("\n5️⃣ Testing main function signature...")
    try:
        from watcher.src.soullink_watcher.main import ingest_from_file
        print("✅ Main function imports available")
        
        # Check if calling main with None config works
        from watcher.src.soullink_watcher.main import main
        help_result = None
        
        # Try calling main with --help to see if it exits gracefully
        try:
            main(argv=["--help"])
        except SystemExit as e:
            if e.code in [0, None]:
                print("✅ Help command works (SystemExit 0)")
            else:
                print(f"⚠️  Help command exits with code: {e.code}")
        except Exception as e:
            print(f"❌ Help command failed: {e}")
            
    except Exception as e:
        print(f"❌ Main function test failed: {e}")
        return
    
    print("\n" + "="*40)
    print("🎯 ANALYSIS:")
    print("All watcher components appear to be working correctly.")
    print("The hanging issue might be in the daemon loop or HTTP client.")
    print("\nPossible causes:")
    print("  • Watcher enters infinite daemon loop even with --from-file")
    print("  • HTTP client hangs on connection attempts") 
    print("  • Lock file acquisition blocks the process")

if __name__ == "__main__":
    test_watcher_components()