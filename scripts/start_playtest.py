#!/usr/bin/env python3
"""
SoulLink Tracker - Playtest Startup Script
Automated script to prepare and start all components for a SoulLink playtest.

This script:
1. Initializes the database with sample data
2. Creates player configurations
3. Starts the API server
4. Opens the web dashboard
5. Provides instructions for manual components (DeSmuME, watchers)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from client.watcher.player_config import PlayerConfigManager


class PlaytestManager:
    """Manages the startup and coordination of playtest components."""
    
    def __init__(self):
        self.project_root = project_root
        self.api_url = "http://127.0.0.1:9000"
        self.api_process = None
        self.watcher_processes = []
        
        # Paths
        self.scripts_dir = self.project_root / "scripts"
        self.client_dir = self.project_root / "client"
        self.web_dir = self.project_root / "web"
        
        print("[PLAYTEST] SoulLink Tracker - Playtest Manager")
        print("=" * 50)
    
    async def run_playtest_setup(self):
        """Run the complete playtest setup process."""
        try:
            # Step 1: Initialize database
            print("\n📊 Step 1: Initializing database...")
            await self.initialize_database()
            
            # Step 2: Create player configurations
            print("\n[STEP 2] Creating player configurations...")
            await self.create_player_configs()
            
            # Step 3: Start API server
            print("\n[STEP 3] Starting API server...")
            await self.start_api_server()
            
            # Step 4: Open web dashboard
            print("\n🌐 Step 4: Opening web dashboard...")
            await self.open_dashboard()
            
            # Step 5: Provide manual setup instructions
            print("\n📋 Step 5: Manual setup instructions")
            self.show_manual_instructions()
            
            # Step 6: Monitor and manage processes
            print("\n👀 Step 6: Monitoring components...")
            await self.monitor_components()
            
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down playtest...")
            await self.cleanup()
        except Exception as e:
            print(f"\n[ERROR] Error during playtest setup: {e}")
            await self.cleanup()
            sys.exit(1)
    
    async def initialize_database(self):
        """Initialize the database with sample data."""
        init_script = self.scripts_dir / "init_database.py"
        
        if not init_script.exists():
            raise FileNotFoundError(f"Database initialization script not found: {init_script}")
        
        print("  - Running database initialization...")
        result = subprocess.run([
            sys.executable, str(init_script)
        ], capture_output=True, text=True, cwd=self.project_root)
        
        if result.returncode != 0:
            print(f"[ERROR] Database initialization failed:")
            print(result.stderr)
            raise RuntimeError("Database initialization failed")
        
        print("  [OK] Database initialized successfully")
        
        # Load the generated config
        config_file = self.project_root / "test_config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.db_config = json.load(f)
            print(f"  📋 Created run: {self.db_config['run_name']}")
            print(f"  👥 Players: {', '.join([p['name'] for p in self.db_config['players']])}")
        else:
            raise FileNotFoundError("Database config file not created")
    
    async def create_player_configs(self):
        """Create player configuration files."""
        try:
            config_manager = PlayerConfigManager(self.project_root)
            
            print("  - Creating watcher configurations...")
            watcher_configs = config_manager.create_watcher_configs(
                api_base_url=self.api_url,
                watch_base_dir=str(self.project_root / "temp" / "events")
            )
            
            print("  - Creating Lua configurations...")
            lua_configs = config_manager.create_lua_configs()
            
            print(f"  [OK] Created {len(watcher_configs)} watcher configs")
            print(f"  [OK] Created {len(lua_configs)} Lua configs")
            
            # Store config paths for later use
            self.watcher_configs = watcher_configs
            self.lua_configs = lua_configs
            
        except Exception as e:
            print(f"[ERROR] Failed to create player configs: {e}")
            raise
    
    async def start_api_server(self):
        """Start the FastAPI server."""
        print("  - Starting FastAPI server...")
        
        # Check if uvicorn is available
        try:
            import uvicorn
        except ImportError:
            print("[ERROR] uvicorn not found. Install with: pip install uvicorn")
            raise
        
        # Start server in subprocess
        cmd = [
            sys.executable, "-m", "uvicorn",
            "src.soullink_tracker.main:app",
            "--host", "127.0.0.1",
            "--port", "9000",
            "--reload"
        ]
        
        print(f"  - Command: {' '.join(cmd)}")
        
        self.api_process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        print("  - Waiting for server to start...")
        for attempt in range(30):  # Wait up to 30 seconds
            try:
                import requests
                response = requests.get(f"{self.api_url}/health", timeout=1)
                if response.status_code == 200:
                    print("  [OK] API server started successfully")
                    server_info = response.json()
                    print(f"     Service: {server_info.get('service', 'unknown')}")
                    print(f"     Version: {server_info.get('version', 'unknown')}")
                    return
            except:
                pass
            
            await asyncio.sleep(1)
        
        # Check if process is still running
        if self.api_process.poll() is not None:
            stdout, stderr = self.api_process.communicate()
            print(f"[ERROR] API server failed to start:")
            print(f"stdout: {stdout}")
            print(f"stderr: {stderr}")
            raise RuntimeError("API server failed to start")
        
        print("[WARNING] API server may not be fully ready yet")
    
    async def open_dashboard(self):
        """Open the web dashboard in the default browser."""
        dashboard_url = f"{self.api_url}/dashboard?run={self.db_config['run_id']}"
        
        print(f"  - Opening dashboard: {dashboard_url}")
        
        try:
            webbrowser.open(dashboard_url)
            print("  [OK] Dashboard opened in browser")
        except Exception as e:
            print(f"  [WARNING] Could not open browser automatically: {e}")
            print(f"  🔗 Please open manually: {dashboard_url}")
    
    def show_manual_instructions(self):
        """Show instructions for manual setup components."""
        print("\n" + "="*60)
        print("📋 MANUAL SETUP INSTRUCTIONS")
        print("="*60)
        
        print("\n[DESMUME] DeSmuME Setup (for each player):")
        print("1. Open DeSmuME emulator")
        print("2. Load Pokemon HeartGold/SoulSilver ROM")
        print("3. Open Tools → Lua Script Console")
        print("4. Load the appropriate config file:")
        
        for i, lua_config in enumerate(self.lua_configs, 1):
            player_name = self.db_config['players'][i-1]['name'] if i <= len(self.db_config['players']) else f"Player{i}"
            print(f"   Player {i} ({player_name}): {lua_config}")
        
        print("\n🔄 Python Watcher Setup (for each player):")
        print("Run these commands in separate terminals:")
        
        for i, watcher_config in enumerate(self.watcher_configs, 1):
            player_name = self.db_config['players'][i-1]['name'] if i <= len(self.db_config['players']) else f"Player{i}"
            print(f"\n   Player {i} ({player_name}):")
            print(f"   cd {self.project_root}")
            print(f"   python client/watcher/event_watcher.py {watcher_config}")
        
        print(f"\n🌐 Web Dashboard:")
        print(f"   URL: {self.api_url}/dashboard?run={self.db_config['run_id']}")
        
        print(f"\n📊 API Documentation:")
        print(f"   URL: {self.api_url}/docs")
        
        print("\n🔧 Quick Test Commands:")
        print(f"   Health check: curl {self.api_url}/health")
        print(f"   View run: curl {self.api_url}/v1/runs/{self.db_config['run_id']}")
        
        print("\n" + "="*60)
        print("Ready for playtest! Press Ctrl+C to shutdown all components.")
        print("="*60)
    
    async def monitor_components(self):
        """Monitor running components and handle shutdown."""
        try:
            while True:
                # Check API server
                if self.api_process and self.api_process.poll() is not None:
                    print("[WARNING] API server process has stopped")
                    break
                
                # Could add health checks here
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            raise
    
    async def cleanup(self):
        """Clean up all processes and resources."""
        print("🧹 Cleaning up components...")
        
        # Stop API server
        if self.api_process:
            print("  - Stopping API server...")
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=5)
                print("  [OK] API server stopped")
            except subprocess.TimeoutExpired:
                print("  [WARNING] API server did not stop gracefully, killing...")
                self.api_process.kill()
        
        # Stop watcher processes (if we started any)
        for process in self.watcher_processes:
            if process and process.poll() is None:
                process.terminate()
        
        print("🏁 Cleanup complete")
    
    def get_system_info(self):
        """Get system information for troubleshooting."""
        info = {
            "python_version": sys.version,
            "project_root": str(self.project_root),
            "api_url": self.api_url,
            "platform": sys.platform
        }
        
        # Check dependencies
        try:
            import uvicorn
            info["uvicorn_version"] = uvicorn.__version__
        except ImportError:
            info["uvicorn_version"] = "NOT INSTALLED"
        
        try:
            import fastapi
            info["fastapi_version"] = fastapi.__version__
        except ImportError:
            info["fastapi_version"] = "NOT INSTALLED"
        
        return info


async def main():
    """Main entry point."""
    manager = PlaytestManager()
    
    # Show system info
    print("\n🔍 System Information:")
    for key, value in manager.get_system_info().items():
        print(f"   {key}: {value}")
    
    # Validate prerequisites
    print("\n[CHECK] Checking prerequisites...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("[ERROR] Python 3.9+ required")
        sys.exit(1)
    
    # Check required packages
    missing_packages = []
    for package in ["fastapi", "uvicorn", "sqlalchemy", "aiohttp"]:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"[ERROR] Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        sys.exit(1)
    
    print("[OK] All prerequisites met")
    
    # Start playtest setup
    await manager.run_playtest_setup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)