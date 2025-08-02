"""
Portable SoulLink Tracker Launcher

This is the main entry point for the portable version of SoulLink Tracker.
It handles:
- Resource detection (bundled vs development)
- Auto port detection 
- Browser launching
- System tray integration
- Graceful shutdown
"""

import asyncio
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Tuple
import logging
import signal
import atexit

# Third-party imports for system tray (optional)
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    # Create dummy classes to prevent import errors
    class Image:
        @staticmethod
        def new(*args, **kwargs):
            return None
    class ImageDraw:
        @staticmethod
        def Draw(*args, **kwargs):
            return None

import uvicorn
from uvicorn.config import Config

# Import our FastAPI app
from .main import app


class ResourceManager:
    """Manages resource paths for both development and bundled environments."""
    
    def __init__(self):
        self.is_bundled = self._detect_bundle_environment()
        self.app_dir = self._get_app_directory()
        self.data_dir = self._get_data_directory()
        
    def _detect_bundle_environment(self) -> bool:
        """Detect if we're running in a bundled environment (PyInstaller/Nuitka)."""
        return (
            hasattr(sys, 'frozen') or  # Nuitka
            hasattr(sys, '_MEIPASS') or  # PyInstaller
            'site-packages' not in __file__  # Bundled check
        )
        
    def _get_app_directory(self) -> Path:
        """Get the application directory (where resources are located)."""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller bundle
            return Path(sys._MEIPASS)
        elif hasattr(sys, 'frozen'):
            # Nuitka or other frozen environment
            return Path(sys.executable).parent
        else:
            # Development environment
            return Path(__file__).parent.parent.parent
            
    def _get_data_directory(self) -> Path:
        """Get user data directory for database, logs, configs."""
        if self.is_bundled:
            # For portable apps, use current working directory or app directory
            data_dir = Path.cwd() / "data"
        else:
            # Development - use project data directory
            data_dir = self.app_dir / "data"
            
        data_dir.mkdir(exist_ok=True)
        return data_dir
        
    def get_web_directory(self) -> Path:
        """Get web assets directory."""
        return self.app_dir / "web"
        
    def get_lua_directory(self) -> Path:
        """Get Lua scripts directory."""
        return self.app_dir / "client" / "lua"
        
    def get_data_files_directory(self) -> Path:
        """Get CSV data files directory."""
        return self.app_dir / "data"


