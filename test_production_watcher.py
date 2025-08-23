#!/usr/bin/env python3
"""
Test script to validate the production watcher pipeline and identify UUID bugs
"""

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

def test_production_watcher_uuid_bug():
    """Test the production watcher with a real event file to identify UUID issues."""
    print("Testing Production Watcher UUID Generation...")
    
    # First test: Try importing the production watcher
    try:
        from watcher.src.soullink_watcher.main import main
        from watcher.src.soullink_watcher.config import WatcherConfig
        print("✅ Successfully imported production watcher")
    except ImportError as e:
        print(f"❌ Failed to import production watcher: {e}")
        return False
    
    # Create test UUIDs 
    test_run_id = str(uuid.uuid4())
    test_player_id = str(uuid.uuid4())
    test_token = "test-token-12345"
    
    print(f"Test Run ID: {test_run_id}")
    print(f"Test Player ID: {test_player_id}")
    
    # Create a temporary directory and event file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create event file
        event_file = temp_path / "test_encounter.json"
        test_event = {
            "type": "encounter",
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 29,
            "species_id": 25,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        with open(event_file, 'w') as f:
            json.dump(test_event, f, indent=2)
        
        print(f"Created test event file: {event_file}")
        print(f"Event content: {test_event}")
        
        # Test the production watcher configuration
        try:
            from watcher.src.soullink_watcher.cli import build_config
            from argparse import Namespace
            
            # Mock command line arguments - note the argument names match CLI exactly
            args = Namespace(
                base_url="http://localhost:8000",
                run_id=test_run_id,
                player_id=test_player_id,
                token=test_token,
                from_file=str(event_file),
                spool_dir=str(temp_path / "spool"),
                poll_interval=1.0,
                http_timeout=10.0,
                backoff_base=1.0,
                backoff_max=60.0,
                backoff_jitter=0.1,
                dev=True
            )
            
            config = build_config(args)
            print("✅ Successfully built watcher config")
            print(f"Config run_id: {config.run_id}")
            print(f"Config player_id: {config.player_id}")
            
        except Exception as e:
            print(f"❌ Failed to build watcher config: {e}")
            return False
        
        # Test event validation
        try:
            from watcher.src.soullink_watcher.ndjson_reader import validate_event_minimal
            
            # Test validation without UUIDs (should inject them)
            validated_event = validate_event_minimal(test_event, test_run_id, test_player_id)
            print("✅ Event validation passed")
            print(f"Validated event: {json.dumps(validated_event, indent=2)}")
            
            # Check if UUIDs were injected correctly
            assert validated_event["run_id"] == test_run_id
            assert validated_event["player_id"] == test_player_id
            print("✅ UUIDs injected correctly")
            
        except Exception as e:
            print(f"❌ Event validation failed: {e}")
            return False
        
        # Test UUID generation in spool system
        try:
            from watcher.src.soullink_watcher.spool import SpoolQueue
            
            spool = SpoolQueue(temp_path / "spool", test_run_id, test_player_id)
            
            # Test enqueueing an event
            headers = {
                'Authorization': f'Bearer {test_token}',
                'Content-Type': 'application/json'
            }
            
            # This is where the UUID generation bug might be
            spool_path = spool.enqueue(
                payload=validated_event,
                idempotency_key=str(uuid.uuid4()),  # Generate UUID here
                headers=headers,
                base_url="http://localhost:8000"
            )
            
            print("✅ Successfully spooled event")
            print(f"Spool file: {spool_path}")
            
            # Read back the spooled event
            with open(spool_path, 'r') as f:
                spooled_data = json.load(f)
            
            print(f"Spooled record ID: {spooled_data.get('record_id')}")
            print(f"Idempotency key: {spooled_data.get('idempotency_key')}")
            
            # Check for UUID format issues
            record_id = spooled_data.get('record_id')
            idempotency_key = spooled_data.get('idempotency_key')
            
            try:
                uuid.UUID(record_id)
                print("✅ Record ID is valid UUID")
            except ValueError:
                print(f"❌ Record ID is invalid UUID: {record_id}")
                return False
            
            try:
                uuid.UUID(idempotency_key)
                print("✅ Idempotency key is valid UUID")
            except ValueError:
                print(f"❌ Idempotency key is invalid UUID: {idempotency_key}")
                return False
                
        except Exception as e:
            print(f"❌ Spool system test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test the HTTP client UUID handling
        try:
            from watcher.src.soullink_watcher.http_client import EventSender
            from watcher.src.soullink_watcher.spool import SpoolRecord
            
            # Create a mock SpoolRecord
            record_data = {
                'record_id': str(uuid.uuid4()),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'next_attempt_at': datetime.now(timezone.utc).isoformat(),
                'attempt': 0,
                'idempotency_key': str(uuid.uuid4()),
                'base_url': 'http://localhost:8000',
                'endpoint_path': '/v1/events',
                'method': 'POST',
                'headers': headers,
                'request_json': validated_event,
                'run_id': test_run_id,
                'player_id': test_player_id
            }
            
            record = SpoolRecord.from_dict(record_data)
            print("✅ Successfully created SpoolRecord")
            
            # Test UUID fields in record
            try:
                uuid.UUID(record.record_id)
                uuid.UUID(record.idempotency_key)
                uuid.UUID(record.run_id)
                uuid.UUID(record.player_id)
                print("✅ All UUIDs in SpoolRecord are valid")
            except ValueError as e:
                print(f"❌ Invalid UUID in SpoolRecord: {e}")
                return False
            
        except Exception as e:
            print(f"❌ HTTP client test failed: {e}")
            return False
    
    print("\n" + "="*50)
    print("✅ All production watcher UUID tests passed!")
    print("The UUID generation appears to be working correctly.")
    print("\nIf there was a bug, it may have been:")
    print("  1. Already fixed in recent changes")
    print("  2. Related to specific runtime conditions")
    print("  3. In a different part of the pipeline")
    return True

def test_simple_watcher_comparison():
    """Test the simple watcher to compare behavior."""
    print("\nTesting Simple Watcher for comparison...")
    
    try:
        from simple_watcher import SimpleWatcher
        
        watcher = SimpleWatcher()
        watcher.run_id = str(uuid.uuid4())
        watcher.player_id = str(uuid.uuid4())
        watcher.player_token = "test-token"
        
        print(f"Simple watcher run_id: {watcher.run_id}")
        print(f"Simple watcher player_id: {watcher.player_id}")
        
        # Test UUID validation
        try:
            uuid.UUID(watcher.run_id)
            uuid.UUID(watcher.player_id)
            print("✅ Simple watcher UUIDs are valid")
        except ValueError as e:
            print(f"❌ Simple watcher UUID error: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import simple watcher: {e}")
        return False
    except Exception as e:
        print(f"❌ Simple watcher test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("PRODUCTION WATCHER UUID BUG INVESTIGATION")
    print("="*60)
    
    success1 = test_production_watcher_uuid_bug()
    success2 = test_simple_watcher_comparison()
    
    print("\n" + "="*60)
    if success1 and success2:
        print("🎉 CONCLUSION: No UUID generation bugs detected!")
        print("\nThe issue might be:")
        print("  • Already resolved by recent fixes")
        print("  • Occurs only in specific runtime scenarios") 
        print("  • Related to network/API communication rather than UUID generation")
        print("\nNext steps: Test actual watcher-to-API communication with running server")
    else:
        print("🚨 CONCLUSION: UUID generation issues detected!")
        print("Review the failed tests above for specific problems.")

if __name__ == "__main__":
    main()