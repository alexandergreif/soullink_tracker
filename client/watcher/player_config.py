#!/usr/bin/env python3
"""
SoulLink Tracker - Player Configuration Management
Manages player configuration for the event watcher system.

This script handles:
1. Loading player configuration from database initialization
2. Generating watcher configuration files
3. Validating API connectivity
4. Setting up directory structures
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

import requests


class PlayerConfigManager:
    """Manages player configuration for the watcher system."""
    
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # Assume we're in client/watcher/ and find project root
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.config_dir = self.project_root / "client" / "watcher" / "configs"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_database_config(self) -> Dict:
        """Load configuration from database initialization."""
        config_file = self.project_root / "test_config.json"
        
        if not config_file.exists():
            raise FileNotFoundError(
                f"Database configuration not found at {config_file}. "
                "Please run 'python scripts/init_database.py' first."
            )
        
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def create_watcher_configs(
        self, 
        api_base_url: str = "http://127.0.0.1:9000",
        watch_base_dir: Optional[str] = None
    ) -> List[Path]:
        """Create watcher configuration files for all players."""
        
        # Load database config
        db_config = self.load_database_config()
        
        # Default watch directory
        if watch_base_dir is None:
            watch_base_dir = str(self.project_root / "temp" / "events")
        
        config_files = []
        
        for player in db_config['players']:
            config = self._create_player_config(
                player=player,
                run_id=db_config['run_id'],
                api_base_url=api_base_url,
                watch_base_dir=watch_base_dir
            )
            
            config_file = self._write_config_file(player['name'], config)
            config_files.append(config_file)
            
            print(f"Created config for {player['name']}: {config_file}")
        
        return config_files
    
    def _create_player_config(
        self, 
        player: Dict, 
        run_id: str, 
        api_base_url: str, 
        watch_base_dir: str
    ) -> Dict:
        """Create configuration for a single player."""
        
        player_watch_dir = Path(watch_base_dir) / player['name']
        log_dir = self.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            # Player identification
            "player_name": player['name'],
            "player_id": player['id'],
            "player_token": player['token'],
            "game_version": player['game'],
            "region": "EU",  # Default, can be overridden
            
            # Run information
            "run_id": run_id,
            
            # API connection
            "api_base_url": api_base_url,
            "connection_timeout": 10,
            "retry_attempts": 3,
            "retry_delay": 1000,
            
            # File system
            "watch_directory": str(player_watch_dir),
            "log_file": str(log_dir / f"watcher_{player['name'].lower()}.log"),
            "delete_processed_files": True,
            
            # Performance and rate limiting
            "max_events_per_minute": 30,
            "poll_interval": 1,  # seconds
            
            # Debug and logging
            "debug": True,
            "log_api_calls": True,
            "log_file_processing": True,
            
            # Event processing
            "enable_idempotency": True,
            "queue_max_size": 1000,
            "batch_processing": False,
            
            # Health monitoring
            "health_check_interval": 60,  # seconds
            "api_health_check": True,
            
            # Advanced options
            "auto_cleanup_old_files": True,
            "max_file_age_hours": 24,
            "max_log_size_mb": 10
        }
    
    def _write_config_file(self, player_name: str, config: Dict) -> Path:
        """Write configuration to file."""
        config_file = self.config_dir / f"{player_name.lower()}_config.json"
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return config_file
    
    def validate_config(self, config_file: Path) -> Dict[str, List[str]]:
        """Validate a configuration file."""
        errors = []
        warnings = []
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            return {"errors": [f"Failed to load config file: {e}"], "warnings": []}
        
        # Required fields
        required_fields = [
            'player_name', 'player_id', 'player_token', 'run_id',
            'api_base_url', 'watch_directory'
        ]
        
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
            elif not config[field]:
                errors.append(f"Empty required field: {field}")
        
        # Validate UUIDs
        for uuid_field in ['player_id', 'run_id']:
            if uuid_field in config:
                try:
                    UUID(config[uuid_field])
                except ValueError:
                    errors.append(f"Invalid UUID format for {uuid_field}: {config[uuid_field]}")
        
        # Validate API URL
        if 'api_base_url' in config:
            url = config['api_base_url']
            if not url.startswith(('http://', 'https://')):
                errors.append(f"Invalid API URL format: {url}")
        
        # Validate directories
        if 'watch_directory' in config:
            watch_dir = Path(config['watch_directory'])
            try:
                watch_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create watch directory {watch_dir}: {e}")
        
        # Check token format
        if 'player_token' in config:
            token = config['player_token']
            if not token or len(token) < 10:
                warnings.append("Player token seems invalid (too short)")
        
        # Performance warnings
        if config.get('max_events_per_minute', 30) > 60:
            warnings.append("High event rate limit may overwhelm API")
        
        if config.get('connection_timeout', 10) < 5:
            warnings.append("Low connection timeout may cause failures")
        
        return {"errors": errors, "warnings": warnings}
    
    def test_api_connectivity(self, config_file: Path) -> bool:
        """Test API connectivity with the given configuration."""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Test health endpoint
            health_url = f"{config['api_base_url']}/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code != 200:
                print(f"API health check failed: {response.status_code}")
                return False
            
            print(f"API health check passed: {response.json()}")
            
            # Test authentication
            auth_url = f"{config['api_base_url']}/v1/runs"
            headers = {"Authorization": f"Bearer {config['player_token']}"}
            
            auth_response = requests.get(auth_url, headers=headers, timeout=5)
            
            if auth_response.status_code in (200, 401, 403):
                if auth_response.status_code == 200:
                    print("Authentication test passed")
                    return True
                else:
                    print(f"Authentication failed: {auth_response.status_code}")
                    return False
            else:
                print(f"Unexpected auth response: {auth_response.status_code}")
                return False
                
        except Exception as e:
            print(f"API connectivity test failed: {e}")
            return False
    
    def create_lua_configs(self) -> List[Path]:
        """Create Lua configuration files from watcher configs."""
        lua_config_dir = self.project_root / "client" / "lua" / "configs"
        lua_config_dir.mkdir(parents=True, exist_ok=True)
        
        lua_configs = []
        
        # Find watcher configs
        for config_file in self.config_dir.glob("*_config.json"):
            with open(config_file, 'r') as f:
                watcher_config = json.load(f)
            
            lua_config = self._create_lua_config(watcher_config)
            lua_file = lua_config_dir / f"{watcher_config['player_name'].lower()}_config.lua"
            
            with open(lua_file, 'w') as f:
                f.write(self._format_lua_config(lua_config))
            
            lua_configs.append(lua_file)
            print(f"Created Lua config: {lua_file}")
        
        return lua_configs
    
    def _create_lua_config(self, watcher_config: Dict) -> Dict:
        """Convert watcher config to Lua config format."""
        return {
            "player_name": watcher_config['player_name'],
            "game_version": watcher_config['game_version'],
            "region": watcher_config['region'],
            "api_base_url": watcher_config['api_base_url'],
            "player_token": watcher_config['player_token'],
            "output_dir": watcher_config['watch_directory'].replace('\\', '/') + '/',
            "log_file": watcher_config.get('log_file', '').replace('\\', '/'),
            "poll_interval": 60,  # Lua uses frame intervals
            "debug_mode": watcher_config.get('debug', True),
            "enable_shiny_detection": True,
            "detect_fishing": True,
            "detect_surfing": True,
            "detect_headbutt": True,
            "max_events_per_minute": watcher_config.get('max_events_per_minute', 30)
        }
    
    def _format_lua_config(self, config: Dict) -> str:
        """Format configuration as Lua code."""
        lua_lines = [
            "-- Auto-generated configuration for SoulLink Tracker",
            "-- Generated by player_config.py",
            "",
            "local PLAYER_CONFIG = {"
        ]
        
        for key, value in config.items():
            if isinstance(value, str):
                lua_lines.append(f'    {key} = "{value}",')
            elif isinstance(value, bool):
                lua_lines.append(f'    {key} = {str(value).lower()},')
            elif isinstance(value, (int, float)):
                lua_lines.append(f'    {key} = {value},')
        
        lua_lines.extend([
            "}",
            "",
            "return {",
            "    PLAYER_CONFIG = PLAYER_CONFIG",
            "}"
        ])
        
        return '\n'.join(lua_lines)
    
    def list_configs(self) -> Dict[str, List[Path]]:
        """List all configuration files."""
        return {
            "watcher_configs": list(self.config_dir.glob("*_config.json")),
            "lua_configs": list((self.project_root / "client" / "lua" / "configs").glob("*_config.lua"))
        }
    
    def cleanup_old_configs(self):
        """Clean up old configuration files."""
        for config_file in self.config_dir.glob("*_config.json"):
            config_file.unlink()
            print(f"Removed old config: {config_file}")
        
        lua_config_dir = self.project_root / "client" / "lua" / "configs"
        if lua_config_dir.exists():
            for lua_file in lua_config_dir.glob("*_config.lua"):
                lua_file.unlink()
                print(f"Removed old Lua config: {lua_file}")


def main():
    """Main CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SoulLink Tracker Player Configuration Manager")
    parser.add_argument("--api-url", default="http://127.0.0.1:9000", help="API server URL")
    parser.add_argument("--watch-dir", help="Base directory for event files")
    parser.add_argument("--validate", metavar="CONFIG_FILE", help="Validate a configuration file")
    parser.add_argument("--test-api", metavar="CONFIG_FILE", help="Test API connectivity")
    parser.add_argument("--create-lua", action="store_true", help="Create Lua configuration files")
    parser.add_argument("--list", action="store_true", help="List all configuration files")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old configuration files")
    
    args = parser.parse_args()
    
    manager = PlayerConfigManager()
    
    if args.validate:
        config_file = Path(args.validate)
        if not config_file.exists():
            print(f"Configuration file not found: {config_file}")
            sys.exit(1)
        
        result = manager.validate_config(config_file)
        
        if result['errors']:
            print("[ERROR] Configuration errors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        if result['warnings']:
            print("[WARNING] Configuration warnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")
        
        if not result['errors']:
            print("[OK] Configuration is valid")
        
        sys.exit(1 if result['errors'] else 0)
    
    elif args.test_api:
        config_file = Path(args.test_api)
        if not config_file.exists():
            print(f"Configuration file not found: {config_file}")
            sys.exit(1)
        
        success = manager.test_api_connectivity(config_file)
        sys.exit(0 if success else 1)
    
    elif args.create_lua:
        try:
            lua_configs = manager.create_lua_configs()
            print(f"[OK] Created {len(lua_configs)} Lua configuration files")
        except Exception as e:
            print(f"[ERROR] Failed to create Lua configs: {e}")
            sys.exit(1)
    
    elif args.list:
        configs = manager.list_configs()
        print("Watcher configurations:")
        for config in configs['watcher_configs']:
            print(f"  - {config}")
        print("Lua configurations:")
        for config in configs['lua_configs']:
            print(f"  - {config}")
    
    elif args.cleanup:
        manager.cleanup_old_configs()
        print("[OK] Cleaned up old configuration files")
    
    else:
        # Default: create watcher configs
        try:
            config_files = manager.create_watcher_configs(
                api_base_url=args.api_url,
                watch_base_dir=args.watch_dir
            )
            
            print(f"[OK] Created {len(config_files)} watcher configuration files")
            
            # Validate all configs
            for config_file in config_files:
                result = manager.validate_config(config_file)
                if result['errors']:
                    print(f"[ERROR] Validation errors in {config_file.name}:")
                    for error in result['errors']:
                        print(f"  - {error}")
                else:
                    print(f"[OK] {config_file.name} is valid")
            
            # Test API connectivity for first config
            if config_files:
                print("\nTesting API connectivity...")
                success = manager.test_api_connectivity(config_files[0])
                if success:
                    print("[OK] API connectivity test passed")
                else:
                    print("[ERROR] API connectivity test failed")
        
        except Exception as e:
            print(f"[ERROR] Failed to create configurations: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()