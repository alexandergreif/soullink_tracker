#!/usr/bin/env python3
"""
Test script to validate Lua event generation
Creates sample events as if they came from the Lua script
"""

import json
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Test configuration
TEST_RUN_ID = str(uuid4())
TEST_PLAYER_ID = str(uuid4())
OUTPUT_DIR = Path("C:/temp/soullink_events/")

def create_test_encounter(species_id=1, level=5, route_id=29, method="grass", rod_kind=None):
    """Create a test encounter event."""
    event = {
        "type": "encounter",
        "run_id": TEST_RUN_ID,
        "player_id": TEST_PLAYER_ID,
        "time": datetime.utcnow().isoformat() + "Z",
        "route_id": route_id,
        "species_id": species_id,
        "level": level,
        "shiny": False,
        "method": method,
        "event_version": "v3"
    }
    
    # Add rod_kind only for fishing
    if method == "fish" and rod_kind:
        event["rod_kind"] = rod_kind
    
    return event

def create_test_catch_result(species_id=1, route_id=29, status="caught"):
    """Create a test catch result event."""
    return {
        "type": "catch_result",
        "run_id": TEST_RUN_ID,
        "player_id": TEST_PLAYER_ID,
        "time": datetime.utcnow().isoformat() + "Z",
        "encounter_ref": {
            "route_id": route_id,
            "species_id": species_id
        },
        "status": status,
        "event_version": "v3"
    }

def validate_event(event):
    """Validate event has required fields."""
    errors = []
    
    # Check required base fields
    required_fields = ["type", "run_id", "player_id", "time"]
    for field in required_fields:
        if field not in event:
            errors.append(f"Missing required field: {field}")
    
    # Type-specific validation
    if event.get("type") == "encounter":
        encounter_fields = ["route_id", "species_id", "level", "shiny", "method"]
        for field in encounter_fields:
            if field not in event:
                errors.append(f"Missing encounter field: {field}")
        
        # Check rod_kind for fishing
        if event.get("method") == "fish" and "rod_kind" not in event:
            errors.append("Fishing encounter missing rod_kind")
            
    elif event.get("type") == "catch_result":
        if "encounter_ref" not in event:
            errors.append("Missing encounter_ref")
        elif not isinstance(event["encounter_ref"], dict):
            errors.append("encounter_ref must be an object")
        else:
            ref_fields = ["route_id", "species_id"]
            for field in ref_fields:
                if field not in event["encounter_ref"]:
                    errors.append(f"Missing encounter_ref.{field}")
        
        if "status" not in event:
            errors.append("Missing status field")
    
    return errors

def main():
    print("🧪 Testing Lua Event Generation Format")
    print("=" * 50)
    
    # Create test events
    test_events = [
        ("Grass encounter", create_test_encounter(1, 5, 29, "grass")),
        ("Surf encounter", create_test_encounter(129, 20, 40, "surf")),
        ("Fishing with old rod", create_test_encounter(129, 10, 32, "fish", "old")),
        ("Fishing with good rod", create_test_encounter(130, 20, 32, "fish", "good")),
        ("Fishing with super rod", create_test_encounter(130, 40, 32, "fish", "super")),
        ("Catch result - caught", create_test_catch_result(1, 29, "caught")),
        ("Catch result - fled", create_test_catch_result(129, 40, "fled")),
    ]
    
    all_valid = True
    
    for name, event in test_events:
        print(f"\n📝 Testing: {name}")
        errors = validate_event(event)
        
        if errors:
            print(f"   ❌ Validation failed:")
            for error in errors:
                print(f"      - {error}")
            all_valid = False
        else:
            print(f"   ✅ Valid event structure")
            
        # Show the event
        print(f"   Event: {json.dumps(event, indent=2)[:200]}...")
    
    print("\n" + "=" * 50)
    if all_valid:
        print("✅ All events are valid!")
        print("\nTest UUIDs used:")
        print(f"  Run ID: {TEST_RUN_ID}")
        print(f"  Player ID: {TEST_PLAYER_ID}")
    else:
        print("❌ Some events have validation errors")
        
    # Test that events can be serialized
    print("\n🔄 Testing JSON serialization...")
    for name, event in test_events:
        try:
            json_str = json.dumps(event, indent=2)
            parsed = json.loads(json_str)
            assert parsed == event
            print(f"   ✅ {name}: Serialization OK")
        except Exception as e:
            print(f"   ❌ {name}: Serialization failed - {e}")

if __name__ == "__main__":
    main()