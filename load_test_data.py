#!/usr/bin/env python3
"""Load test data from CSV files for manual testing."""

import csv
from pathlib import Path
from sqlalchemy.orm import Session
from src.soullink_tracker.db.database import engine
from src.soullink_tracker.db.models import Species, Route

def load_species_data():
    """Load species data from CSV."""
    with Session(engine) as session:
        species_file = Path("data/species.csv")
        
        if not species_file.exists():
            print(f"Species file not found: {species_file}")
            return
            
        with open(species_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                species = Species(
                    id=int(row['id']),
                    name=row['name'],
                    family_id=int(row['family_id'])
                )
                session.merge(species)  # Use merge to handle duplicates
        
        session.commit()
        print("Species data loaded successfully")

def load_routes_data():
    """Load route data from CSV."""
    with Session(engine) as session:
        routes_file = Path("data/routes.csv")
        
        if routes_file.exists():
            with open(routes_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    route = Route(
                        id=int(row['id']),
                        label=row['label'],
                        region=row.get('region', 'Johto')
                    )
                    session.merge(route)  # Use merge to handle duplicates
            
            session.commit()
            print("Routes data loaded successfully")
        else:
            # Create some basic routes for testing
            test_routes = [
                Route(id=30, label="Route 30", region="Johto"),
                Route(id=31, label="Route 31", region="Johto"),
                Route(id=32, label="Route 32", region="Johto"),
                Route(id=33, label="Route 33", region="Johto"),
                Route(id=34, label="Route 34", region="Johto"),
            ]
            
            for route in test_routes:
                session.merge(route)
            
            session.commit()
            print("Test routes created successfully")

if __name__ == "__main__":
    print("Loading test data...")
    load_species_data()
    load_routes_data()
    print("Test data loading complete!")