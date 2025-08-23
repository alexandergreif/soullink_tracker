#!/usr/bin/env python3
"""
Test script to verify watcher validation improvements
Tests UUID validation, timestamp normalization, and event validation
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simple_watcher import SimpleWatcher

def test_uuid_validation():
    """Test UUID validation function."""
    watcher = SimpleWatcher()
    
    # Valid UUID
    valid_uuid = str(uuid4())
    assert watcher.validate_uuid(valid_uuid, "test_field") == valid_uuid
    
    # Invalid UUID
    try:
        watcher.validate_uuid("not-a-uuid", "test_field")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be a valid UUID" in str(e)
    
    # Empty UUID
    try:
        watcher.validate_uuid("", "test_field")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "is required" in str(e)
    
    print("✅ UUID validation tests passed")

def test_timestamp_normalization():
    """Test timestamp normalization."""
    watcher = SimpleWatcher()
    
    # Already correct format with Z
    ts1 = "2025-08-23T10:30:00Z"
    assert watcher.normalize_timestamp(ts1) == ts1
    
    # ISO format without timezone
    ts2 = "2025-08-23T10:30:00"
    result = watcher.normalize_timestamp(ts2)
    assert result.endswith("+00:00") or result.endswith("Z")
    
    # Invalid format should return current time
    ts3 = "invalid-timestamp"
    result = watcher.normalize_timestamp(ts3)
    assert "T" in result and ("Z" in result or "+" in result)
    
    # Empty should return current time
    result = watcher.normalize_timestamp("")
    assert "T" in result and ("Z" in result or "+" in result)
    
    print("✅ Timestamp normalization tests passed")

def test_event_validation():
    """Test event validation logic."""
    watcher = SimpleWatcher()
    
    # Valid encounter event
    encounter = {
        "type": "encounter",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "route_id": 29,
        "species_id": 1,
        "level": 5,
        "shiny": False,
        "method": "grass"
    }
    errors = watcher.validate_event(encounter)
    assert len(errors) == 0, f"Valid encounter should have no errors: {errors}"
    
    # Fishing encounter without rod_kind
    fishing = encounter.copy()
    fishing["method"] = "fish"
    errors = watcher.validate_event(fishing)
    assert len(errors) == 1
    assert "rod_kind" in errors[0]
    
    # Valid fishing encounter
    fishing["rod_kind"] = "good"
    errors = watcher.validate_event(fishing)
    assert len(errors) == 0
    
    # Invalid rod_kind
    fishing["rod_kind"] = "invalid"
    errors = watcher.validate_event(fishing)
    assert len(errors) == 1
    assert "Invalid rod_kind" in errors[0]
    
    # Valid catch_result with encounter_ref
    catch_result = {
        "type": "catch_result",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "encounter_ref": {
            "route_id": 29,
            "species_id": 1
        },
        "status": "caught"
    }
    errors = watcher.validate_event(catch_result)
    assert len(errors) == 0
    
    # catch_result without encounter reference
    bad_catch = catch_result.copy()
    del bad_catch["encounter_ref"]
    errors = watcher.validate_event(bad_catch)
    assert len(errors) == 1
    assert "encounter_id" in errors[0] or "encounter_ref" in errors[0]
    
    # catch_result without status/result
    bad_catch2 = catch_result.copy()
    del bad_catch2["status"]
    errors = watcher.validate_event(bad_catch2)
    assert len(errors) == 1
    assert "result" in errors[0] or "status" in errors[0]
    
    # Valid faint event
    faint = {
        "type": "faint",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "pokemon_key": "12345678"
    }
    errors = watcher.validate_event(faint)
    assert len(errors) == 0
    
    print("✅ Event validation tests passed")

def test_file_processing():
    """Test processing a complete event file."""
    watcher = SimpleWatcher()
    watcher.run_id = str(uuid4())
    watcher.player_id = str(uuid4())
    watcher.player_token = "test-token"
    
    # Create temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_event.json"
        
        # Test event with missing UUIDs (should be injected)
        event = {
            "type": "encounter",
            "time": "2025-08-23T10:30:00",  # Missing timezone
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "encounter_method": "grass"  # V2 field name
        }
        
        with open(test_file, "w") as f:
            json.dump(event, f)
        
        # Mock the API call to avoid actual network request
        import unittest.mock as mock
        with mock.patch('requests.post') as mock_post:
            mock_response = mock.Mock()
            mock_response.status_code = 202
            mock_response.text = '{"message": "Event processed"}'
            mock_post.return_value = mock_response
            
            # Process the file
            result = watcher.process_json_file(test_file)
            
            # Verify the call was made
            assert mock_post.called
            
            # Check the processed event
            call_args = mock_post.call_args
            processed_event = call_args[1]['json']
            
            # Verify UUIDs were injected
            assert processed_event['run_id'] == watcher.run_id
            assert processed_event['player_id'] == watcher.player_id
            
            # Verify timestamp was normalized
            assert 'T' in processed_event['time']
            assert processed_event['time'].endswith('+00:00') or processed_event['time'].endswith('Z')
            
            # Verify method was normalized from encounter_method
            assert processed_event['method'] == 'grass'
            assert 'encounter_method' not in processed_event
            
            # Verify idempotency key was set
            headers = call_args[1]['headers']
            assert 'Idempotency-Key' in headers
            
    print("✅ File processing tests passed")

def main():
    """Run all tests."""
    print("Testing Watcher Validation Improvements\n")
    print("=" * 50)
    
    test_uuid_validation()
    test_timestamp_normalization()
    test_event_validation()
    test_file_processing()
    
    print("\n" + "=" * 50)
    print("✅ All tests passed successfully!")
    print("\nThe watcher now properly:")
    print("  • Validates and normalizes UUID fields")
    print("  • Normalizes timestamps to ISO 8601 UTC")
    print("  • Validates events before sending to API")
    print("  • Handles both V2 and V3 event formats")
    print("  • Generates deterministic idempotency keys")

if __name__ == "__main__":
    main()