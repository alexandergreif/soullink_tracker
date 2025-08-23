#!/usr/bin/env python3
"""
Test the blocklist API endpoint to verify it returns correct data.
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from test_family_blocking_fix import setup_test_database
from soullink_tracker.main import app
from soullink_tracker.db.models import Run, Player, Blocklist
from soullink_tracker.domain.events import EncounterEvent, CatchResultEvent
from soullink_tracker.core.enums import EncounterStatus, EncounterMethod
from soullink_tracker.store.event_store import EventStore
from soullink_tracker.store.projections import ProjectionEngine
from fastapi.testclient import TestClient


def test_blocklist_api():
    """Test the blocklist API endpoint returns correct family blocking data."""
    print("Testing Blocklist API Endpoint\n")
    print("=" * 50)
    
    # Setup database
    engine, db = setup_test_database()
    
    # Create test client
    client = TestClient(app)
    
    # Override the database dependency
    def get_test_db():
        try:
            yield db
        finally:
            pass
    
    from soullink_tracker.db.database import get_db
    app.dependency_overrides[get_db] = get_test_db
    
    # Create test run and player
    run_id = uuid4()
    player_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    
    run = Run(
        id=run_id,
        name="Test Run",
        rules_json={"dupe_clause": True, "species_clause": True},
        created_at=timestamp
    )
    db.add(run)
    
    player = Player(
        id=player_id,
        run_id=run_id,
        name="TestPlayer",
        game="HeartGold",
        region="EU",
        token_hash="test_token_hash",
        created_at=timestamp
    )
    db.add(player)
    db.commit()
    
    print(f"Created run: {run_id}\n")
    
    # Directly add blocklist entries to test API
    blocked_families = [
        (1, "caught"),     # Bulbasaur family
        (7, "caught"),     # Squirtle family
        (25, "caught"),    # Pikachu family
    ]
    
    for family_id, origin in blocked_families:
        blocklist_entry = Blocklist(
            run_id=run_id,
            family_id=family_id,
            origin=origin,
            created_at=timestamp
        )
        db.add(blocklist_entry)
    
    db.commit()
    print(f"Added {len(blocked_families)} families to blocklist\n")
    
    # Test the API endpoint
    print("Testing GET /v1/runs/{run_id}/blocklist\n")
    response = client.get(f"/v1/runs/{run_id}/blocklist")
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response data: {json.dumps(data, indent=2)}\n")
        
        # Verify the response
        if "blocked_families" in data:
            blocklist = data["blocked_families"]
            returned_families = {entry["family_id"] for entry in blocklist}
            expected_families = {1, 7, 25}
            
            print("Expected families:", sorted(expected_families))
            print("Returned families:", sorted(returned_families))
            
            if returned_families == expected_families:
                print("\n✅ SUCCESS: Blocklist API returns correct families!")
                
                # Verify each entry has correct fields
                for entry in blocklist:
                    assert "family_id" in entry
                    assert "origin" in entry
                    assert entry["origin"] == "caught"
                    print(f"  • Family {entry['family_id']}: {entry['origin']} ✓")
                
                success = True
            else:
                print("\n❌ FAILURE: Blocklist API returns wrong families!")
                missing = expected_families - returned_families
                extra = returned_families - expected_families
                if missing:
                    print(f"  Missing families: {missing}")
                if extra:
                    print(f"  Extra families: {extra}")
                success = False
        else:
            print("❌ FAILURE: Response missing 'blocklist' field")
            success = False
    else:
        print(f"❌ FAILURE: API returned status {response.status_code}")
        print(f"Response: {response.text}")
        success = False
    
    # Test with non-existent run
    print("\n" + "-" * 50)
    print("\nTesting with non-existent run...")
    fake_run_id = uuid4()
    response = client.get(f"/v1/runs/{fake_run_id}/blocklist")
    
    if response.status_code == 404:
        print(f"✅ Correctly returns 404 for non-existent run")
    else:
        print(f"❌ Expected 404, got {response.status_code}")
        success = False
    
    # Cleanup
    db.close()
    engine.dispose()
    app.dependency_overrides.clear()
    
    return success


if __name__ == "__main__":
    success = test_blocklist_api()
    sys.exit(0 if success else 1)