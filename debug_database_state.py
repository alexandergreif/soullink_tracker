#!/usr/bin/env python3
"""
Debug the database state to understand what encounters exist.
"""

from src.soullink_tracker.db.database import get_db
from src.soullink_tracker.db.models import Run, Player, Encounter, Species

def debug_database_state():
    """Debug the current database state."""
    print("🔍 Database State Debug")
    print("="*40)
    
    db = next(get_db())
    try:
        # Check runs
        runs = db.query(Run).all()
        print(f"📊 Total runs in database: {len(runs)}")
        
        for i, run in enumerate(runs[-3:], 1):  # Show last 3 runs
            print(f"   Run {i}: {run.id} - {run.name}")
            
            # Check players for this run
            players = db.query(Player).filter(Player.run_id == run.id).all()
            print(f"     Players: {len(players)}")
            
            for player in players:
                print(f"       Player: {player.id} - {player.name}")
                
                # Check encounters for this player
                encounters = db.query(Encounter).filter(
                    Encounter.run_id == run.id,
                    Encounter.player_id == player.id
                ).all()
                print(f"         Encounters: {len(encounters)}")
                
                for enc in encounters:
                    species = db.query(Species).filter(Species.id == enc.species_id).first()
                    species_name = species.name if species else f"Species-{enc.species_id}"
                    print(f"           - {species_name} on Route {enc.route_id} ({enc.status})")
        
        # Check total encounters across all runs
        total_encounters = db.query(Encounter).count()
        print(f"\n📊 Total encounters across all runs: {total_encounters}")
        
        # Check species data
        species_count = db.query(Species).count()
        print(f"📊 Species in database: {species_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_database_state()