class PortManager:
    """Manages port detection and allocation."""
    
    @staticmethod
    def find_free_port(start_port: int = 8000, max_attempts: int = 10) -> Optional[int]:
        """Find a free port starting from start_port."""
        for port in range(start_port, start_port + max_attempts):
            if PortManager.is_port_free(port):
                return port
        return None
        
    @staticmethod
    def is_port_free(port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False


class BrowserManager:
    """Manages browser launching and URL handling."""
    
    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        
    def open_dashboard(self, port: int, delay: float = 2.0) -> None:
        """Open the dashboard in the default browser after a delay."""
        def delayed_open():
            time.sleep(delay)
            url = f"http://{self.host}:{port}"
            try:
                webbrowser.open(url)
                logging.info(f"Opened browser to {url}")
            except Exception as e:
                logging.error(f"Failed to open browser: {e}")
                print(f"Please manually open: {url}")
                
        thread = threading.Thread(target=delayed_open, daemon=True)
        thread.start()


class SystemTrayManager:
    """Optional system tray integration."""
    
    def __init__(self, port: int):
        self.port = port
        self.icon = None
        self.running = True
        
    def create_icon(self):
        """Create a simple icon for the system tray."""
        if not TRAY_AVAILABLE:
            return None
        try:
            # Create a simple 16x16 icon
            img = Image.new('RGB', (16, 16), color='blue')
            draw = ImageDraw.Draw(img)
            draw.text((2, 2), "SL", fill='white')
            return img
        except Exception:
            return None
            
    def create_menu(self):
        """Create system tray menu."""
        def open_dashboard():
            webbrowser.open(f"http://127.0.0.1:{self.port}")
            
        def quit_app():
            self.running = False
            if self.icon:
                self.icon.stop()
            os._exit(0)
            
        return pystray.Menu(
            pystray.MenuItem("Open Dashboard", open_dashboard),
            pystray.MenuItem("Quit", quit_app)
        )
        
    def run(self):
        """Run the system tray."""
        if not TRAY_AVAILABLE:
            return
            
        icon_image = self.create_icon()
        if icon_image:
            self.icon = pystray.Icon(
                "SoulLink Tracker",
                icon_image,
                menu=self.create_menu()
            )
            self.icon.run()


class SoulLinkLauncher:
    """Main launcher class that coordinates all components."""
    
    def __init__(self):
        self.setup_logging()
        self.resource_manager = ResourceManager()
        self.port_manager = PortManager()
        self.browser_manager = BrowserManager()
        self.tray_manager = None
        self.server = None
        self.server_thread = None
        self.port = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup)
        
    def setup_logging(self):
        """Setup logging configuration."""
        # Check if portable logging is already set up
        if hasattr(logging.getLogger(), '_portable_logging_setup'):
            logging.info("Portable logging already configured, skipping basic setup")
            return
            
        log_level = logging.INFO
        if os.getenv('SOULLINK_DEBUG'):
            log_level = logging.DEBUG
            
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                # Add file handler for portable version
                logging.FileHandler('soullink_launcher.log')
            ]
        )
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logging.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        
    def _cleanup(self):
        """Cleanup on exit."""
        if self.server:
            self.server.should_exit = True
            
    def check_dependencies(self) -> bool:
        """Check if all required resources are available."""
        try:
            logging.info("=== RESOURCE DEPENDENCY CHECK ===")
            
            # Check if web directory exists
            web_dir = self.resource_manager.get_web_directory()
            if not web_dir.exists():
                logging.error(f"Web directory not found: {web_dir}")
                return False
            else:
                logging.info(f"Web directory found: {web_dir}")
                
            # Check if main web files exist
            index_file = web_dir / "index.html"
            if not index_file.exists():
                logging.error(f"Web index file not found: {index_file}")
                return False
            else:
                size = index_file.stat().st_size
                logging.info(f"Web index file found: {index_file} ({size} bytes)")
                
            # Check for other critical web files
            critical_web_files = ["static/css", "static/js", "static/img"]
            for web_path in critical_web_files:
                full_path = web_dir / web_path
                if full_path.exists():
                    logging.info(f"Web resource found: {full_path}")
                else:
                    logging.warning(f"Web resource missing: {full_path}")
                
            # Check data files
            data_dir = self.resource_manager.get_data_files_directory()
            species_file = data_dir / "species.csv"
            routes_file = data_dir / "routes.csv"
            
            if not species_file.exists():
                logging.warning(f"Species data file not found: {species_file}")
            else:
                size = species_file.stat().st_size
                logging.info(f"Species data file found: {species_file} ({size} bytes)")
                
            if not routes_file.exists():
                logging.warning(f"Routes data file not found: {routes_file}")
            else:
                size = routes_file.stat().st_size
                logging.info(f"Routes data file found: {routes_file} ({size} bytes)")
                
            # Check lua scripts directory
            lua_dir = self.resource_manager.get_lua_directory()
            if lua_dir.exists():
                lua_files = list(lua_dir.glob("*.lua"))
                logging.info(f"Lua directory found: {lua_dir} ({len(lua_files)} .lua files)")
            else:
                logging.warning(f"Lua directory not found: {lua_dir}")
                
            # Log resource manager environment
            logging.info(f"Resource Manager Environment:")
            logging.info(f"  - Is Bundled: {self.resource_manager.is_bundled}")
            logging.info(f"  - App Directory: {self.resource_manager.app_dir}")
            logging.info(f"  - Data Directory: {self.resource_manager.data_dir}")
                
            logging.info("Resource dependency check completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"Dependency check failed: {e}")
            logging.error(f"Exception details: {repr(e)}")
            return False
            
    def find_available_port(self) -> Optional[int]:
        """Find an available port for the server."""
        port = self.port_manager.find_free_port()
        if port is None:
            logging.error("No available ports found in range 8000-8010")
            return None
            
        logging.info(f"Found available port: {port}")
        return port
        
    def setup_environment(self):
        """Setup environment variables for the FastAPI app."""
        # Set resource paths for the main app to use
        os.environ['SOULLINK_WEB_DIR'] = str(self.resource_manager.get_web_directory())
        os.environ['SOULLINK_DATA_DIR'] = str(self.resource_manager.get_data_files_directory())
        os.environ['SOULLINK_LUA_DIR'] = str(self.resource_manager.get_lua_directory())
        os.environ['SOULLINK_USER_DATA_DIR'] = str(self.resource_manager.data_dir)
        os.environ['SOULLINK_PORTABLE'] = '1' if self.resource_manager.is_bundled else '0'
        
    def start_server(self, port: int) -> bool:
        """Start the FastAPI server."""
        try:
            config = Config(
                app=app,
                host="127.0.0.1",
                port=port,
                log_level="info",
                access_log=False  # Reduce console spam
            )
            
            self.server = uvicorn.Server(config)
            
            # Start server in a separate thread
            def run_server():
                asyncio.run(self.server.serve())
                
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(1)
            
            # Verify server is running
            if self.port_manager.is_port_free(port):
                logging.error("Server failed to start")
                return False
                
            logging.info(f"Server started successfully on port {port}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start server: {e}")
            return False
            
    def start_system_tray(self):
        """Start system tray (optional)."""
        if TRAY_AVAILABLE and self.port:
            self.tray_manager = SystemTrayManager(self.port)
            tray_thread = threading.Thread(target=self.tray_manager.run, daemon=True)
            tray_thread.start()
            logging.info("System tray started")
        else:
            logging.info("System tray not available or port not set")
            
    def show_startup_info(self):
        """Show startup information to the user."""
        print("\n" + "="*60)
        print("SoulLink Tracker - Portable Edition")
        print("="*60)
        print(f"Server running at: http://127.0.0.1:{self.port}")
        print(f"Dashboard: http://127.0.0.1:{self.port}/dashboard")
        print(f"API Docs: http://127.0.0.1:{self.port}/docs")
        print()
        print("The dashboard should open automatically in your browser.")
        print("If not, please click one of the URLs above.")
        print()
        if TRAY_AVAILABLE:
            print("The application will run in the system tray.")
            print("Right-click the tray icon to access options.")
        else:
            print("Press Ctrl+C to stop the server.")
        print("="*60)
        
    def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        try:
            if self.tray_manager and TRAY_AVAILABLE:
                # If tray is available, let it handle the main loop
                while self.tray_manager.running:
                    time.sleep(1)
            else:
                # Otherwise, wait for Ctrl+C
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt")
            
    def shutdown(self):
        """Shutdown the application gracefully."""
        logging.info("Shutting down SoulLink Tracker...")
        
        if self.server:
            self.server.should_exit = True
            
        if self.tray_manager:
            self.tray_manager.running = False
            
        time.sleep(1)  # Give time for cleanup
        logging.info("Shutdown complete")
        
    def run(self) -> int:
        """Main entry point - run the portable application."""
        try:
            logging.info("Starting SoulLink Tracker Portable...")
            
            # Check dependencies
            if not self.check_dependencies():
                print("[ERROR] Dependency check failed. Please check the logs.")
                return 1
                
            # Find available port
            self.port = self.find_available_port()
            if self.port is None:
                print("[ERROR] No available ports found. Please close other applications and try again.")
                return 1
                
            # Setup environment
            self.setup_environment()
            
            # Initialize static files now that environment is set
            from .main import init_static_files
            init_static_files()
            
            # Start server
            if not self.start_server(self.port):
                print("[ERROR] Failed to start server. Please check the logs.")
                return 1
                
            # Start browser
            self.browser_manager.open_dashboard(self.port)
            
            # Start system tray (optional)
            self.start_system_tray()
            
            # Show startup info
            self.show_startup_info()
            
            # Wait for shutdown
            self.wait_for_shutdown()
            
            return 0
            
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print(f"[ERROR] Unexpected error: {e}")
            return 1
        finally:
            self.shutdown()


def main() -> int:
    """Main entry point for the portable launcher."""
    launcher = SoulLinkLauncher()
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())