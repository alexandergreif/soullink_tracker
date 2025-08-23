"""
SoulLink Tracker User Launcher

This module handles launching the user/watcher components of SoulLink Tracker.
It sets up the environment for watchers, Lua scripts, and client components.
"""

import os
import sys
import signal
import atexit
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


@dataclass
class UserResourceManager:
    """Manages resource paths for user components."""
    
    def __init__(self):
        self.is_bundled = hasattr(sys, '_MEIPASS') or hasattr(sys, 'frozen')
        self._app_dir = None
        self._user_data_dir = None
        self._lua_dir = None
        self._spool_dir = None
    
    @property
    def app_dir(self) -> Path:
        """Get the application directory."""
        if self._app_dir is None:
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller bundle
                self._app_dir = Path(sys._MEIPASS)
            elif hasattr(sys, 'frozen'):
                # Other frozen environment
                self._app_dir = Path(sys.executable).parent
            else:
                # Development environment
                self._app_dir = Path(__file__).parent.parent.parent
        return self._app_dir
    
    @property
    def user_data_dir(self) -> Path:
        """Get the user data directory."""
        if self._user_data_dir is None:
            if self.is_bundled:
                # Portable mode - use current working directory
                self._user_data_dir = Path.cwd() / "data_user"
            else:
                # Development mode
                self._user_data_dir = self.app_dir / "data_user"
        return self._user_data_dir
    
    @property
    def lua_dir(self) -> Path:
        """Get the Lua scripts directory."""
        if self._lua_dir is None:
            self._lua_dir = self.app_dir / "client" / "lua"
        return self._lua_dir
    
    @property
    def spool_dir(self) -> Path:
        """Get the spool directory for watcher-lua communication."""
        if self._spool_dir is None:
            self._spool_dir = self.user_data_dir / "spool"
        return self._spool_dir


