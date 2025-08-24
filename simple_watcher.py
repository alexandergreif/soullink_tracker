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
from uuid import uuid4, uuid5, UUID, NAMESPACE_DNS
import re

# Import circuit breaker from watcher package if available
try:
    from watcher.src.soullink_watcher.circuit_breaker import CircuitBreaker, CircuitOpenError
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
if platform.system() == 'Windows':
    default_watch_dir = Path(os.environ.get('TEMP', 'C:/temp')) / 'soullink_events'
else:
    default_watch_dir = Path('/tmp/soullink_events')

CONFIG = {
    'api_base_url': 'http://127.0.0.1:8000',
    'watch_directory': str(default_watch_dir),
    'poll_interval': 2,  # seconds
    'max_retries': 3,
    'timeout': 10,
    'debug': True
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SimpleWatcher:
    def __init__(self):
        self.processed_files = set()
        self.run_id = None
        self.player_id = None
        self.player_token = None
        
        # Initialize circuit breaker for API requests
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60,
            reset_timeout_seconds=300  # 5 minutes
        )
        logger.info(f"Circuit breaker initialized (available: {CIRCUIT_BREAKER_AVAILABLE})")
    
    def make_http_request(self, method, url, **kwargs):
        """Make HTTP request with circuit breaker protection."""
        def make_request():
            if method.upper() == 'GET':
                return requests.get(url, **kwargs)
            elif method.upper() == 'POST':
                return requests.post(url, **kwargs)
            else:
                return requests.request(method, url, **kwargs)
        
        try:
            return self.circuit_breaker.call(make_request)
        except CircuitOpenError:
            logger.error(f"Circuit breaker is OPEN - failing fast for {url}")
            raise
    
    def retry_with_backoff(self, func, max_retries=None, base_delay=1.0, max_delay=60.0, jitter_ratio=0.1):
        """Retry a function with exponential backoff and jitter."""
        if max_retries is None:
            max_retries = CONFIG.get('max_retries', 3)
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except (requests.exceptions.RequestException, CircuitOpenError) as e:
                if attempt == max_retries:
                    logger.error(f"Final retry attempt failed: {e}")
                    raise
                
                # Calculate backoff delay
                delay = min(max_delay, base_delay * (2 ** attempt))
                jitter = random.uniform(-jitter_ratio, jitter_ratio) * delay
                delay = max(0.1, delay + jitter)
                
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
    
    def get_admin_info(self):
        """Get run and player information from the admin API."""
        try:
            # Get available runs
            response = self.make_http_request('GET', f"{CONFIG['api_base_url']}/v1/admin/runs", timeout=CONFIG['timeout'])
            if response.status_code == 200:
                runs = response.json()  # API returns list directly, not object with 'runs' key
                if runs and isinstance(runs, list):
                    # Use the first available run
                    run_data = runs[0]
                    self.run_id = run_data['id']
                    logger.info(f"Using run: {run_data['name']} ({self.run_id})")
                    
                    # Get players for this run
                    players_response = self.make_http_request('GET',
                        f"{CONFIG['api_base_url']}/v1/runs/{self.run_id}/players",
                        timeout=CONFIG['timeout']
                    )
                    if players_response.status_code == 200:
                        players = players_response.json()  # API returns list directly
                        if players and isinstance(players, list):
                            # Regular PlayerResponse doesn't include tokens for security
                            # We'll need to create a new player to get a token
                            logger.info(f"Found existing players, but no tokens available in PlayerResponse")
                            logger.info(f"Existing players: {[p['name'] for p in players]}")
                            return False  # Fall back to creating new player
                        else:
                            logger.error("No players found in run")
                    else:
                        logger.error(f"Failed to get players: {players_response.status_code}")
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
                'name': 'Test SoulLink Run',
                'description': 'Automated test run for Lua script testing',
                'rules': {
                    'dupe_clause': True,
                    'species_clause': True,
                    'nickname_clause': False
                }
            }
            
            response = self.make_http_request('POST',
                f"{CONFIG['api_base_url']}/v1/admin/runs",
                json=run_data,
                timeout=CONFIG['timeout']
            )
            
            if response.status_code == 201:
                run_result = response.json()
                self.run_id = run_result['id']  # RunResponse uses 'id', not 'run_id'
                logger.info(f"Created run: {self.run_id}")
                
                # Create a test player
                player_data = {
                    'name': 'TestPlayer',
                    'game': 'HeartGold',
                    'region': 'EU'
                }
                
                player_response = self.make_http_request('POST',
                    f"{CONFIG['api_base_url']}/v1/admin/runs/{self.run_id}/players",
                    json=player_data,
                    timeout=CONFIG['timeout']
                )
                
                if player_response.status_code == 201:
                    player_result = player_response.json()
                    self.player_id = player_result['id']  # PlayerWithTokenResponse uses 'id', not 'player_id'
                    self.player_token = player_result['new_token']  # PlayerWithTokenResponse uses 'new_token'
                    logger.info(f"Created player: {self.player_id}")
                    logger.info(f"Player token: {self.player_token[:20]}...")
                    return True
                else:
                    logger.error(f"Failed to create player: {player_response.status_code}")
                    logger.error(player_response.text)
            else:
                logger.error(f"Failed to create run: {response.status_code}")
                logger.error(response.text)
                
        except Exception as e:
            logger.error(f"Failed to create test run: {e}")
            
        return False
    
    def setup_run_player(self):
        """Setup run and player for event processing."""
        logger.info("Setting up run and player...")
        
        # First try to get existing run/player
        if self.get_admin_info():
            return True
            
        # If no runs exist, create a test run
        if self.create_test_run():
            return True
            
        logger.error("Failed to setup run and player")
        return False
    
    def normalize_timestamp(self, timestamp_str):
        """Normalize timestamp to ISO 8601 UTC format."""
        if not timestamp_str:
            return datetime.now(timezone.utc).isoformat()
        
        # If already in correct format (ends with Z or timezone), return as-is
        if timestamp_str.endswith('Z') or '+' in timestamp_str[-6:]:
            return timestamp_str
            
        # Try to parse various formats
        try:
            # Try parsing as ISO format without timezone
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except:
            # If parsing fails, use current time
            logger.warning(f"Could not parse timestamp '{timestamp_str}', using current time")
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
        if 'event_id' in event_data:
            # Validate existing event_id is UUID v4 or v5
            try:
                parsed = UUID(event_data['event_id'])
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
        if 'type' not in event_data:
            errors.append("Missing required field 'type'")
            return errors
        
        event_type = event_data['type']
        
        # Common required fields
        required_fields = ['run_id', 'player_id', 'time']
        for field in required_fields:
            if field not in event_data:
                errors.append(f"Missing required field '{field}'")
        
        # Type-specific validation
        if event_type == 'encounter':
            encounter_fields = ['route_id', 'species_id', 'level', 'shiny', 'method']
            for field in encounter_fields:
                if field not in event_data:
                    errors.append(f"Missing encounter field '{field}'")
            
            # Special validation for fishing events
            if event_data.get('method') == 'fish':
                if 'rod_kind' not in event_data:
                    errors.append("Fishing encounter must include 'rod_kind' field")
                elif event_data['rod_kind'] not in ['old', 'good', 'super']:
                    errors.append(f"Invalid rod_kind: {event_data['rod_kind']} (must be 'old', 'good', or 'super')")
        
        elif event_type == 'catch_result':
            # Must have either encounter_id or encounter_ref
            if 'encounter_id' not in event_data and 'encounter_ref' not in event_data:
                errors.append("catch_result must have either 'encounter_id' or 'encounter_ref'")
            
            # Must have either result or status
            if 'result' not in event_data and 'status' not in event_data:
                errors.append("catch_result must have either 'result' or 'status'")
            
            # Validate encounter_ref structure if present
            if 'encounter_ref' in event_data:
                ref = event_data['encounter_ref']
                if not isinstance(ref, dict):
                    errors.append("encounter_ref must be an object")
                elif 'route_id' not in ref or 'species_id' not in ref:
                    errors.append("encounter_ref must contain 'route_id' and 'species_id'")
        
        elif event_type == 'faint':
            faint_fields = ['pokemon_key']
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
                logger.error(f"File {file_path.name} too large ({file_size} bytes), skipping")
                # Move to error directory
                error_path = file_path.parent / "errors" / file_path.name
                error_path.parent.mkdir(exist_ok=True)
                file_path.rename(error_path)
                return False
            
            # Check if file is actually JSON (not binary or corrupted)
            try:
                # Read first few bytes to check for binary data
                with open(file_path, 'rb') as f:
                    header = f.read(min(100, file_size))
                    # Check for common binary file signatures
                    if header.startswith(b'\x00') or b'\xff\xfe' in header or b'\xfe\xff' in header:
                        logger.error(f"File {file_path.name} appears to be binary, not JSON")
                        error_path = file_path.parent / "errors" / file_path.name
                        error_path.parent.mkdir(exist_ok=True)
                        file_path.rename(error_path)
                        return False
            except Exception as e:
                logger.error(f"Could not read file {file_path.name}: {e}")
                return False
            
            # Read and parse JSON with error handling
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
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
            if 'run_id' not in event_data:
                event_data['run_id'] = self.run_id
            else:
                # Validate existing run_id
                try:
                    event_data['run_id'] = self.validate_uuid(event_data['run_id'], 'run_id')
                except ValueError as e:
                    logger.warning(f"Invalid run_id in event, using configured: {e}")
                    event_data['run_id'] = self.run_id
            
            if 'player_id' not in event_data:
                event_data['player_id'] = self.player_id
            else:
                # Validate existing player_id
                try:
                    event_data['player_id'] = self.validate_uuid(event_data['player_id'], 'player_id')
                except ValueError as e:
                    logger.warning(f"Invalid player_id in event, using configured: {e}")
                    event_data['player_id'] = self.player_id
            
            # Normalize timestamp
            if 'time' in event_data:
                event_data['time'] = self.normalize_timestamp(event_data['time'])
            else:
                event_data['time'] = datetime.now(timezone.utc).isoformat()
            
            # Handle method field normalization (V2 might use encounter_method)
            if 'encounter_method' in event_data and 'method' not in event_data:
                event_data['method'] = event_data.pop('encounter_method')
            
            # Normalize method values
            if 'method' in event_data:
                method_map = {
                    'walking': 'grass',
                    'grass': 'grass',
                    'surfing': 'surf',
                    'surf': 'surf',
                    'fishing': 'fish',
                    'fish': 'fish',
                    'static': 'static',
                    'unknown': 'unknown'
                }
                method = event_data['method'].lower()
                event_data['method'] = method_map.get(method, method)
            
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
                'Authorization': f'Bearer {self.player_token}',
                'Content-Type': 'application/json',
                'Idempotency-Key': idempotency_key
            }
            
            response = self.make_http_request('POST',
                f"{CONFIG['api_base_url']}/v1/events",
                json=event_data,
                headers=headers,
                timeout=CONFIG['timeout']
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Event sent successfully: {response.status_code}")
                # Move processed file to avoid reprocessing
                processed_path = file_path.with_suffix('.processed')
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
        watch_path = Path(CONFIG['watch_directory'])
        
        if not watch_path.exists():
            logger.warning(f"Watch directory doesn't exist: {watch_path}")
            return
        
        # Find JSON files that haven't been processed
        json_files = list(watch_path.glob('*.json'))
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
        
        # Setup run and player
        if not self.setup_run_player():
            logger.error("Failed to setup run and player, exiting")
            return False
        
        logger.info("Starting monitoring loop...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                self.scan_directory()
                time.sleep(CONFIG['poll_interval'])
                
        except KeyboardInterrupt:
            logger.info("\nStopping watcher...")
            return True
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SoulLink Event Watcher')
    parser.add_argument('--run-id', help='Run UUID')
    parser.add_argument('--player-id', help='Player UUID')
    parser.add_argument('--token', help='Player authentication token')
    parser.add_argument('--api-url', default='http://127.0.0.1:8000', help='API server URL')
    parser.add_argument('--watch-dir', help='Directory to watch for events')
    
    args = parser.parse_args()
    
    # Override config with command-line arguments
    if args.api_url:
        CONFIG['api_base_url'] = args.api_url
    if args.watch_dir:
        CONFIG['watch_directory'] = args.watch_dir
    
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
        logger.error(f"Make sure the SoulLink server is running at {CONFIG['api_base_url']}")
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

if __name__ == '__main__':
    sys.exit(main())