#!/usr/bin/env python3
"""
Test V2/V3 schema compatibility validation.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from src.soullink_tracker.api.schemas import EventEncounter, EventCatchResult
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus, RodKind


def test_v2_encounter_validation():
    """Test V2 encounter event format validation."""
    print("🧪 Testing V2 Encounter Event Compatibility")
    
    # V2 format with encounter_method (legacy field name)
    v2_encounter = {
        "type": "encounter",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "route_id": 32,
        "species_id": 129,
        "level": 10,
        "shiny": False,
        "encounter_method": "fish",  # V2 field name
        "rod_kind": "old"
    }
    
    try:
        encounter = EventEncounter(**v2_encounter)
        print(f"✅ V2 encounter validation passed")
        print(f"   Method: {encounter.method}")
        print(f"   Rod Kind: {encounter.rod_kind}")
        assert encounter.method == EncounterMethod.FISH
        assert encounter.rod_kind == RodKind.OLD
        return True
    except Exception as e:
        print(f"❌ V2 encounter validation failed: {e}")
        return False


def test_v2_catch_result_validation():
    """Test V2 catch_result event format validation."""
    print("\n🧪 Testing V2 Catch Result Event Compatibility")
    
    # V2 format with status field and encounter_ref
    v2_catch_result = {
        "type": "catch_result",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "encounter_ref": {
            "route_id": 32,
            "species_id": 129
        },
        "status": "caught"  # V2 field name
    }
    
    try:
        catch_result = EventCatchResult(**v2_catch_result)
        print(f"✅ V2 catch_result validation passed")
        print(f"   Status: {catch_result.status}")
        print(f"   Result: {catch_result.result}")
        print(f"   Encounter Ref: {catch_result.encounter_ref}")
        assert catch_result.status == EncounterStatus.CAUGHT
        assert catch_result.result == EncounterStatus.CAUGHT  # Should be synchronized
        return True
    except Exception as e:
        print(f"❌ V2 catch_result validation failed: {e}")
        return False


def test_v3_encounter_validation():
    """Test V3 encounter event format validation."""
    print("\n🧪 Testing V3 Encounter Event Compatibility")
    
    # V3 format with method field
    v3_encounter = {
        "type": "encounter",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "route_id": 31,
        "species_id": 25,
        "level": 5,
        "shiny": False,
        "method": "grass"  # V3 field name
    }
    
    try:
        encounter = EventEncounter(**v3_encounter)
        print(f"✅ V3 encounter validation passed")
        print(f"   Method: {encounter.method}")
        assert encounter.method == EncounterMethod.GRASS
        return True
    except Exception as e:
        print(f"❌ V3 encounter validation failed: {e}")
        return False


def test_v3_catch_result_validation():
    """Test V3 catch_result event format validation."""
    print("\n🧪 Testing V3 Catch Result Event Compatibility")
    
    # V3 format with result field and encounter_id
    v3_catch_result = {
        "type": "catch_result",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "encounter_id": str(uuid4()),
        "result": "fled"  # V3 field name
    }
    
    try:
        catch_result = EventCatchResult(**v3_catch_result)
        print(f"✅ V3 catch_result validation passed")
        print(f"   Result: {catch_result.result}")
        print(f"   Status: {catch_result.status}")
        print(f"   Encounter ID: {catch_result.encounter_id}")
        assert catch_result.result == EncounterStatus.FLED
        assert catch_result.status == EncounterStatus.FLED  # Should be synchronized
        return True
    except Exception as e:
        print(f"❌ V3 catch_result validation failed: {e}")
        return False


def test_enum_coercion():
    """Test string to enum coercion features."""
    print("\n🧪 Testing Enum Coercion Features")
    
    # Test case-insensitive and whitespace handling
    test_cases = [
        ("GRASS", EncounterMethod.GRASS),
        ("  surf  ", EncounterMethod.SURF),
        ("static", EncounterMethod.STATIC)
    ]
    
    all_passed = True
    for method_str, expected_enum in test_cases:
        encounter_data = {
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": method_str
        }
        
        try:
            encounter = EventEncounter(**encounter_data)
            print(f"✅ Enum coercion: '{method_str}' → {encounter.method}")
            assert encounter.method == expected_enum
        except Exception as e:
            print(f"❌ Enum coercion failed for '{method_str}': {e}")
            all_passed = False
    
    # Test fishing enum coercion with rod_kind
    fishing_data = {
        "type": "encounter",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "route_id": 32,
        "species_id": 129,
        "level": 10,
        "shiny": False,
        "method": "FISH",  # Uppercase
        "rod_kind": "good"
    }
    
    try:
        encounter = EventEncounter(**fishing_data)
        print(f"✅ Fishing enum coercion: 'FISH' → {encounter.method} with {encounter.rod_kind}")
        assert encounter.method == EncounterMethod.FISH
    except Exception as e:
        print(f"❌ Fishing enum coercion failed: {e}")
        all_passed = False
            
    return all_passed


def test_fishing_validation():
    """Test fishing-specific validation."""
    print("\n🧪 Testing Fishing Encounter Validation")
    
    # Valid fishing encounter
    valid_fishing = {
        "type": "encounter",
        "run_id": str(uuid4()),
        "player_id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "route_id": 32,
        "species_id": 129,
        "level": 10,
        "shiny": False,
        "method": "fish",
        "rod_kind": "super"
    }
    
    try:
        encounter = EventEncounter(**valid_fishing)
        print(f"✅ Valid fishing encounter passed: {encounter.rod_kind}")
    except Exception as e:
        print(f"❌ Valid fishing encounter failed: {e}")
        return False
    
    # Invalid fishing encounter (missing rod_kind)
    invalid_fishing = valid_fishing.copy()
    del invalid_fishing["rod_kind"]
    
    try:
        encounter = EventEncounter(**invalid_fishing)
        print(f"❌ Invalid fishing encounter should have failed but didn't")
        return False
    except Exception as e:
        print(f"✅ Invalid fishing encounter properly rejected: {e}")
        
    return True


def main():
    """Run all compatibility validation tests."""
    print("🚀 V2/V3 Schema Compatibility Validation Tests")
    print("=" * 60)
    
    results = [
        test_v2_encounter_validation(),
        test_v2_catch_result_validation(),
        test_v3_encounter_validation(),
        test_v3_catch_result_validation(),
        test_enum_coercion(),
        test_fishing_validation()
    ]
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 All compatibility tests passed!")
        print("✅ V2/V3 backward compatibility layer is working correctly")
        return True
    else:
        print("\n⚠️  Some tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)