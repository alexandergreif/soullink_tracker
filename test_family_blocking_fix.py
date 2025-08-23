#!/usr/bin/env python3
"""
Test script to verify the family blocking bug is fixed.
This test creates a realistic scenario to reproduce and verify the fix.
"""

import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4, UUID
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from soullink_tracker.domain.events import EncounterEvent, CatchResultEvent
from soullink_tracker.domain.rules import apply_catch_result, RunState
from soullink_tracker.core.enums import EncounterStatus, EncounterMethod
from soullink_tracker.store.event_store import EventStore
from soullink_tracker.store.projections import ProjectionEngine
from soullink_tracker.db.database import create_database_engine, SessionLocal
from soullink_tracker.db.models import Base, Species, Route, Run, Player


def setup_test_database():
    """Create a test database with species and routes data."""
    # Create temporary database
    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_database_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal(bind=engine)
    
    # Add species data (matching Pokemon families)
    species_data = [
        (1, "Bulbasaur", 1),      # Bulbasaur family
        (2, "Ivysaur", 1),
        (3, "Venusaur", 1),
        (4, "Charmander", 4),      # Charmander family
        (5, "Charmeleon", 4),
        (6, "Charizard", 4),
        (7, "Squirtle", 7),        # Squirtle family
        (8, "Wartortle", 7),
        (9, "Blastoise", 7),
        (10, "Caterpie", 10),      # Caterpie family
        (11, "Metapod", 10),
        (12, "Butterfree", 10),
    ]
    
    for species_id, name, family_id in species_data:
        species = Species(id=species_id, name=name, family_id=family_id)
        db.add(species)
    
    # Add routes
    routes_data = [
        (29, "Route 29", "Johto"),
        (30, "Route 30", "Johto"),
        (31, "Route 31", "Johto"),
        (32, "Route 32", "Johto"),
    ]
    
    for route_id, label, region in routes_data:
        route = Route(id=route_id, label=label, region=region)
        db.add(route)
    
    db.commit()
    return engine, db


def test_family_blocking_scenario():
    """Test the complete family blocking scenario."""
    print("Testing Family Blocking Bug Fix\n")
    print("=" * 50)
    
    # Setup database
    engine, db = setup_test_database()
    event_store = EventStore(db)
    projection_engine = ProjectionEngine(db)
    
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
    
    print(f"Created run: {run_id}")
    print(f"Created player: {player_id}\n")
    
    # Create encounter events
    bulbasaur_encounter_id = uuid4()
    squirtle_encounter_id = uuid4()
    charmander_encounter_id = uuid4()
    
    encounters = [
        EncounterEvent(
            event_id=bulbasaur_encounter_id,
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            route_id=29,
            species_id=1,  # Bulbasaur
            family_id=1,   # Bulbasaur family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        ),
        EncounterEvent(
            event_id=squirtle_encounter_id,
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            route_id=31,
            species_id=7,  # Squirtle
            family_id=7,   # Squirtle family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        ),
        EncounterEvent(
            event_id=charmander_encounter_id,
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            route_id=30,
            species_id=4,  # Charmander
            family_id=4,   # Charmander family
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        ),
    ]
    
    # Store encounter events
    for encounter in encounters:
        envelope = event_store.append(encounter)
        projection_engine.apply_event(envelope)
        print(f"Stored encounter: species_id={encounter.species_id}, family_id={encounter.family_id}")
    
    print("\n" + "-" * 50 + "\n")
    
    # Create catch result events
    catch_results = [
        CatchResultEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            encounter_id=bulbasaur_encounter_id,
            result=EncounterStatus.CAUGHT
        ),
        CatchResultEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            encounter_id=squirtle_encounter_id,
            result=EncounterStatus.CAUGHT
        ),
        CatchResultEvent(
            event_id=uuid4(),
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp,
            encounter_id=charmander_encounter_id,
            result=EncounterStatus.FLED
        ),
    ]
    
    # Process catch results and check blocking
    print("Processing catch results:\n")
    blocked_families = set()
    
    for catch_result in catch_results:
        # Store the event
        envelope = event_store.append(catch_result)
        
        # Process with projection engine to update blocklist
        projection_engine.apply_event(envelope)
        
        # Check what got blocked using direct lookup
        encounter_event = event_store.get_event_by_id(run_id, catch_result.encounter_id)
        if encounter_event:
            enc = encounter_event.event
            species_name = {1: "Bulbasaur", 7: "Squirtle", 4: "Charmander"}.get(enc.species_id, "Unknown")
            result_str = "CAUGHT" if catch_result.result == EncounterStatus.CAUGHT else "FLED"
            
            print(f"  {species_name} (family={enc.family_id}): {result_str}")
            
            if catch_result.result == EncounterStatus.CAUGHT:
                blocked_families.add(enc.family_id)
                print(f"    → Family {enc.family_id} should be blocked")
    
    print("\n" + "-" * 50 + "\n")
    
    # Verify blocklist in database
    from soullink_tracker.db.models import Blocklist
    blocklist_entries = db.query(Blocklist).filter(Blocklist.run_id == run_id).all()
    
    actual_blocked = {entry.family_id for entry in blocklist_entries}
    
    print("Expected blocked families:", sorted(blocked_families))
    print("Actual blocked families:", sorted(actual_blocked))
    
    # Verify correctness
    expected = {1, 7}  # Bulbasaur and Squirtle families (caught)
    success = actual_blocked == expected
    
    if success:
        print("\n✅ SUCCESS: Correct families are blocked!")
        print("  • Bulbasaur family (1) - blocked ✓")
        print("  • Squirtle family (7) - blocked ✓")
        print("  • Charmander family (4) - not blocked (fled) ✓")
        print("  • Caterpie family (10) - not blocked (never encountered) ✓")
    else:
        print("\n❌ FAILURE: Wrong families are blocked!")
        if 10 in actual_blocked:
            print("  • ERROR: Caterpie family (10) is blocked but was never encountered!")
        if 1 not in actual_blocked:
            print("  • ERROR: Bulbasaur family (1) should be blocked but isn't!")
        if 7 not in actual_blocked:
            print("  • ERROR: Squirtle family (7) should be blocked but isn't!")
        if 4 in actual_blocked:
            print("  • ERROR: Charmander family (4) shouldn't be blocked (fled)!")
    
    # Cleanup
    db.close()
    engine.dispose()
    
    return success


if __name__ == "__main__":
    success = test_family_blocking_scenario()
    sys.exit(0 if success else 1)