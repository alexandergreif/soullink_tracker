#!/usr/bin/env python3
"""
SoulLink Tracker - Player Setup Script
Complete installation and setup script for players.

This script:
1. Installs Python dependencies for the event watcher
2. Downloads and configures DeSmuME Lua scripts
3. Sets up file monitoring and event processing
4. Configures connection to the admin server
5. Provides guided setup for DeSmuME integration
6. Starts the event watcher system

Usage:
    python player_setup.py [player_config.json]
    
The player_config.json file should contain:
    {
        "player_id": "uuid",
        "player_name": "Player Name", 
        "server_url": "https://tunnel-url.trycloudflare.com",
        "bearer_token": "jwt_token"
    }
"""

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

# Determine script location
script_path = Path(__file__).resolve()
if script_path.name == "setup.py":
    # Running from player package
    project_root = script_path.parent
    player_package_mode = True
else:
    # Running from main project
    project_root = script_path.parent.parent
    player_package_mode = False

sys.path.insert(0, str(project_root))


class PlayerSetupManager:
    """Complete setup and management for SoulLink Tracker player clients."""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.project_root = project_root
        self.player_package_mode = player_package_mode
        self.config_file = config_file
        self.player_config = {}
        
        # Process tracking
        self.watcher_process = None
        
        # Paths
        if self.player_package_mode:
            self.client_dir = self.project_root / "client"
            self.temp_dir = self.project_root / "temp"
            self.logs_dir = self.project_root / "logs"
        else:
            self.client_dir = self.project_root / "client"
            self.temp_dir = self.project_root / "temp"
            self.logs_dir = self.project_root / "logs"
        
        print("[PLAYER] SoulLink Tracker - Player Setup Manager")
        print("=" * 60)
        print(f"Mode: {'Package' if self.player_package_mode else 'Development'}")
        print(f"Location: {self.project_root}")
        print("=" * 60)
    
    async def run_complete_setup(self):
        """Run the complete player setup process."""
        try:
            # Step 1: Load or create player configuration
            print("\\n[STEP 1] Loading player configuration...")
            await self.load_player_config()
            
            # Step 2: Check system requirements
            print("\\n[STEP 2] Checking system requirements...")
            await self.check_system_requirements()
            
            # Step 3: Install dependencies
            print("\\n[STEP 3] Installing dependencies...")
            await self.install_dependencies()
            
            # Step 4: Setup directories
            print("\\n[STEP 4] Setting up directories...")
            await self.setup_directories()
            
            # Step 5: Download/setup client files
            print("\\n📥 Step 5: Setting up client files...")
            await self.setup_client_files()
            
            # Step 6: Configure connections
            print("\\n🔗 Step 6: Testing server connection...")
            await self.test_server_connection()
            
            # Step 7: Generate player-specific configs
            print("\\n[STEP 7] Generating configurations...")
            await self.generate_player_configs()
            
            # Step 8: Setup DeSmuME integration
            print("\\n[STEP 8] Setting up DeSmuME integration...")
            await self.setup_desmume_integration()
            
            # Step 9: Start event watcher
            print("\\n[STEP 9] Starting event watcher...")
            await self.start_event_watcher()
            
            # Step 10: Open dashboard and provide instructions
            print("\\n[STEP 10] Opening player dashboard...")
            await self.open_player_dashboard()
            
            # Step 11: Monitor and manage
            print("\\n[STEP 11] Monitoring system...")
            await self.monitor_system()
            
        except KeyboardInterrupt:
            print("\\n\\n🛑 Shutting down player setup...")
            await self.cleanup()
        except Exception as e:
            print(f"\\n[ERROR] Error during player setup: {e}")
            await self.cleanup()
            sys.exit(1)
    
    async def load_player_config(self):
        """Load or create player configuration."""
        if self.config_file and self.config_file.exists():
            print(f"  - Loading config from: {self.config_file}")
            with open(self.config_file, 'r') as f:
                self.player_config = json.load(f)
        else:
            # Look for config in current directory (package mode)
            config_files = list(self.project_root.glob("*config*.json"))
            if config_files and self.player_package_mode:
                config_file = config_files[0]
                print(f"  - Found config file: {config_file.name}")
                with open(config_file, 'r') as f:
                    self.player_config = json.load(f)
            else:
                # Interactive configuration
                print("  - No configuration file found, creating interactive setup...")
                await self.create_interactive_config()
        
        # Validate required fields
        required_fields = ["player_id", "player_name", "server_url", "bearer_token"]
        missing_fields = [field for field in required_fields if field not in self.player_config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")
        
        print(f"  [OK] Player: {self.player_config['player_name']}")
        print(f"  [SERVER] Server: {self.player_config['server_url']}")
    
    async def create_interactive_config(self):
        """Create player configuration interactively."""
        print("\\n[CONFIG] Interactive Player Configuration")
        print("-" * 40)
        
        self.player_config["player_name"] = input("Enter your player name: ").strip()
        self.player_config["server_url"] = input("Enter server URL: ").strip()
        self.player_config["bearer_token"] = input("Enter your bearer token: ").strip()
        
        # Generate player ID if not provided
        import uuid
        self.player_config["player_id"] = str(uuid.uuid4())
        
        # Save configuration
        config_file = self.project_root / "player_config.json"
        with open(config_file, 'w') as f:
            json.dump(self.player_config, f, indent=2)
        
        print(f"  [OK] Configuration saved to: {config_file.name}")
    
    async def check_system_requirements(self):
        """Check system requirements for the player setup."""
        print("  - Checking Python version...")
        if sys.version_info < (3, 8):
            raise RuntimeError(f"Python 3.8+ required, found {sys.version}")
        print(f"  [OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        
        print("  - Checking operating system...")
        os_name = platform.system()
        print(f"  [OK] Operating System: {os_name} {platform.release()}")
        
        print("  - Checking available disk space...")
        total, used, free = shutil.disk_usage(self.project_root)
        free_mb = free // (1024**2)
        if free_mb < 100:
            print(f"  [WARNING] Low disk space: {free_mb}MB available")
        else:
            print(f"  [OK] Disk space: {free_mb}MB available")
        
        print("  - Checking network connectivity...")
        try:
            urllib.request.urlopen(self.player_config["server_url"] + "/health", timeout=5)
            print("  [OK] Server connectivity")
        except Exception as e:
            print(f"  [WARNING] Server connectivity issue: {e}")
            print("  [RETRY] Will retry connection during setup...")
        
        print("  - Checking for DeSmuME...")
        desmume_found = self.find_desmume_installation()
        if desmume_found:
            print(f"  [OK] DeSmuME found: {desmume_found}")
        else:
            print("  [WARNING] DeSmuME not found in standard locations")
            print("  📥 Will provide download instructions...")
    
    def find_desmume_installation(self) -> Optional[str]:
        """Find DeSmuME installation on the system."""
        common_paths = []
        
        if platform.system() == "Windows":
            common_paths = [
                "C:\\\\Program Files\\\\DeSmuME\\\\DeSmuME.exe",
                "C:\\\\Program Files (x86)\\\\DeSmuME\\\\DeSmuME.exe",
                "C:\\\\DeSmuME\\\\DeSmuME.exe"
            ]
        elif platform.system() == "Darwin":  # macOS
            common_paths = [
                "/Applications/DeSmuME.app",
                "/Applications/Games/DeSmuME.app",
                "~/Applications/DeSmuME.app"
            ]
        elif platform.system() == "Linux":
            common_paths = [
                "/usr/bin/desmume",
                "/usr/local/bin/desmume",
                "~/.local/bin/desmume"
            ]
        
        for path in common_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                return str(expanded_path)
        
        # Check PATH
        desmume_cmd = shutil.which("desmume") or shutil.which("DeSmuME")
        if desmume_cmd:
            return desmume_cmd
        
        return None
    
    async def install_dependencies(self):
        """Install Python dependencies for the event watcher."""
        print("  - Installing Python packages...")
        
        # Upgrade pip first
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        
        # Required packages for player client
        required_packages = [
            "aiohttp>=3.8.0",
            "requests>=2.28.0", 
            "watchdog>=2.1.0",
            "aiofiles>=0.8.0",
            "pydantic>=1.10.0"
        ]
        
        for package in required_packages:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", package, "--quiet"], 
                              check=True, capture_output=True)
                print(f"    [OK] {package.split('>=')[0]}")
            except subprocess.CalledProcessError as e:
                print(f"    [ERROR] Failed to install {package}: {e}")
                raise
        
        print("  [OK] All Python dependencies installed")
    
    async def setup_directories(self):
        """Create necessary directories."""
        directories = [
            self.temp_dir,
            self.temp_dir / "events",
            self.logs_dir,
            self.client_dir / "lua" / "configs",
            self.client_dir / "watcher" / "configs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  [OK] Created: {directory.relative_to(self.project_root)}")
    
    async def setup_client_files(self):
        """Setup or download client files."""
        if self.player_package_mode:
            print("  - Client files included in package")
            
            # Verify required files exist
            required_files = [
                "client/lua/pokemon_tracker.lua",
                "client/lua/memory_addresses.lua", 
                "client/lua/config_template.lua",
                "client/watcher/event_watcher.py",
                "client/watcher/player_config.py"
            ]
            
            missing_files = []
            for file_path in required_files:
                full_path = self.project_root / file_path
                if not full_path.exists():
                    missing_files.append(file_path)
            
            if missing_files:
                print(f"  [ERROR] Missing client files: {missing_files}")
                await self.download_client_files()
            else:
                print("  [OK] All client files present")
        else:
            print("  - Using client files from project directory")
    
    async def download_client_files(self):
        """Download missing client files from repository."""
        base_url = "https://raw.githubusercontent.com/anthropics/soullink-tracker/main"
        
        required_files = [
            "client/lua/pokemon_tracker.lua",
            "client/lua/memory_addresses.lua",
            "client/lua/config_template.lua", 
            "client/watcher/event_watcher.py",
            "client/watcher/player_config.py",
            "client/watcher/requirements.txt"
        ]
        
        print("  - Downloading client files...")
        for file_path in required_files:
            url = f"{base_url}/{file_path}"
            local_path = self.project_root / file_path
            
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, local_path)
                print(f"    [OK] Downloaded: {file_path}")
            except Exception as e:
                print(f"    [ERROR] Failed to download {file_path}: {e}")
                # Create minimal fallback if critical file
                if "event_watcher.py" in file_path:
                    await self.create_fallback_watcher()
    
    async def create_fallback_watcher(self):
        """Create a minimal fallback event watcher."""
        fallback_content = '''#!/usr/bin/env python3
"""
Fallback Event Watcher - Minimal Implementation
This is a basic implementation that can be replaced with the full version.
"""

import asyncio
import json
import sys
from pathlib import Path

async def main():
    print("[WARNING] Using fallback event watcher")
    print("Please contact admin for full client files")
    
    # Basic event monitoring loop
    while True:
        await asyncio.sleep(10)
        print("Monitoring for events...")

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        watcher_path = self.client_dir / "watcher" / "event_watcher.py"
        watcher_path.parent.mkdir(parents=True, exist_ok=True)
        with open(watcher_path, 'w') as f:
            f.write(fallback_content)
        print("    [OK] Created fallback event watcher")
    
    async def test_server_connection(self):
        """Test connection to the admin server."""
        import requests
        
        server_url = self.player_config["server_url"]
        bearer_token = self.player_config["bearer_token"]
        
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        
        # Test health endpoint
        print(f"  - Testing connection to: {server_url}")
        try:
            response = requests.get(f"{server_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"  [OK] Server health: {health_data.get('service')} v{health_data.get('version')}")
            else:
                print(f"  [WARNING] Health check returned status {response.status_code}")
        except Exception as e:
            print(f"  [ERROR] Health check failed: {e}")
            raise ConnectionError(f"Cannot connect to server: {e}")
        
        # Test authenticated endpoint
        print("  - Testing authentication...")
        try:
            response = requests.get(f"{server_url}/v1/runs", headers=headers, timeout=10)
            if response.status_code == 200:
                runs = response.json()
                print(f"  [OK] Authentication successful, {len(runs)} runs available")
                self.available_runs = runs
            elif response.status_code == 401:
                print("  [ERROR] Authentication failed - invalid token")
                raise ValueError("Invalid bearer token")
            else:
                print(f"  [WARNING] Auth test returned status {response.status_code}")
        except Exception as e:
            if "Invalid bearer token" in str(e):
                raise
            print(f"  [ERROR] Auth test failed: {e}")
    
    async def generate_player_configs(self):
        """Generate player-specific configuration files."""
        player_name = self.player_config["player_name"]
        player_id = self.player_config["player_id"]
        server_url = self.player_config["server_url"]
        bearer_token = self.player_config["bearer_token"]
        
        # Generate watcher configuration
        watcher_config = {
            "player_id": player_id,
            "player_name": player_name,
            "api_base_url": server_url,
            "bearer_token": bearer_token,
            "watch_directory": str(self.temp_dir / "events"),
            "log_file": str(self.logs_dir / f"{player_name.lower()}_watcher.log"),
            "polling_interval": 1.0,
            "batch_size": 10,
            "retry_attempts": 3,
            "retry_delay": 5.0
        }
        
        watcher_config_file = self.client_dir / "watcher" / "configs" / f"{player_name.lower()}_config.json"
        with open(watcher_config_file, 'w') as f:
            json.dump(watcher_config, f, indent=2)
        
        print(f"  [OK] Watcher config: {watcher_config_file.name}")
        
        # Generate Lua configuration
        lua_config_content = f'''-- SoulLink Tracker - {player_name} Configuration
