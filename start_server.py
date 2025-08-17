#!/usr/bin/env python3
"""
Simple SoulLink Tracker Server Startup Script

This script starts the SoulLink Tracker server with all necessary initialization.
No portable mode, no complex build process - just a simple server.
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path
import time


def setup_environment():
    """Setup the Python path and environment."""
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Set environment variables for development
    os.environ["SOULLINK_DEBUG"] = "true"
    os.environ["SOULLINK_DEV_MODE"] = "true"


def run_migrations():
    """Run database migrations to ensure schema is up to date."""
    print("🔧 Running database migrations...")
    try:
        subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], check=True, capture_output=True, text=True)
        print("✅ Database migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False


def load_reference_data():
    """Load routes and species data if needed."""
    print("📊 Loading reference data...")
    try:
        # Import after setting up the path
        from soullink_tracker.db.database import get_db
        from soullink_tracker.db.models import Route, Species
        import csv
        
        db = next(get_db())
        
        # Check if data already exists
        if db.query(Route).count() > 0 and db.query(Species).count() > 0:
            print("✅ Reference data already loaded")
            return True
            
        # Load routes
        routes_file = Path("data/routes.csv")
        if routes_file.exists():
            with open(routes_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    route = Route(
                        id=int(row['id']),
                        label=row['label'],
                        region=row['region']
                    )
                    db.merge(route)
            
        # Load species
        species_file = Path("data/species.csv")
        if species_file.exists():
            with open(species_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    species = Species(
                        id=int(row['id']),
                        name=row['name'],
                        family_id=int(row['family_id'])
                    )
                    db.merge(species)
        
        db.commit()
        print("✅ Reference data loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to load reference data: {e}")
        return False


def start_server():
    """Start the FastAPI server using uvicorn."""
    print("🚀 Starting SoulLink Tracker server...")
    print("📍 Server will be available at: http://127.0.0.1:8000")
    print("🔧 Admin panel: http://127.0.0.1:8000/admin")
    print("📊 Dashboard: http://127.0.0.1:8000/dashboard")
    print("📖 API docs: http://127.0.0.1:8000/docs")
    print("")
    print("📋 To create runs and players, use the admin panel in your browser")
    print("🔑 Players need: run name + player name + run password for their watchers")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Give a moment for user to read the output
        time.sleep(1)
        
        # Auto-open admin panel in browser
        webbrowser.open("http://127.0.0.1:8000/admin")
        
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "soullink_tracker.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"  # Auto-restart on code changes
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return False
    
    return True


def main():
    """Main entry point."""
    print("🎮 SoulLink Tracker - Server Startup")
    print("=" * 40)
    
    # Setup environment
    setup_environment()
    
    # Run migrations
    if not run_migrations():
        print("❌ Cannot start server without database migrations")
        sys.exit(1)
    
    # Load reference data
    if not load_reference_data():
        print("⚠️  Server will start but reference data may be missing")
    
    # Start server
    if not start_server():
        sys.exit(1)


if __name__ == "__main__":
    main()