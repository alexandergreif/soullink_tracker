#!/usr/bin/env python3
"""
SoulLink Tracker - Admin Setup Script
Complete installation and setup script for administrators.

This script:
1. Checks system requirements and dependencies
2. Installs Python dependencies 
3. Sets up the database
4. Configures networking (Cloudflare tunnel)
5. Starts the complete server stack
6. Provides monitoring and management tools

Usage:
    python scripts/admin_setup.py [--dev] [--production] [--tunnel-only]
    
Options:
    --dev           Development mode (local only)
    --production    Production mode (with tunnel)
    --tunnel-only   Only setup Cloudflare tunnel
    --reset         Reset database and configs
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

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))


class AdminSetupManager:
    """Complete setup and management for SoulLink Tracker admin deployment."""
    
    def __init__(self, mode: str = "dev"):
        self.project_root = project_root
        self.mode = mode  # dev, production
        self.api_port = 9000
        self.api_url = f"http://127.0.0.1:{self.api_port}"
        self.tunnel_url = None
        
        # Process tracking
        self.api_process = None
        self.tunnel_process = None
        
        # Paths
        self.scripts_dir = self.project_root / "scripts"
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.project_root / "logs"
        self.temp_dir = self.project_root / "temp"
        
        # Config files
        self.admin_config_file = self.project_root / "admin_config.json"
        self.tunnel_config_file = self.project_root / "tunnel_config.json"
        
        print("🔧 SoulLink Tracker - Admin Setup Manager")
        print("=" * 60)
        print(f"Mode: {self.mode.upper()}")
        print(f"Project root: {self.project_root}")
        print("=" * 60)
    
    async def run_complete_setup(self, reset: bool = False):
        """Run the complete admin setup process."""
        try:
            if reset:
                print("\n🗑️ Resetting previous configuration...")
                await self.reset_configuration()
            
            # Step 1: System requirements check
            print("\n🔍 Step 1: Checking system requirements...")
            await self.check_system_requirements()
            
            # Step 2: Install dependencies
            print("\n📦 Step 2: Installing dependencies...")
            await self.install_dependencies()
            
            # Step 3: Setup directories and permissions
            print("\n📁 Step 3: Setting up directories...")
            await self.setup_directories()
            
            # Step 4: Initialize database
            print("\n🗄️ Step 4: Setting up database...")
            await self.setup_database()
            
            # Step 5: Configure networking
            if self.mode == "production":
                print("\n🌐 Step 5: Setting up networking (Cloudflare tunnel)...")
                await self.setup_networking()
            else:
                print("\n🌐 Step 5: Skipping tunnel setup (development mode)")
            
            # Step 6: Start services
            print("\n🚀 Step 6: Starting services...")
            await self.start_services()
            
            # Step 7: Generate admin tools and configs
            print("\n⚙️ Step 7: Generating admin configuration...")
            await self.generate_admin_configs()
            
            # Step 8: Run health checks
            print("\n❤️ Step 8: Running health checks...")
            await self.run_health_checks()
            
            # Step 9: Show admin dashboard
            print("\n📊 Step 9: Opening admin dashboard...")
            await self.open_admin_dashboard()
            
            # Step 10: Monitor services
            print("\n👀 Step 10: Monitoring services...")
            await self.monitor_services()
            
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down admin setup...")
            await self.cleanup()
        except Exception as e:
            print(f"\n❌ Error during admin setup: {e}")
            await self.cleanup()
            sys.exit(1)
    
    async def check_system_requirements(self):
        """Check system requirements and dependencies."""
        print("  - Checking Python version...")
        if sys.version_info < (3, 9):
            raise RuntimeError(f"Python 3.9+ required, found {sys.version}")
        print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        
        print("  - Checking operating system...")
        os_name = platform.system()
        print(f"  ✅ Operating System: {os_name} {platform.release()}")
        
        print("  - Checking available disk space...")
        total, used, free = shutil.disk_usage(self.project_root)
        free_gb = free // (1024**3)
        if free_gb < 1:
            print(f"  ⚠️ Low disk space: {free_gb}GB available")
        else:
            print(f"  ✅ Disk space: {free_gb}GB available")
        
        print("  - Checking network connectivity...")
        try:
            urllib.request.urlopen('https://google.com', timeout=5)
            print("  ✅ Internet connectivity")
        except:
            print("  ⚠️ Limited internet connectivity")
        
        print("  - Checking required commands...")
        required_commands = ["git", "python", "pip"]
        if self.mode == "production":
            required_commands.append("curl")
        
        missing_commands = []
        for cmd in required_commands:
            if not shutil.which(cmd):
                missing_commands.append(cmd)
        
        if missing_commands:
            raise RuntimeError(f"Missing required commands: {missing_commands}")
        
        print(f"  ✅ All required commands available: {required_commands}")
    
    async def install_dependencies(self):
        """Install Python dependencies."""
        print("  - Installing Python packages...")
        
        # Upgrade pip first
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        
        # Install main dependencies
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"], 
                      cwd=self.project_root, check=True)
        
        # Install development dependencies if in dev mode
        if self.mode == "dev":
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[dev]", "--quiet"], 
                          cwd=self.project_root, check=True)
        
        print("  ✅ Python dependencies installed")
        
        # Install Cloudflare tunnel if in production mode
        if self.mode == "production":
            print("  - Installing Cloudflare tunnel...")
            await self.install_cloudflare_tunnel()
    
    async def install_cloudflare_tunnel(self):
        """Install Cloudflare tunnel binary."""
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        # Map architecture names
        if arch in ["x86_64", "amd64"]:
            arch = "amd64"
        elif arch in ["arm64", "aarch64"]:
            arch = "arm64"
        else:
            raise RuntimeError(f"Unsupported architecture: {arch}")
        
        # Determine download URL
        if system == "windows":
            binary_name = f"cloudflared-windows-{arch}.exe"
            local_name = "cloudflared.exe"
        elif system == "darwin":
            binary_name = f"cloudflared-darwin-{arch}.tgz"
            local_name = "cloudflared"
        elif system == "linux":
            binary_name = f"cloudflared-linux-{arch}"
            local_name = "cloudflared"
        else:
            raise RuntimeError(f"Unsupported operating system: {system}")
        
        download_url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{binary_name}"
        binary_path = self.project_root / local_name
        
        if binary_path.exists():
            print("  ✅ Cloudflare tunnel already installed")
            return
        
        print(f"  - Downloading {binary_name}...")
        try:
            urllib.request.urlretrieve(download_url, binary_path)
            
            # Extract if tar.gz
            if binary_name.endswith('.tgz'):
                import tarfile
                with tarfile.open(binary_path, 'r:gz') as tar:
                    tar.extractall(self.project_root)
                binary_path.unlink()  # Remove tar file
                binary_path = self.project_root / "cloudflared"
            
            # Make executable on Unix systems
            if system != "windows":
                os.chmod(binary_path, 0o755)
            
            print("  ✅ Cloudflare tunnel installed")
            
        except Exception as e:
            raise RuntimeError(f"Failed to install Cloudflare tunnel: {e}")
    
    async def setup_directories(self):
        """Create necessary directories with proper permissions."""
        directories = [
            self.data_dir,
            self.logs_dir,
            self.temp_dir,
            self.temp_dir / "events",
            self.project_root / "client" / "lua" / "configs",
            self.project_root / "client" / "watcher" / "configs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  ✅ Created directory: {directory.relative_to(self.project_root)}")
        
        # Set up log rotation
        self.setup_log_rotation()
    
    def setup_log_rotation(self):
        """Set up log rotation configuration."""
        logrotate_config = """