-- Auto-generated player configuration for DeSmuME Lua scripting

config = {{
    player_id = "{player_id}",
    player_name = "{player_name}",
    output_directory = "{str(self.temp_dir / 'events').replace(chr(92), '/')}", 
    log_file = "{str(self.logs_dir / f'{player_name.lower()}_lua.log').replace(chr(92), '/')}",
    
    -- Event detection settings
    detection_interval = 100,  -- milliseconds
    memory_validation = true,
    auto_save = true,
    
    -- ROM region (adjust based on your ROM)
    rom_region = "US",  -- US, EU, JP
    
    -- Debug settings
    debug_mode = false,
    verbose_logging = false
}}

-- Load main tracker with this configuration
dofile("{str(self.client_dir / 'lua' / 'pokemon_tracker.lua').replace(chr(92), '/')}")
'''
        
        lua_config_file = self.client_dir / "lua" / "configs" / f"{player_name.lower()}_config.lua"
        with open(lua_config_file, 'w') as f:
            f.write(lua_config_content)
        
        print(f"  [OK] Lua config: {lua_config_file.name}")
        
        # Store paths for later use
        self.watcher_config_file = watcher_config_file
        self.lua_config_file = lua_config_file
    
    async def setup_desmume_integration(self):
        """Setup DeSmuME integration and provide instructions."""
        desmume_path = self.find_desmume_installation()
        
        if desmume_path:
            print(f"  [OK] DeSmuME found at: {desmume_path}")
        else:
            print("  📥 DeSmuME not found - providing download instructions...")
            self.show_desmume_download_instructions()
        
        print("  📋 DeSmuME setup instructions:")
        print(f"     1. Open DeSmuME emulator")
        print(f"     2. Load your Pokemon HeartGold/SoulSilver ROM")
        print(f"     3. Open Tools → Lua Script Console")
        print(f"     4. Load script: {self.lua_config_file}")
        print(f"     5. Start playing - events will be automatically tracked!")
    
    def show_desmume_download_instructions(self):
        """Show download instructions for DeSmuME."""
        os_name = platform.system()
        
        print("\\n" + "=" * 50)
        print("📥 DESMUME DOWNLOAD INSTRUCTIONS")
        print("=" * 50)
        
        if os_name == "Windows":
            print("For Windows:")
            print("1. Visit: https://desmume.org/download/")
            print("2. Download the latest Windows version")
            print("3. Extract to C:\\\\DeSmuME\\\\")
            print("4. Run DeSmuME.exe")
        elif os_name == "Darwin":  # macOS
            print("For macOS:")
            print("1. Visit: https://desmume.org/download/")
            print("2. Download the macOS version")
            print("3. Install to /Applications/")
        elif os_name == "Linux":
            print("For Linux:")
            print("1. Install via package manager:")
            print("   Ubuntu/Debian: sudo apt install desmume")
            print("   Fedora: sudo dnf install desmume")
            print("   Arch: sudo pacman -S desmume")
            print("2. Or build from source: https://github.com/TASVideos/desmume")
        
        print("\\n💡 Make sure to use a compatible Pokemon HG/SS ROM!")
        print("=" * 50)
    
    async def start_event_watcher(self):
        """Start the event watcher process."""
        watcher_script = self.client_dir / "watcher" / "event_watcher.py"
        
        if not watcher_script.exists():
            print("  [ERROR] Event watcher script not found")
            return
        
        print("  - Starting event watcher...")
        
        cmd = [
            sys.executable,
            str(watcher_script),
            str(self.watcher_config_file)
        ]
        
        self.watcher_process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment to check if it started successfully
        await asyncio.sleep(2)
        
        if self.watcher_process.poll() is None:
            print(f"  [OK] Event watcher started (PID: {self.watcher_process.pid})")
        else:
            stdout, stderr = self.watcher_process.communicate()
            print(f"  [ERROR] Event watcher failed to start:")
            print(f"     stdout: {stdout}")
            print(f"     stderr: {stderr}")
    
    async def open_player_dashboard(self):
        """Open the player dashboard and show important information."""
        if hasattr(self, 'available_runs') and self.available_runs:
            # Use the first available run
            run_id = self.available_runs[0]['id']
            dashboard_url = f"{self.player_config['server_url']}/dashboard?run={run_id}"
        else:
            dashboard_url = f"{self.player_config['server_url']}/docs"
        
        print(f"  - Opening dashboard: {dashboard_url}")
        
        try:
            webbrowser.open(dashboard_url)
            print("  [OK] Dashboard opened in browser")
        except Exception as e:
            print(f"  [WARNING] Could not open dashboard: {e}")
            print(f"  🔗 Open manually: {dashboard_url}")
        
        # Show player summary
        self.show_player_summary()
    
    def show_player_summary(self):
        """Show comprehensive player setup summary."""
        print("\\n" + "=" * 70)
        print("[COMPLETE] SOULLINK TRACKER - PLAYER SETUP COMPLETE")
        print("=" * 70)
        
        print(f"\\n👤 Player Information:")
        print(f"   Name: {self.player_config['player_name']}")
        print(f"   ID: {self.player_config['player_id']}")
        print(f"   Server: {self.player_config['server_url']}")
        
        print(f"\\n[FILES] Configuration Files:")
        print(f"   Watcher config: {self.watcher_config_file}")
        print(f"   Lua config: {self.lua_config_file}")
        
        print(f"\\n[DESMUME] DeSmuME Setup:")
        print(f"   1. Open DeSmuME")
        print(f"   2. Load Pokemon HG/SS ROM")
        print(f"   3. Tools → Lua Script Console")
        print(f"   4. Load: {self.lua_config_file}")
        
        print(f"\\n[MONITOR] Monitoring:")
        print(f"   Event watcher: {'Running' if self.watcher_process and self.watcher_process.poll() is None else 'Stopped'}")
        player_name_lower = self.player_config['player_name'].lower()
        print(f"   Log file: {self.logs_dir / f'{player_name_lower}_watcher.log'}")
        print(f"   Events dir: {self.temp_dir / 'events'}")
        
        print(f"\\n[DASHBOARD] Web Dashboard:")
        if hasattr(self, 'available_runs') and self.available_runs:
            run_id = self.available_runs[0]['id'] 
            dashboard_url = f"{self.player_config['server_url']}/dashboard?run={run_id}"
            print(f"   URL: {dashboard_url}")
        else:
            print(f"   URL: {self.player_config['server_url']}/docs")
        
        print(f"\\n[READY] Ready to Play!")
        print(f"   - Start playing Pokemon HG/SS in DeSmuME")
        print(f"   - Events will be automatically tracked")
        print(f"   - Monitor dashboard for real-time updates")
        print(f"   - Press Ctrl+C in this window to stop monitoring")
        
        print("\\n" + "=" * 70)
    
    async def monitor_system(self):
        """Monitor the event watcher and provide status updates."""
        print("\\n[MONITOR] System monitoring started (Ctrl+C to stop)...")
        
        last_status_time = time.time()
        
        try:
            while True:
                # Check watcher process
                if self.watcher_process:
                    if self.watcher_process.poll() is None:
                        # Process is running
                        current_time = time.time()
                        if current_time - last_status_time > 60:  # Status update every minute
                            print(f"[OK] Event watcher running (PID: {self.watcher_process.pid})")
                            last_status_time = current_time
                    else:
                        print("[ERROR] Event watcher process has stopped")
                        stdout, stderr = self.watcher_process.communicate()
                        if stderr:
                            print(f"Error output: {stderr}")
                        
                        # Attempt to restart
                        print("[RESTART] Attempting to restart event watcher...")
                        await self.start_event_watcher()
                
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            print("\\n🛑 Shutdown requested by player...")
            raise
    
    async def cleanup(self):
        """Clean up processes and resources."""
        print("[CLEANUP] Cleaning up player setup...")
        
        # Stop watcher process
        if self.watcher_process:
            print("  - Stopping event watcher...")
            self.watcher_process.terminate()
            try:
                self.watcher_process.wait(timeout=5)
                print("  [OK] Event watcher stopped")
            except subprocess.TimeoutExpired:
                print("  [WARNING] Force killing event watcher...")
                self.watcher_process.kill()
        
        print("[COMPLETE] Player cleanup complete")
        print("👋 Thank you for playing SoulLink!")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SoulLink Tracker Player Setup")
    parser.add_argument("config", nargs="?", help="Player configuration file")
    parser.add_argument("--interactive", action="store_true", help="Force interactive configuration")
    
    args = parser.parse_args()
    
    # Determine config file
    config_file = None
    if args.config:
        config_file = Path(args.config)
        if not config_file.exists():
            print(f"[ERROR] Configuration file not found: {config_file}")
            sys.exit(1)
    
    # Create manager
    manager = PlayerSetupManager(config_file=config_file)
    
    # Show welcome message
    print("\\n[WELCOME] Welcome to SoulLink Tracker Player Setup!")
    print("This will set up everything you need to participate in a SoulLink run.")
    
    if not config_file and not args.interactive:
        print("\\n💡 Looking for configuration file...")
        # Try to find config in current directory
        config_files = list(Path.cwd().glob("*config*.json"))
        if config_files:
            config_file = config_files[0]
            print(f"[CONFIG] Found config: {config_file.name}")
            manager.config_file = config_file
    
    # Run setup
    await manager.run_complete_setup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Player setup cancelled!")
    except Exception as e:
        print(f"\\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)