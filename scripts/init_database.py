#!/usr/bin/env python3
"""Initialize database with sample data for SoulLink tracker."""

import csv
import sys
from pathlib import Path
from uuid import uuid4

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from soullink_tracker.db.database import Base
from soullink_tracker.db.models import Run, Player, Species, Route


def create_database(database_url: str = "sqlite:///soullink_tracker.db"):
    """Create database and tables."""
    print(f"Creating database: {database_url}")
    
    engine = create_engine(database_url)
    
    # Enable WAL mode for SQLite
    if database_url.startswith("sqlite"):
        from sqlalchemy import event
        
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=1000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
        
        event.listen(engine, "connect", set_sqlite_pragma)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
    
    return engine


def load_species_data(session, species_file: Path):
    """Load Pokemon species reference data."""
    print(f"Loading species data from {species_file}")
    
    if not species_file.exists():
        print(f"⚠️  Species file not found: {species_file}")
        print("Creating minimal species data for testing...")
        
        # Create some basic species for testing
        test_species = [
            (1, "Bulbasaur", 1),
            (2, "Ivysaur", 1), 
            (3, "Venusaur", 1),
            (4, "Charmander", 4),
            (5, "Charmeleon", 4),
            (6, "Charizard", 4),
            (7, "Squirtle", 7),
            (8, "Wartortle", 7),
            (9, "Blastoise", 7),
            (25, "Pikachu", 25),
            (26, "Raichu", 25),
            # Add more as needed for testing
        ]
        
        for species_id, name, family_id in test_species:
            species = Species(id=species_id, name=name, family_id=family_id)
            session.merge(species)  # Use merge to handle duplicates
            
        print(f"✅ Created {len(test_species)} test species")
        return len(test_species)
    
    # Load from CSV file
    count = 0
    with open(species_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            species = Species(
                id=int(row['id']),
                name=row['name'],
                family_id=int(row['family_id'])
            )
            session.merge(species)
            count += 1
    
    print(f"✅ Loaded {count} species from CSV")
    return count


def load_routes_data(session, routes_file: Path):
    """Load route reference data."""
    print(f"Loading routes data from {routes_file}")
    
    if not routes_file.exists():
        print(f"⚠️  Routes file not found: {routes_file}")
        print("Creating minimal routes data for testing...")
        
        # Create some basic HG/SS routes for testing
        test_routes = [
            (1, "Route 29", "EU"),
            (2, "Route 30", "EU"), 
            (3, "Route 31", "EU"),
            (4, "Route 32", "EU"),
            (5, "Route 33", "EU"),
            (6, "Violet City", "EU"),
            (7, "Cherrygrove City", "EU"),
            (8, "New Bark Town", "EU"),
            # Add more routes as needed
        ]
        
        for route_id, label, region in test_routes:
            route = Route(id=route_id, label=label, region=region)
            session.merge(route)
            
        print(f"✅ Created {len(test_routes)} test routes")
        return len(test_routes)
    
    # Load from CSV file
    count = 0
    with open(routes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            route = Route(
                id=int(row['id']),
                label=row['label'],
                region=row['region']
            )
            session.merge(route)
            count += 1
    
    print(f"✅ Loaded {count} routes from CSV")
    return count


def create_sample_run(session):
    """Create a sample run with 3 players."""
    print("Creating sample SoulLink run...")
    
    # Create run
    run = Run(
        id=uuid4(),
        name="Test SoulLink Run - HG/SS",
        rules_json={
            "dupes_clause": True,
            "fishing_enabled": True,
            "soul_link_enabled": True,
            "species_clause": True
        }
    )
    session.add(run)
    session.flush()  # Get the ID
    
    # Create 3 players
    players = []
    games = ["HeartGold", "SoulSilver", "HeartGold"]
    names = ["Player1", "Player2", "Player3"]
    
    for i, (name, game) in enumerate(zip(names, games)):
        token, token_hash = Player.generate_token()
        
        player = Player(
            id=uuid4(),
            run_id=run.id,
            name=name,
            game=game,
            region="EU",
            token_hash=token_hash
        )
        session.add(player)
        session.flush()
        
        players.append({
            "id": str(player.id),
            "name": name,
            "game": game,
            "token": token  # Store for output
        })
    
    session.commit()
    
    print(f"✅ Created sample run: {run.name}")
    print(f"   Run ID: {run.id}")
    print("   Players:")
    for player in players:
        print(f"     - {player['name']} ({player['game']})")
        print(f"       ID: {player['id']}")
        print(f"       Token: {player['token']}")
    
    return {
        "run_id": str(run.id),
        "run_name": run.name,
        "players": players
    }


def main():
    """Main initialization function."""
    print("🚀 Initializing SoulLink Tracker Database")
    print("=" * 50)
    
    # Paths
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    species_file = data_dir / "species.csv"
    routes_file = data_dir / "routes.csv"
    
    # Create database
    engine = create_database()
    SessionLocal = sessionmaker(bind=engine)
    
    # Load data
    with SessionLocal() as session:
        # Load reference data
        species_count = load_species_data(session, species_file)
        routes_count = load_routes_data(session, routes_file)
        
        # Create sample run
        sample_run = create_sample_run(session)
        
        session.commit()
    
    print("\n" + "=" * 50)
    print("🎉 Database initialization complete!")
    print(f"   Species loaded: {species_count}")
    print(f"   Routes loaded: {routes_count}")
    print(f"   Sample run created: {sample_run['run_name']}")
    
    # Write configuration file for easy access
    config_file = project_root / "test_config.json"
    import json
    with open(config_file, 'w') as f:
        json.dump(sample_run, f, indent=2)
    
    print(f"   Configuration saved to: {config_file}")
    print("\n🎮 Ready for testing!")
    print("\nNext steps:")
    print("1. Start the FastAPI server: uvicorn src.soullink_tracker.main:app --host 127.0.0.1 --port 9000")
    print("2. Test API health: curl http://127.0.0.1:9000/health")
    print("3. View API docs: http://127.0.0.1:9000/docs")


if __name__ == "__main__":
    main()