class SoulLinkWatcherLauncher:
    """Launcher for the SoulLink Tracker user/watcher components."""
    
    def __init__(self):
        self.resource_manager = UserResourceManager()
        self.logger = None
        self.watcher_thread = None
        self.tray_icon = None
        self.shutdown_event = threading.Event()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self.shutdown)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()
    
    def setup_logging(self) -> None:
        """Setup logging for the user launcher."""
        # Check if portable logging is already setup
        root_logger = logging.getLogger()
        if hasattr(root_logger, '_portable_logging_setup'):
            self.logger = logging.getLogger(__name__)
            return
        
        # Basic logging setup if portable logging not available
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.resource_manager.user_data_dir / "user_launcher.log")
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        self.logger.info("Checking dependencies...")
        
        # Check if Lua directory exists and contains scripts
        if not self.resource_manager.lua_dir.exists():
            self.logger.error(f"Lua directory not found: {self.resource_manager.lua_dir}")
            return False
        
        lua_script = self.resource_manager.lua_dir / "pokemon_tracker_v3.lua"
        if not lua_script.exists():
            self.logger.error(f"Main Lua script not found: {lua_script}")
            return False
        
        # Create spool directory if it doesn't exist
        self.resource_manager.spool_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Spool directory ready: {self.resource_manager.spool_dir}")
        
        # Test watcher import
        try:
            import importlib.util
            spec = importlib.util.find_spec("soullink_watcher")
            if spec is None:
                raise ImportError("soullink_watcher not found")
            self.logger.info("Watcher package imported successfully")
        except ImportError as e:
            self.logger.error(f"Cannot import watcher package: {e}")
            return False
        
        return True
    
    def setup_environment(self) -> None:
        """Setup environment variables for the user components."""
        # Set standard environment variables
        os.environ["SOULLINK_LUA_DIR"] = str(self.resource_manager.lua_dir)
        os.environ["SOULLINK_USER_DATA_DIR"] = str(self.resource_manager.user_data_dir)
        os.environ["SOULLINK_WATCHER_SPOOL_DIR"] = str(self.resource_manager.spool_dir)
        os.environ["SOULLINK_PORTABLE"] = "1" if self.resource_manager.is_bundled else "0"
        
        # Set default API URL if not provided
        if "SOULLINK_API_URL" not in os.environ:
            os.environ["SOULLINK_API_URL"] = "http://127.0.0.1:8000"
        
        self.logger.info("Environment configured:")
        self.logger.info(f"  Lua Dir: {os.environ['SOULLINK_LUA_DIR']}")
        self.logger.info(f"  User Data Dir: {os.environ['SOULLINK_USER_DATA_DIR']}")
        self.logger.info(f"  Spool Dir: {os.environ['SOULLINK_WATCHER_SPOOL_DIR']}")
        self.logger.info(f"  API URL: {os.environ['SOULLINK_API_URL']}")
    
    def ensure_lua_config(self, api_url: Optional[str] = None) -> Path:
        """Ensure Lua config exists, create from template if needed."""
        config_path = self.resource_manager.lua_dir / "config.lua"
        template_path = self.resource_manager.lua_dir / "config_template.lua"
        
        if config_path.exists():
            self.logger.info(f"Lua config already exists: {config_path}")
            return config_path
        
        # Use provided API URL or environment variable
        if api_url is None:
            api_url = os.environ.get("SOULLINK_API_URL", "http://127.0.0.1:8000")
        
        # Create config from template if available
        if template_path.exists():
            self.logger.info(f"Creating config from template: {template_path}")
            try:
                template_content = template_path.read_text(encoding="utf-8")
                config_content = template_content.replace("{{API_URL}}", api_url)
                # Use forward slashes for Lua path compatibility (works on both Windows and Unix)
                spool_dir_lua = str(self.resource_manager.spool_dir).replace("\\", "/")
                config_content = config_content.replace("{{SPOOL_DIR}}", spool_dir_lua)
                config_path.write_text(config_content, encoding="utf-8")
                self.logger.info(f"Lua config created: {config_path}")
            except Exception as e:
                self.logger.error(f"Failed to create config from template: {e}")
                # Fallback to basic config
                self._create_basic_lua_config(config_path, api_url)
        else:
            self.logger.info("No template found, creating basic config")
            self._create_basic_lua_config(config_path, api_url)
        
        return config_path
    
    def _create_basic_lua_config(self, config_path: Path, api_url: str):
        """Create a basic Lua config file."""
        basic_config = f'''-- SoulLink Tracker Lua Config (auto-generated)
return {{
    API_URL = "{api_url}",
    SPOOL_DIR = [[{self.resource_manager.spool_dir}]],
    DEBUG = false,
    RETRY_DELAY = 1.0
}}
'''
        config_path.write_text(basic_config, encoding="utf-8")
        self.logger.info(f"Basic Lua config created: {config_path}")
    
    def start_watcher(self) -> bool:
        """Start the watcher in a background thread."""
        try:
            from soullink_watcher.main import main as watcher_main
            from soullink_watcher.config import get_config
            
            # Get watcher configuration
            config = get_config()
            self.logger.info(f"Starting watcher with config: API URL={config.api_url}, Spool Dir={config.spool_dir}")
            
            def watcher_worker():
                try:
                    result = watcher_main(config)
                    self.logger.info(f"Watcher completed with exit code: {result}")
                except Exception as e:
                    self.logger.error(f"Watcher failed: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
            
            self.watcher_thread = threading.Thread(target=watcher_worker, daemon=True)
            self.watcher_thread.start()
            self.logger.info("Watcher started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start watcher: {e}")
            return False
    
    def start_system_tray(self) -> None:
        """Start system tray icon if available."""
        if not HAS_TRAY:
            self.logger.info("System tray not available (pystray/PIL not installed)")
            return
        
        # Create tray icon
        def create_icon():
            # Simple icon - blue circle
            img = Image.new('RGB', (64, 64), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill=(0, 100, 200))
            return img
        
        # Tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Open Lua Folder", self.open_lua_folder),
            pystray.MenuItem("View Logs", self.open_logs_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_from_tray)
        )
        
        try:
            self.tray_icon = pystray.Icon("SoulLink User", create_icon(), menu=menu)
            
            # Run tray in separate thread
            def run_tray():
                try:
                    self.tray_icon.run()
                except Exception as e:
                    self.logger.error(f"Tray icon error: {e}")
            
            tray_thread = threading.Thread(target=run_tray, daemon=True)
            tray_thread.start()
            self.logger.info("System tray started")
            
        except Exception as e:
            self.logger.error(f"Failed to start system tray: {e}")
    
    def open_lua_folder(self) -> None:
        """Open the Lua folder in the file explorer."""
        lua_dir = self.resource_manager.lua_dir
        try:
            if sys.platform == "win32":
                os.startfile(lua_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(lua_dir)])
            else:
                subprocess.run(["xdg-open", str(lua_dir)])
            self.logger.info(f"Opened Lua folder: {lua_dir}")
        except Exception as e:
            self.logger.error(f"Failed to open Lua folder: {e}")
    
    def open_logs_folder(self) -> None:
        """Open the logs folder in the file explorer."""
        logs_dir = self.resource_manager.user_data_dir
        try:
            if sys.platform == "win32":
                os.startfile(logs_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(logs_dir)])
            else:
                subprocess.run(["xdg-open", str(logs_dir)])
            self.logger.info(f"Opened logs folder: {logs_dir}")
        except Exception as e:
            self.logger.error(f"Failed to open logs folder: {e}")
    
    def _quit_from_tray(self):
        """Quit application from tray menu."""
        self.logger.info("Quit requested from tray menu")
        self.shutdown_event.set()
        if self.tray_icon:
            self.tray_icon.stop()
    
    def show_startup_info(self) -> None:
        """Display startup information to user."""
        print("\n" + "="*60)
        print("SoulLink Tracker User Components Started")
        print("="*60)
        print(f"Lua Scripts Folder: {self.resource_manager.lua_dir}")
        print(f"Spool Directory: {self.resource_manager.spool_dir}")
        print(f"API URL: {os.environ.get('SOULLINK_API_URL', 'Not set')}")
        print(f"Logs Directory: {self.resource_manager.user_data_dir}")
        print()
        print("Instructions:")
        print("1. Load pokemon_tracker_v3.lua in your DeSmuME emulator")
        print("2. The watcher will automatically process data from the spool directory")
        print("3. Make sure the admin server is running at the API URL above")
        print()
        if HAS_TRAY:
            print("System tray icon available - right-click for options")
        print("Press Ctrl+C to quit")
        print("="*60)
    
    def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        try:
            self.shutdown_event.wait()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
    
    def shutdown(self) -> None:
        """Shutdown all components."""
        if hasattr(self, '_shutdown_called'):
            return
        self._shutdown_called = True
        
        self.logger.info("Shutting down user components...")
        
        # Stop tray icon
        if self.tray_icon:
            self.tray_icon.stop()
        
        # Note: Watcher thread will be killed when main process exits (daemon=True)
        self.logger.info("User components shutdown complete")
    
    def run(self) -> int:
        """Main run loop for the user launcher."""
        try:
            # Setup logging first
            self.resource_manager.user_data_dir.mkdir(parents=True, exist_ok=True)
            self.setup_logging()
            
            self.logger.info("="*60)
            self.logger.info("SoulLink Tracker User Launcher Starting")
            self.logger.info("="*60)
            
            # Check dependencies
            if not self.check_dependencies():
                print("Dependency check failed - cannot continue")
                return 1
            
            # Setup environment
            self.setup_environment()
            
            # Ensure Lua config exists
            self.ensure_lua_config()
            
            # Start watcher
            if not self.start_watcher():
                print("Failed to start watcher - cannot continue")
                return 1
            
            # Start system tray
            self.start_system_tray()
            
            # Show startup info
            self.show_startup_info()
            
            # Wait for shutdown
            self.wait_for_shutdown()
            
            return 0
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"User launcher failed: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            else:
                print(f"User launcher failed: {e}")
            return 1


def main() -> int:
    """Main entry point for user launcher."""
    launcher = SoulLinkWatcherLauncher()
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())