# SoulLink Tracker log rotation
{logs_dir}/*.log {{
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644
    maxage 30
}}
        """.format(logs_dir=self.logs_dir)
        
        logrotate_file = self.project_root / "logrotate.conf"
        logrotate_file.write_text(logrotate_config.strip())
        print(f"  ✅ Log rotation configured: {logrotate_file.relative_to(self.project_root)}")
    
    async def setup_database(self):
        """Initialize and configure the database."""
        print("  - Initializing database...")
        
        # Run database initialization script
        init_script = self.scripts_dir / "init_database.py"
        if not init_script.exists():
            raise FileNotFoundError(f"Database initialization script not found: {init_script}")
        
        result = subprocess.run([
            sys.executable, str(init_script)
        ], capture_output=True, text=True, cwd=self.project_root)
        
        if result.returncode != 0:
            print(f"❌ Database initialization failed:")
            print(result.stderr)
            raise RuntimeError("Database initialization failed")
        
        print("  ✅ Database initialized")
        
        # Load generated config
        config_file = self.project_root / "test_config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.db_config = json.load(f)
            print(f"  📋 Run created: {self.db_config['run_name']}")
            print(f"  👥 Players: {len(self.db_config['players'])}")
        
        # Create database backup
        await self.create_database_backup()
    
    async def create_database_backup(self):
        """Create a backup of the initialized database."""
        import shutil
        from datetime import datetime
        
        db_file = self.project_root / "soullink_tracker.db"
        if db_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.logs_dir / f"database_backup_{timestamp}.db"
            shutil.copy2(db_file, backup_file)
            print(f"  💾 Database backup created: {backup_file.name}")
    
    async def setup_networking(self):
        """Set up Cloudflare tunnel for external access."""
        print("  - Setting up Cloudflare tunnel...")
        
        cloudflared_path = self.project_root / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
        if not cloudflared_path.exists():
            raise FileNotFoundError("Cloudflare tunnel binary not found")
        
        # Test tunnel connectivity
        print("  - Testing tunnel connectivity...")
        test_cmd = [str(cloudflared_path), "tunnel", "--url", self.api_url, "--logfile", str(self.logs_dir / "tunnel_test.log")]
        
        # Start tunnel in background for testing
        test_process = subprocess.Popen(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for tunnel to start and get URL
        tunnel_url = None
        for attempt in range(30):
            try:
                log_file = self.logs_dir / "tunnel_test.log"
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        content = f.read()
                        if "trycloudflare.com" in content:
                            # Extract tunnel URL
                            for line in content.split('\n'):
                                if "https://" in line and "trycloudflare.com" in line:
                                    tunnel_url = line.split()[-1]
                                    break
                            if tunnel_url:
                                break
                await asyncio.sleep(1)
            except:
                pass
        
        # Stop test process
        test_process.terminate()
        try:
            test_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            test_process.kill()
        
        if tunnel_url:
            self.tunnel_url = tunnel_url
            print(f"  ✅ Tunnel connectivity verified: {tunnel_url}")
            
            # Save tunnel config
            tunnel_config = {
                "tunnel_url": tunnel_url,
                "local_url": self.api_url,
                "created_at": time.time()
            }
            with open(self.tunnel_config_file, 'w') as f:
                json.dump(tunnel_config, f, indent=2)
        else:
            print("  ⚠️ Could not verify tunnel connectivity")
    
    async def start_services(self):
        """Start all required services."""
        print("  - Starting FastAPI server...")
        
        # Start API server
        cmd = [
            sys.executable, "-m", "uvicorn",
            "src.soullink_tracker.main:app",
            "--host", "127.0.0.1",
            "--port", str(self.api_port),
            "--access-log",
            "--log-file", str(self.logs_dir / "api.log")
        ]
        
        if self.mode == "dev":
            cmd.append("--reload")
        
        self.api_process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for API server to start
        for attempt in range(30):
            try:
                import requests
                response = requests.get(f"{self.api_url}/health", timeout=1)
                if response.status_code == 200:
                    print("  ✅ API server started successfully")
                    break
            except:
                pass
            await asyncio.sleep(1)
        else:
            raise RuntimeError("API server failed to start within 30 seconds")
        
        # Start tunnel if in production mode
        if self.mode == "production" and self.tunnel_url:
            print("  - Starting Cloudflare tunnel...")
            await self.start_tunnel()
    
    async def start_tunnel(self):
        """Start the Cloudflare tunnel."""
        cloudflared_path = self.project_root / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
        
        tunnel_cmd = [
            str(cloudflared_path), "tunnel",
            "--url", self.api_url,
            "--logfile", str(self.logs_dir / "tunnel.log")
        ]
        
        self.tunnel_process = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for tunnel to start and extract URL
        tunnel_url = None
        for attempt in range(30):
            try:
                log_file = self.logs_dir / "tunnel.log"
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            if "https://" in line and "trycloudflare.com" in line:
                                tunnel_url = line.split()[-1]
                                break
                        if tunnel_url:
                            break
                await asyncio.sleep(1)
            except:
                pass
        
        if tunnel_url:
            self.tunnel_url = tunnel_url
            print(f"  ✅ Tunnel started: {tunnel_url}")
        else:
            print("  ⚠️ Could not extract tunnel URL")
    
    async def generate_admin_configs(self):
        """Generate admin configuration files and tools."""
        admin_config = {
            "version": "1.0.0",
            "mode": self.mode,
            "setup_time": time.time(),
            "api": {
                "url": self.api_url,
                "port": self.api_port,
                "process_id": self.api_process.pid if self.api_process else None
            },
            "tunnel": {
                "url": self.tunnel_url,
                "enabled": self.mode == "production",
                "process_id": self.tunnel_process.pid if self.tunnel_process else None
            },
            "database": self.db_config if hasattr(self, 'db_config') else {},
            "paths": {
                "project_root": str(self.project_root),
                "logs_dir": str(self.logs_dir),
                "data_dir": str(self.data_dir),
                "temp_dir": str(self.temp_dir)
            },
            "monitoring": {
                "health_check_url": f"{self.api_url}/health",
                "metrics_url": f"{self.api_url}/metrics" if self.mode == "production" else None,
                "docs_url": f"{self.api_url}/docs"
            }
        }
        
        with open(self.admin_config_file, 'w') as f:
            json.dump(admin_config, f, indent=2)
        
        print(f"  ✅ Admin configuration saved: {self.admin_config_file.name}")
        
        # Generate player distribution script
        await self.generate_player_distribution_script()
    
    async def generate_player_distribution_script(self):
        """Generate script for distributing player configurations."""
        script_content = f'''#!/usr/bin/env python3
"""
SoulLink Tracker - Player Distribution Script
Auto-generated admin tool for distributing player configurations.
"""

import json
import shutil
import zipfile
from pathlib import Path

def create_player_packages():
    """Create distribution packages for each player."""
    project_root = Path(__file__).parent
    admin_config_file = project_root / "admin_config.json"
    
    if not admin_config_file.exists():
        print("❌ Admin configuration not found. Run admin setup first.")
        return
    
    with open(admin_config_file, 'r') as f:
        config = json.load(f)
    
    api_url = config["tunnel"]["url"] if config["tunnel"]["enabled"] else config["api"]["url"]
    
    print(f"📦 Creating player packages...")
    print(f"🌐 Server URL: {{api_url}}")
    
    packages_dir = project_root / "player_packages"
    packages_dir.mkdir(exist_ok=True)
    
    # Create packages for each player
    for player in config["database"]["players"]:
        player_name = player["name"]
        player_id = player["id"]
        
        print(f"  - Creating package for {{player_name}}...")
        
        player_dir = packages_dir / f"{{player_name}}_package"
        player_dir.mkdir(exist_ok=True)
        
        # Copy player setup script
        player_script = project_root / "scripts" / "player_setup.py"
        if player_script.exists():
            shutil.copy(player_script, player_dir / "setup.py")
        
        # Create player config
        player_config = {{
            "player_id": player_id,
            "player_name": player_name,
            "server_url": api_url,
            "bearer_token": player["token"]
        }}
        
        with open(player_dir / "player_config.json", 'w') as f:
            json.dump(player_config, f, indent=2)
        
        # Create README
        readme_content = f"""# SoulLink Tracker - {{player_name}} Setup

## Quick Start
1. Run: `python setup.py`
2. Follow the on-screen instructions
3. Start DeSmuME and load the provided Lua script

## Server Details
- Server URL: {{api_url}}
- Player: {{player_name}}
- Dashboard: {{api_url}}/dashboard?run={{config["database"]["run_id"]}}

## Support
Contact the admin if you encounter any issues.
"""
        
        with open(player_dir / "README.md", 'w') as f:
            f.write(readme_content)
        
        # Create ZIP package
        zip_file = packages_dir / f"{{player_name}}_setup.zip"
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in player_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(player_dir)
                    zf.write(file_path, arcname)
        
        print(f"  ✅ Package created: {{zip_file.name}}")
    
    print(f"\\n📁 All packages created in: {{packages_dir}}")
    print("\\n📧 Send the appropriate ZIP file to each player")

if __name__ == "__main__":
    create_player_packages()
'''
        
        distribution_script = self.scripts_dir / "distribute_players.py"
        with open(distribution_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(distribution_script, 0o755)
        print(f"  ✅ Player distribution script created: {distribution_script.name}")
    
    async def run_health_checks(self):
        """Run comprehensive health checks."""
        print("  - API server health...")
        try:
            import requests
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"  ✅ API: {health_data.get('service')} v{health_data.get('version')}")
            else:
                print(f"  ⚠️ API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ API health check failed: {e}")
        
        print("  - Database connectivity...")
        try:
            response = requests.get(f"{self.api_url}/v1/runs", timeout=5)
            if response.status_code == 200:
                runs = response.json()
                print(f"  ✅ Database: {len(runs)} runs available")
            else:
                print(f"  ⚠️ Database check returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Database check failed: {e}")
        
        if self.tunnel_url:
            print("  - Tunnel connectivity...")
            try:
                response = requests.get(f"{self.tunnel_url}/health", timeout=10)
                if response.status_code == 200:
                    print(f"  ✅ Tunnel: External access working")
                else:
                    print(f"  ⚠️ Tunnel returned status {response.status_code}")
            except Exception as e:
                print(f"  ❌ Tunnel check failed: {e}")
    
    async def open_admin_dashboard(self):
        """Open the admin dashboard."""
        if hasattr(self, 'db_config'):
            dashboard_url = f"{self.api_url}/dashboard?run={self.db_config['run_id']}"
        else:
            dashboard_url = f"{self.api_url}/docs"
        
        try:
            webbrowser.open(dashboard_url)
            print(f"  ✅ Admin dashboard opened: {dashboard_url}")
        except Exception as e:
            print(f"  ⚠️ Could not open dashboard: {e}")
            print(f"  🔗 Open manually: {dashboard_url}")
        
        # Show all important URLs
        self.show_admin_summary()
    
    def show_admin_summary(self):
        """Show comprehensive admin summary."""
        print("\\n" + "=" * 80)
        print("🎮 SOULLINK TRACKER - ADMIN SUMMARY")
        print("=" * 80)
        
        print(f"\\n🔧 System Information:")
        print(f"   Mode: {self.mode.upper()}")
        print(f"   Project: {self.project_root}")
        print(f"   Python: {sys.version.split()[0]}")
        
        print(f"\\n🌐 Server URLs:")
        print(f"   Local API: {self.api_url}")
        if self.tunnel_url:
            print(f"   Public URL: {self.tunnel_url}")
        print(f"   API Docs: {self.api_url}/docs")
        
        if hasattr(self, 'db_config'):
            print(f"\\n📊 Current Run:")
            print(f"   Name: {self.db_config['run_name']}")
            print(f"   ID: {self.db_config['run_id']}")
            print(f"   Players: {len(self.db_config['players'])}")
            print(f"   Dashboard: {self.api_url}/dashboard?run={self.db_config['run_id']}")
        
        print(f"\\n🛠️ Admin Tools:")
        print(f"   Distribute players: python scripts/distribute_players.py")
        print(f"   Health check: python scripts/health_check.py")
        print(f"   Database backup: python scripts/backup_database.py")
        
        print(f"\\n📁 Important Files:")
        print(f"   Admin config: {self.admin_config_file.name}")
        print(f"   Logs directory: {self.logs_dir}")
        print(f"   Database: soullink_tracker.db")
        
        print(f"\\n🎯 Next Steps:")
        print("   1. Run: python scripts/distribute_players.py")
        print("   2. Send player packages to each player")
        print("   3. Monitor logs and dashboard for activity")
        print("   4. Use Ctrl+C to shutdown all services")
        
        print("\\n" + "=" * 80)
    
    async def monitor_services(self):
        """Monitor all running services."""
        print("\\n🔄 Service monitoring started (Ctrl+C to stop)...")
        
        try:
            while True:
                # Check processes
                api_running = self.api_process and self.api_process.poll() is None
                tunnel_running = self.tunnel_process and self.tunnel_process.poll() is None
                
                if not api_running:
                    print("⚠️ API server process has stopped")
                    break
                
                if self.mode == "production" and not tunnel_running:
                    print("⚠️ Tunnel process has stopped")
                
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            print("\\n🛑 Shutdown requested by admin...")
            raise
    
    async def reset_configuration(self):
        """Reset all configuration and data."""
        print("  - Removing configuration files...")
        files_to_remove = [
            self.admin_config_file,
            self.tunnel_config_file,
            self.project_root / "test_config.json",
            self.project_root / "soullink_tracker.db",
            self.project_root / "soullink_tracker.db-shm",
            self.project_root / "soullink_tracker.db-wal"
        ]
        
        for file_path in files_to_remove:
            if file_path.exists():
                file_path.unlink()
                print(f"    ✅ Removed: {file_path.name}")
        
        print("  - Clearing temporary directories...")
        dirs_to_clear = [self.logs_dir, self.temp_dir]
        for dir_path in dirs_to_clear:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"    ✅ Cleared: {dir_path.name}")
    
    async def cleanup(self):
        """Clean up all processes and resources."""
        print("🧹 Cleaning up services...")
        
        # Stop API server
        if self.api_process:
            print("  - Stopping API server...")
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=10)
                print("  ✅ API server stopped")
            except subprocess.TimeoutExpired:
                print("  ⚠️ Force killing API server...")
                self.api_process.kill()
        
        # Stop tunnel
        if self.tunnel_process:
            print("  - Stopping tunnel...")
            self.tunnel_process.terminate()
            try:
                self.tunnel_process.wait(timeout=5)
                print("  ✅ Tunnel stopped")
            except subprocess.TimeoutExpired:
                print("  ⚠️ Force killing tunnel...")
                self.tunnel_process.kill()
        
        print("🏁 Admin cleanup complete")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SoulLink Tracker Admin Setup")
    parser.add_argument("--dev", action="store_true", help="Development mode (local only)")
    parser.add_argument("--production", action="store_true", help="Production mode (with tunnel)")
    parser.add_argument("--tunnel-only", action="store_true", help="Only setup tunnel")
    parser.add_argument("--reset", action="store_true", help="Reset configuration")
    
    args = parser.parse_args()
    
    # Determine mode
    if args.production:
        mode = "production"
    elif args.dev:
        mode = "dev"
    else:
        # Ask user
        print("Select setup mode:")
        print("1. Development (local access only)")
        print("2. Production (with external tunnel)")
        choice = input("Enter choice [1-2]: ").strip()
        mode = "production" if choice == "2" else "dev"
    
    # Create manager
    manager = AdminSetupManager(mode=mode)
    
    # Handle tunnel-only mode
    if args.tunnel_only:
        print("🌐 Setting up Cloudflare tunnel only...")
        await manager.install_cloudflare_tunnel()
        await manager.setup_networking()
        return
    
    # Run complete setup
    await manager.run_complete_setup(reset=args.reset)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Admin setup cancelled!")
    except Exception as e:
        print(f"\\n💥 Unexpected error: {e}")
        sys.exit(1)