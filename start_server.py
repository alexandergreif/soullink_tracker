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
    # Add src to Python path - critical for module imports
    project_root = Path(__file__).parent.absolute()
    src_path = project_root / "src"
    
    # Ensure src path exists
    if not src_path.exists():
        print(f"❌ Error: src directory not found at {src_path}")
        print("Make sure you're running this script from the project root directory")
        sys.exit(1)
    
    # Add to Python path if not already there
    src_str = str(src_path)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
        print(f"✅ Added {src_str} to Python path")
    
    # Also set PYTHONPATH environment variable for subprocesses
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    if src_str not in current_pythonpath:
        if current_pythonpath:
            os.environ["PYTHONPATH"] = f"{src_str}{os.pathsep}{current_pythonpath}"
        else:
            os.environ["PYTHONPATH"] = src_str
        print(f"✅ Set PYTHONPATH environment variable")
    
    # Set environment variables for development
    os.environ["SOULLINK_DEBUG"] = "true"
    os.environ["SOULLINK_DEV_MODE"] = "true"
    
    print(f"📁 Project root: {project_root}")
    print(f"📁 Source path: {src_path}")
    print(f"🐍 Python executable: {sys.executable}")
    print(f"🔗 Python path includes: {[p for p in sys.path if 'soullink' in p or 'src' in p]}")
    
    # Verify module can be imported
    try:
        import soullink_tracker
        print("✅ soullink_tracker module can be imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import soullink_tracker: {e}")
        print("🔍 Current Python path:")
        for i, path in enumerate(sys.path):
            print(f"  {i}: {path}")
        sys.exit(1)


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
        
        # Start the server with explicit environment
        env = os.environ.copy()
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "soullink_tracker.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"  # Auto-restart on code changes
        ], check=True, env=env)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return False
    
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'alembic', 
        'pydantic', 'python-jose', 'passlib', 'python-multipart'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            try:
                # Some packages have different import names
                import_map = {
                    'python-jose': 'jose',
                    'python-multipart': 'multipart'
                }
                actual_name = import_map.get(package, package)
                __import__(actual_name)
            except ImportError:
                missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nTo install missing packages, run:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\nOr install all requirements:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ All required dependencies are installed")
    return True


def main():
    """Main entry point."""
    print("🎮 SoulLink Tracker - Server Startup")
    print("=" * 40)
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        print("❌ Cannot start server without required dependencies")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        print("❌ Cannot start server without database migrations")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Load reference data
    if not load_reference_data():
        print("⚠️  Server will start but reference data may be missing")
    
    # Start server
    if not start_server():
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()