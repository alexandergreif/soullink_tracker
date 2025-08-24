#!/usr/bin/env python3
"""
Simple SoulLink Event Watcher
Monitors JSON files from Lua script and sends them to the API server

This is a simplified version that doesn't require complex watcher setup.
Just run this script and it will automatically process events.
"""

import os
import sys
import time
import json
import requests
import logging
import random
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid5, UUID, NAMESPACE_DNS
import re

# Import circuit breaker from watcher package if available
try:
    from watcher.src.soullink_watcher.circuit_breaker import (
        CircuitBreaker,
        CircuitOpenError,
    )

    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

    # Fallback dummy classes
    class CircuitBreaker:
        def __init__(self, *args, **kwargs):
            pass

        def call(self, func):
            return func()

        def get_stats(self):
            return {"state": "disabled"}

    class CircuitOpenError(Exception):
        pass


# Configuration
# Determine default watch directory based on platform
import platform

if platform.system() == "Windows":
    default_watch_dir = Path(os.environ.get("TEMP", "C:/temp")) / "soullink_events"
else:
    default_watch_dir = Path("/tmp/soullink_events")

CONFIG = {
    "api_base_url": "http://127.0.0.1:8000",
    "watch_directory": str(default_watch_dir),
    "poll_interval": 2,  # seconds
    "max_retries": 3,
    "timeout": 10,
    "debug": True,
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class SimpleWatcher:
    def __init__(self):
        self.processed_files = set()
        self.run_id = None
        self.player_id = None
        self.player_token = None
        self.config_lua_path = None

        # Initialize circuit breaker for API requests
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60,
            reset_timeout_seconds=300,  # 5 minutes
        )
        logger.info(
            f"Circuit breaker initialized (available: {CIRCUIT_BREAKER_AVAILABLE})"
        )
    
    def setup_watch_directory(self):
        """Create watch directory if it doesn't exist and verify write access."""
        watch_path = Path(CONFIG["watch_directory"])
        
        # Log OS detection info
        logger.info(f"Operating System: {platform.system()}")
        logger.info(f"Platform Details: {platform.platform()}")
        
        # Try to create directory if it doesn't exist
        try:
            watch_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Watch directory exists: {watch_path}")
        except Exception as e:
            logger.error(f"❌ Failed to create watch directory: {e}")
            
            # Provide OS-specific instructions
            if platform.system() == "Windows":
                logger.error("\nTo create the directory manually on Windows:")
                logger.error(f'  PowerShell: New-Item -ItemType Directory -Force -Path "{watch_path}"')
                logger.error(f'  CMD: mkdir "{watch_path}"')
            else:
                logger.error("\nTo create the directory manually:")
                logger.error(f'  mkdir -p "{watch_path}"')
            return False
        
        # Test write access
        test_file = watch_path / f"watcher_test_{os.getpid()}_{int(time.time())}.json"
        try:
            test_data = {
                "type": "test",
                "message": "Watcher startup test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
                "platform": platform.system()
            }
            
            with open(test_file, "w") as f:
                json.dump(test_data, f, indent=2)
            
            logger.info(f"✅ Directory is writable - test file created: {test_file.name}")
            
            # Clean up test file
            test_file.unlink()
            
        except Exception as e:
            logger.error(f"❌ Cannot write to watch directory: {e}")
            logger.error("Please check directory permissions")
            return False
        
        # Create subdirectories for organization
        subdirs = ["processed", "errors"]
        for subdir in subdirs:
            subdir_path = watch_path / subdir
            try:
                subdir_path.mkdir(exist_ok=True)
                logger.debug(f"  Created subdirectory: {subdir}")
            except Exception as e:
                logger.warning(f"  Could not create {subdir} subdirectory: {e}")
        
        # Also update config.lua if found to use this directory
        self.update_lua_config_directory(watch_path)
        
        return True
    
    def update_lua_config_directory(self, watch_path):
        """Update config.lua to use the correct output directory."""
        # Try to find config.lua
        possible_paths = [
            Path("client/lua/config.lua"),
            Path("lua/config.lua"),
            Path("config.lua"),
        ]
        
        config_exists = False
        for path in possible_paths:
            if path.exists():
                self.config_lua_path = path
                config_exists = True
                break
        
        # If no config.lua exists, create one from template
        if not config_exists:
            self.create_default_lua_config(watch_path)
            return
        
        if self.config_lua_path and self.config_lua_path.exists():
            try:
                # Read current config
                with open(self.config_lua_path, "r") as f:
                    content = f.read()
                
                # Update output_dir line
                import re
                # Convert path to forward slashes for Lua
                lua_path = str(watch_path).replace("\\", "/")
                if not lua_path.endswith("/"):
                    lua_path += "/"
                
                # Update the output_dir line
                new_content = re.sub(
                    r'output_dir\s*=\s*["\'][^"^\']*["\']',
                    f'output_dir = "{lua_path}"',
                    content
                )
                
                if new_content != content:
                    # Write updated config
                    with open(self.config_lua_path, "w") as f:
                        f.write(new_content)
                    logger.info(f"✅ Updated {self.config_lua_path} with output_dir: {lua_path}")
                else:
                    logger.debug(f"Config.lua already has correct output_dir")
                    
            except Exception as e:
                logger.warning(f"Could not update config.lua: {e}")
    
    def create_default_lua_config(self, watch_path):
        """Create a default config.lua file with auto-detected settings."""
        config_dir = Path("client/lua")
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.lua"
        
        # Convert path to forward slashes for Lua
        lua_path = str(watch_path).replace("\\", "/")
        if not lua_path.endswith("/"):
            lua_path += "/"
        
        config_content = f"""-- Auto-generated SoulLink Tracker Configuration
-- Created by watcher at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

return {{
    -- API server settings
    api_base_url = "http://127.0.0.1:8000",
    
    -- IMPORTANT: Replace these with your actual UUIDs from the admin panel
    -- Get these from http://127.0.0.1:8000/admin
    run_id = "{self.run_id or 'REPLACE_WITH_YOUR_RUN_ID'}",
    player_id = "{self.player_id or 'REPLACE_WITH_YOUR_PLAYER_ID'}",
    
    -- Auto-detected output directory for your OS
    output_dir = "{lua_path}",
    
    -- Optional settings
    poll_interval = 60,  -- Frames between checks (60 = 1 second)
    debug = true,        -- Enable debug logging
    max_runtime = 3600,  -- Max runtime in seconds (0 = unlimited)
    memory_profile = "US" -- ROM version: "US" or "EU"
}}
"""
        
        try:
            with open(config_path, "w") as f:
                f.write(config_content)
            logger.info(f"✅ Created default config.lua at: {config_path}")
            logger.info(f"   Output directory: {lua_path}")
            if not self.run_id:
                logger.warning("   ⚠️  Remember to update run_id and player_id from the admin panel!")
            self.config_lua_path = config_path
        except Exception as e:
            logger.error(f"Failed to create config.lua: {e}")

    def make_http_request(self, method, url, **kwargs):
        """Make HTTP request with circuit breaker protection."""

        def make_request():
            if method.upper() == "GET":
                return requests.get(url, **kwargs)
            elif method.upper() == "POST":
                return requests.post(url, **kwargs)
            else:
                return requests.request(method, url, **kwargs)

        try:
            return self.circuit_breaker.call(make_request)
        except CircuitOpenError:
            logger.error(f"Circuit breaker is OPEN - failing fast for {url}")
            raise

    def read_config_lua(self):
        """Read config.lua file and extract run_id and player_id.

        Returns:
            tuple: (run_id, player_id, config_path) or (None, None, None) if failed
        """
        # Try multiple possible paths for config.lua
        possible_paths = [
            Path("client/lua/config.lua"),  # From project root
            Path("../client/lua/config.lua"),  # If running from client/ directory
            Path("lua/config.lua"),  # If running from client/ directory
            Path("config.lua"),  # Same directory as watcher
        ]

        # Add current script directory path
        script_dir = Path(__file__).parent
        possible_paths.append(script_dir / "lua" / "config.lua")
        possible_paths.append(script_dir.parent / "client" / "lua" / "config.lua")

        for config_path in possible_paths:
            try:
                if config_path.exists():
                    logger.info(f"🔍 Found config.lua at: {config_path}")

                    # Read the Lua config file
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Simple Lua table parsing for our specific format
                    run_id = None
                    player_id = None

                    # Extract run_id using regex
                    run_match = re.search(
                        r'run_id\s*=\s*["\']([a-fA-F0-9\-]+)["\']', content
                    )
                    if run_match:
                        run_id = run_match.group(1).strip()

                    # Extract player_id using regex
                    player_match = re.search(
                        r'player_id\s*=\s*["\']([a-fA-F0-9\-]+)["\']', content
                    )
                    if player_match:
                        player_id = player_match.group(1).strip()

                    # Validate extracted UUIDs
                    if run_id and player_id:
                        try:
                            # Validate UUID format
                            UUID(run_id)
                            UUID(player_id)

                            # Check for placeholder values
                            if "REPLACE_WITH" in run_id or "MISSING_" in run_id:
                                logger.warning(
                                    f"⚠️  config.lua contains placeholder run_id: {run_id}"
                                )
                                continue
                            if "REPLACE_WITH" in player_id or "MISSING_" in player_id:
                                logger.warning(
                                    f"⚠️  config.lua contains placeholder player_id: {player_id}"
                                )
                                continue

                            logger.info("✅ Successfully loaded config.lua:")
                            logger.info(f"   📍 Path: {config_path}")
                            logger.info(f"   🎯 Run ID: {run_id}")
                            logger.info(f"   👤 Player ID: {player_id}")

                            self.config_lua_path = config_path
                            return run_id, player_id, config_path

                        except ValueError as e:
                            logger.error(f"❌ Invalid UUID format in config.lua: {e}")
                            continue
                    else:
                        logger.warning(
                            f"⚠️  Could not extract run_id or player_id from {config_path}"
                        )
                        continue

            except Exception as e:
                logger.debug(f"Could not read {config_path}: {e}")
                continue

        logger.warning("⚠️  No valid config.lua found in any of these locations:")
        for path in possible_paths:
            logger.warning(
                f"   • {path} {'(exists)' if path.exists() else '(not found)'}"
            )

        return None, None, None

    def validate_config_in_database(self, run_id, player_id):
        """Validate that run_id and player_id exist in database and get player token.

        Returns:
            str: player_token if validation successful, None if failed
        """
        try:
            logger.info("🔍 Validating config UUIDs in database...")

            # Check if run exists
            response = self.make_http_request(
                "GET",
                f"{CONFIG['api_base_url']}/v1/admin/runs",
                timeout=CONFIG["timeout"],
            )

            if response.status_code != 200:
                logger.error(
                    f"❌ Failed to get runs from database: {response.status_code}"
                )
                return None

            runs = response.json()
            run_found = None
            for run in runs:
                if run["id"] == run_id:
                    run_found = run
                    break

            if not run_found:
                logger.error(f"❌ Run ID {run_id} not found in database")
                return None

            logger.info(f"✅ Run found: {run_found['name']} ({run_id})")

            # Check if player exists in this run
            players_response = self.make_http_request(
                "GET",
                f"{CONFIG['api_base_url']}/v1/runs/{run_id}/players",
                timeout=CONFIG["timeout"],
            )

            if players_response.status_code != 200:
                logger.error(
                    f"❌ Failed to get players for run: {players_response.status_code}"
                )
                return None

            players_data = players_response.json()
            players = players_data.get("players", [])
            player_found = None
            for player in players:
                if player["id"] == player_id:
                    player_found = player
                    break

            if not player_found:
                logger.error(f"❌ Player ID {player_id} not found in run {run_id}")
                return None

            logger.info(f"✅ Player found: {player_found['name']} ({player_id})")

            # Since PlayerResponse doesn't include tokens, we need to create a new token
            # This is a security limitation - tokens are only shown once during creation
            logger.warning("⚠️  Config validation successful, but no token available")
            logger.warning(
                "   Player tokens are not stored in PlayerResponse for security"
            )
            logger.warning("   Will need to create new player or get token another way")

            return "CONFIG_VALIDATED"  # Special marker indicating validation passed

        except Exception as e:
            logger.error(f"❌ Database validation error: {e}")
            return None

    def retry_with_backoff(
        self, func, max_retries=None, base_delay=1.0, max_delay=60.0, jitter_ratio=0.1
    ):
        """Retry a function with exponential backoff and jitter."""
        if max_retries is None:
            max_retries = CONFIG.get("max_retries", 3)

        for attempt in range(max_retries + 1):
            try:
                return func()
            except (requests.exceptions.RequestException, CircuitOpenError) as e:
                if attempt == max_retries:
                    logger.error(f"Final retry attempt failed: {e}")
                    raise

                # Calculate backoff delay
                delay = min(max_delay, base_delay * (2**attempt))
                jitter = random.uniform(-jitter_ratio, jitter_ratio) * delay
                delay = max(0.1, delay + jitter)

                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)

    def get_admin_info(self):
        """Get run and player information from the admin API."""
        try:
            # Get available runs
            response = self.make_http_request(
                "GET",
                f"{CONFIG['api_base_url']}/v1/admin/runs",
                timeout=CONFIG["timeout"],
            )
            if response.status_code == 200:
                runs = (
                    response.json()
                )  # API returns list directly, not object with 'runs' key
                if runs and isinstance(runs, list):
                    # Use the first available run
                    run_data = runs[0]
                    self.run_id = run_data["id"]
                    logger.info(f"Using run: {run_data['name']} ({self.run_id})")

                    # Get players for this run
                    players_response = self.make_http_request(
                        "GET",
                        f"{CONFIG['api_base_url']}/v1/runs/{self.run_id}/players",
                        timeout=CONFIG["timeout"],
                    )
                    if players_response.status_code == 200:
                        players_data = (
                            players_response.json()
                        )  # API returns {"players": [...]}
                        players = players_data.get("players", [])
                        if players and isinstance(players, list):
                            # Regular PlayerResponse doesn't include tokens for security
                            # We'll need to create a new player to get a token
                            logger.info(
                                "Found existing players, but no tokens available in PlayerResponse"
                            )
                            logger.info(
                                f"Existing players: {[p['name'] for p in players]}"
                            )
                            return False  # Fall back to creating new player
                        else:
                            logger.error("No players found in run")
                    else:
                        logger.error(
                            f"Failed to get players: {players_response.status_code}"
                        )
                        logger.error(f"Players response: {players_response.text}")
                else:
                    logger.error("No runs found")
            else:
                logger.error(f"Failed to get runs: {response.status_code}")
                logger.error(f"Response: {response.text}")

        except Exception as e:
            logger.error(f"Failed to get admin info: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

        return False

    def create_test_run(self):
        """Create a test run and player if none exist."""
        try:
            logger.info("Creating test run and player...")

            # Create a test run
            run_data = {
                "name": "Test SoulLink Run",
                "description": "Automated test run for Lua script testing",
                "rules": {
                    "dupe_clause": True,
                    "species_clause": True,
                    "nickname_clause": False,
                },
            }

            response = self.make_http_request(
                "POST",
                f"{CONFIG['api_base_url']}/v1/admin/runs",
                json=run_data,
                timeout=CONFIG["timeout"],
            )

            if response.status_code == 201:
                run_result = response.json()
                self.run_id = run_result["id"]  # RunResponse uses 'id', not 'run_id'
                logger.info(f"Created run: {self.run_id}")

                # Create a test player
                player_data = {
                    "name": "TestPlayer",
                    "game": "HeartGold",
                    "region": "EU",
                }

                player_response = self.make_http_request(
                    "POST",
                    f"{CONFIG['api_base_url']}/v1/admin/runs/{self.run_id}/players",
                    json=player_data,
                    timeout=CONFIG["timeout"],
                )

                if player_response.status_code == 201:
                    player_result = player_response.json()
                    self.player_id = player_result[
                        "id"
                    ]  # PlayerWithTokenResponse uses 'id', not 'player_id'
                    self.player_token = player_result[
                        "new_token"
                    ]  # PlayerWithTokenResponse uses 'new_token'
                    logger.info(f"Created player: {self.player_id}")
                    logger.info(f"Player token: {self.player_token[:20]}...")
                    return True
                else:
                    logger.error(
                        f"Failed to create player: {player_response.status_code}"
                    )
                    logger.error(player_response.text)
            else:
                logger.error(f"Failed to create run: {response.status_code}")
                logger.error(response.text)

        except Exception as e:
            logger.error(f"Failed to create test run: {e}")

        return False

    def setup_run_player(self):
        """Setup run and player for event processing."""
        logger.info("🚀 Setting up run and player...")

        # STEP 1: Try to read config.lua first
        logger.info("🔄 STEP 1: Attempting to read config.lua...")
        config_run_id, config_player_id, config_path = self.read_config_lua()

        if config_run_id and config_player_id:
            logger.info("✅ Found valid UUIDs in config.lua")

            # STEP 2: Validate these UUIDs exist in database
            logger.info("🔄 STEP 2: Validating config UUIDs in database...")
            validation_result = self.validate_config_in_database(
                config_run_id, config_player_id
            )

            if validation_result == "CONFIG_VALIDATED":
                # Use the config UUIDs but we still need a token
                self.run_id = config_run_id
                self.player_id = config_player_id

                logger.info("✅ Config UUIDs validated successfully!")
                logger.info(f"   🎯 Using Run ID: {self.run_id}")
                logger.info(f"   👤 Using Player ID: {self.player_id}")

                # For now, we'll need to create a temporary test run to get a token
                # This is a limitation - tokens are only provided during player creation
                logger.warning(
                    "⚠️  Need to create temporary player for authentication token"
                )
                logger.warning(
                    "   This is a current limitation - tokens aren't stored in database responses"
                )
                logger.warning(
                    "   Config IDs will be IGNORED - using temporary IDs that match the token"
                )

                # Store config IDs for reference (but won't use them)
                config_run_id_original = self.run_id
                config_player_id_original = self.player_id

                # Try to create a temporary player to get a token
                # This will OVERWRITE self.run_id and self.player_id with temporary values
                if self.create_test_run():  # This creates temporary credentials
                    # Use the temporary credentials consistently - no mixing!
                    # self.run_id and self.player_id already set by create_test_run()
                    # self.player_token already set by create_test_run()

                    logger.info("✅ Using TEMPORARY credentials for authentication")
                    logger.info(
                        f"   🔄 Config run_id {config_run_id_original} → Temporary: {self.run_id}"
                    )
                    logger.info(
                        f"   🔄 Config player_id {config_player_id_original} → Temporary: {self.player_id}"
                    )
                    logger.info(
                        "   ⚠️  All events will be submitted with temporary IDs to match the auth token"
                    )
                    return True

        # STEP 3: Fallback to getting existing run/player from admin API
        logger.info(
            "🔄 STEP 3: Fallback - trying to get existing run/player from admin API..."
        )
        if self.get_admin_info():
            logger.info("✅ Successfully configured from existing run/player")
            return True

        # STEP 4: Last resort - create a test run
        logger.info("🔄 STEP 4: Last resort - creating new test run...")
        if self.create_test_run():
            logger.info("✅ Successfully created test run and player")
            return True

        logger.error("❌ Failed to setup run and player after all attempts")
        return False

    def normalize_timestamp(self, timestamp_str):
        """Normalize timestamp to ISO 8601 UTC format."""
        if not timestamp_str:
            return datetime.now(timezone.utc).isoformat()

        # If already in correct format (ends with Z or timezone), return as-is
        if timestamp_str.endswith("Z") or "+" in timestamp_str[-6:]:
            return timestamp_str

        # Try to parse various formats
        try:
            # Try parsing as ISO format without timezone
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            # If parsing fails, use current time
            logger.warning(
                f"Could not parse timestamp '{timestamp_str}', using current time"
            )
            return datetime.now(timezone.utc).isoformat()

    def validate_uuid(self, value, field_name):
        """Validate and normalize UUID string."""
        if not value:
            raise ValueError(f"{field_name} is required")

        # If already a valid UUID string, return it
        if isinstance(value, str):
            try:
                # Validate UUID format
                UUID(value)
                return value
            except ValueError:
                raise ValueError(f"{field_name} must be a valid UUID, got: {value}")

        raise ValueError(f"{field_name} must be a string UUID, got type: {type(value)}")

    def generate_idempotency_key(self, event_data, file_path):
        """Generate RFC 4122 compliant UUID v4/v5 for idempotency.

        Uses deterministic UUID v5 generation to ensure same event content
        generates same UUID for reliable retry behavior.
        """
        if "event_id" in event_data:
            # Validate existing event_id is UUID v4 or v5
            try:
                parsed = UUID(event_data["event_id"])
                if parsed.version in [4, 5]:
                    return str(parsed)
            except (ValueError, AttributeError):
                pass  # Fall through to generate new UUID

        # Create deterministic UUID v5 from event content
        # This ensures same event generates same UUID for retries
        event_str = f"{event_data['type']}_{event_data['player_id']}_{event_data.get('time', '')}_{file_path.name}"
        return str(uuid5(NAMESPACE_DNS, event_str))

    def validate_event(self, event_data):
        """Validate event data before sending to API."""
        errors = []

        # Check event type
        if "type" not in event_data:
            errors.append("Missing required field 'type'")
            return errors

        event_type = event_data["type"]

        # Common required fields
        required_fields = ["run_id", "player_id", "time"]
        for field in required_fields:
            if field not in event_data:
                errors.append(f"Missing required field '{field}'")

        # Type-specific validation
        if event_type == "encounter":
            encounter_fields = ["route_id", "species_id", "level", "shiny", "method"]
            for field in encounter_fields:
                if field not in event_data:
                    errors.append(f"Missing encounter field '{field}'")

            # Special validation for fishing events
            if event_data.get("method") == "fish":
                if "rod_kind" not in event_data:
                    errors.append("Fishing encounter must include 'rod_kind' field")
                elif event_data["rod_kind"] not in ["old", "good", "super"]:
                    errors.append(
                        f"Invalid rod_kind: {event_data['rod_kind']} (must be 'old', 'good', or 'super')"
                    )

        elif event_type == "catch_result":
            # Must have either encounter_id or encounter_ref
            if "encounter_id" not in event_data and "encounter_ref" not in event_data:
                errors.append(
                    "catch_result must have either 'encounter_id' or 'encounter_ref'"
                )

            # Must have either result or status
            if "result" not in event_data and "status" not in event_data:
                errors.append("catch_result must have either 'result' or 'status'")

            # Validate encounter_ref structure if present
            if "encounter_ref" in event_data:
                ref = event_data["encounter_ref"]
                if not isinstance(ref, dict):
                    errors.append("encounter_ref must be an object")
                elif "route_id" not in ref or "species_id" not in ref:
                    errors.append(
                        "encounter_ref must contain 'route_id' and 'species_id'"
                    )

        elif event_type == "faint":
            faint_fields = ["pokemon_key"]
            for field in faint_fields:
                if field not in event_data:
                    errors.append(f"Missing faint field '{field}'")

        return errors

    def process_json_file(self, file_path):
        """Process a single JSON event file with enhanced edge case handling."""
        try:
            # Check file size to prevent DoS from huge files
            file_size = file_path.stat().st_size
            if file_size > 1024 * 1024:  # 1MB limit
                logger.error(
                    f"File {file_path.name} too large ({file_size} bytes), skipping"
                )
                # Move to error directory
                error_path = file_path.parent / "errors" / file_path.name
                error_path.parent.mkdir(exist_ok=True)
                file_path.rename(error_path)
                return False

            # Check if file is actually JSON (not binary or corrupted)
            try:
                # Read first few bytes to check for binary data
                with open(file_path, "rb") as f:
                    header = f.read(min(100, file_size))
                    # Check for common binary file signatures
                    if (
                        header.startswith(b"\x00")
                        or b"\xff\xfe" in header
                        or b"\xfe\xff" in header
                    ):
                        logger.error(
                            f"File {file_path.name} appears to be binary, not JSON"
                        )
                        error_path = file_path.parent / "errors" / file_path.name
                        error_path.parent.mkdir(exist_ok=True)
                        file_path.rename(error_path)
                        return False
            except Exception as e:
                logger.error(f"Could not read file {file_path.name}: {e}")
                return False

            # Read and parse JSON with error handling
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    event_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {file_path.name}: {e}")
                # Move corrupted file to errors directory
                error_path = file_path.parent / "errors" / file_path.name
                error_path.parent.mkdir(exist_ok=True)
                file_path.rename(error_path)
                return False
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error in {file_path.name}: {e}")
                error_path = file_path.parent / "errors" / file_path.name
                error_path.parent.mkdir(exist_ok=True)
                file_path.rename(error_path)
                return False

            # Add required fields for V3 API
            # ALWAYS use the watcher's credentials (temporary or configured)
            # to match the authentication token we're using
            original_run_id = event_data.get("run_id")
            original_player_id = event_data.get("player_id")

            event_data["run_id"] = self.run_id
            event_data["player_id"] = self.player_id

            # Log if we're overriding IDs from the event
            if original_run_id and original_run_id != self.run_id:
                logger.debug(
                    f"Overriding event run_id: {original_run_id} → {self.run_id}"
                )
            if original_player_id and original_player_id != self.player_id:
                logger.debug(
                    f"Overriding event player_id: {original_player_id} → {self.player_id}"
                )

            # Normalize timestamp
            if "time" in event_data:
                event_data["time"] = self.normalize_timestamp(event_data["time"])
            else:
                event_data["time"] = datetime.now(timezone.utc).isoformat()

            # Handle method field normalization (V2 might use encounter_method)
            if "encounter_method" in event_data and "method" not in event_data:
                event_data["method"] = event_data.pop("encounter_method")

            # Normalize method values
            if "method" in event_data:
                method_map = {
                    "walking": "grass",
                    "grass": "grass",
                    "surfing": "surf",
                    "surf": "surf",
                    "fishing": "fish",
                    "fish": "fish",
                    "static": "static",
                    "unknown": "unknown",
                }
                method = event_data["method"].lower()
                event_data["method"] = method_map.get(method, method)

            # Validate event before sending
            validation_errors = self.validate_event(event_data)
            if validation_errors:
                logger.error(f"Event validation failed for {file_path.name}:")
                for error in validation_errors:
                    logger.error(f"  - {error}")
                logger.debug(f"Event data: {json.dumps(event_data, indent=2)}")
                return False

            logger.info(f"Processing event: {event_data['type']} from {file_path.name}")

            # Generate RFC 4122 compliant idempotency key
            idempotency_key = self.generate_idempotency_key(event_data, file_path)

            # Send to API
            headers = {
                "Authorization": f"Bearer {self.player_token}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            }

            response = self.make_http_request(
                "POST",
                f"{CONFIG['api_base_url']}/v1/events",
                json=event_data,
                headers=headers,
                timeout=CONFIG["timeout"],
            )

            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Event sent successfully: {response.status_code}")
                # Move processed file to avoid reprocessing
                processed_path = file_path.with_suffix(".processed")
                file_path.rename(processed_path)
                return True
            else:
                logger.error(f"❌ API error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False

    def scan_directory(self):
        """Scan for new JSON files and process them."""
        watch_path = Path(CONFIG["watch_directory"])

        if not watch_path.exists():
            logger.warning(f"Watch directory doesn't exist: {watch_path}")
            return

        # Find JSON files that haven't been processed
        json_files = list(watch_path.glob("*.json"))
        new_files = [f for f in json_files if f not in self.processed_files]

        if new_files:
            logger.info(f"Found {len(new_files)} new event files")

            for file_path in new_files:
                if self.process_json_file(file_path):
                    self.processed_files.add(file_path)

        elif len(json_files) == 0:
            logger.debug("No JSON files found in watch directory")

    def run(self):
        """Main monitoring loop."""
        logger.info("=== Simple SoulLink Event Watcher ===")
        logger.info(f"API Server: {CONFIG['api_base_url']}")
        logger.info(f"Watch Directory: {CONFIG['watch_directory']}")
        logger.info(f"Poll Interval: {CONFIG['poll_interval']} seconds")
        
        # Verify or create watch directory
        if not self.setup_watch_directory():
            return False

        # Setup run and player
        if not self.setup_run_player():
            logger.error("Failed to setup run and player, exiting")
            return False

        logger.info("Starting monitoring loop...")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                self.scan_directory()
                time.sleep(CONFIG["poll_interval"])

        except KeyboardInterrupt:
            logger.info("\nStopping watcher...")
            return True
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SoulLink Event Watcher")
    parser.add_argument("--run-id", help="Run UUID")
    parser.add_argument("--player-id", help="Player UUID")
    parser.add_argument("--token", help="Player authentication token")
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000", help="API server URL"
    )
    parser.add_argument("--watch-dir", help="Directory to watch for events")

    args = parser.parse_args()

    # Override config with command-line arguments
    if args.api_url:
        CONFIG["api_base_url"] = args.api_url
    if args.watch_dir:
        CONFIG["watch_directory"] = args.watch_dir

    # Check if server is running
    logger.info("Checking server status...")
    try:
        response = requests.get(f"{CONFIG['api_base_url']}/health", timeout=5)
        if response.status_code != 200:
            logger.error(f"Server health check failed: {response.status_code}")
            logger.error("Make sure the SoulLink server is running first!")
            return 1
    except Exception as e:
        logger.error(f"Cannot connect to server: {e}")
        logger.error(
            f"Make sure the SoulLink server is running at {CONFIG['api_base_url']}"
        )
        return 1

    logger.info("✅ Server is running and accessible")

    # Start the watcher
    watcher = SimpleWatcher()

    # Set credentials if provided via command line
    if args.run_id:
        watcher.run_id = args.run_id
        logger.info(f"Using run_id from command line: {args.run_id}")
    if args.player_id:
        watcher.player_id = args.player_id
        logger.info(f"Using player_id from command line: {args.player_id}")
    if args.token:
        watcher.player_token = args.token
        logger.info("Using token from command line")

    success = watcher.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
