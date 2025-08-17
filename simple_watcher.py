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
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Configuration
CONFIG = {
    'api_base_url': 'http://127.0.0.1:8000',
    'watch_directory': 'C:/temp/soullink_events/',
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
        
    def get_admin_info(self):
        """Get run and player information from the admin API."""
        try:
            # Get available runs
            response = requests.get(f"{CONFIG['api_base_url']}/v1/admin/runs", timeout=CONFIG['timeout'])
            if response.status_code == 200:
                runs = response.json().get('runs', [])
                if runs:
                    # Use the first available run
                    run_data = runs[0]
                    self.run_id = run_data['id']
                    logger.info(f"Using run: {run_data['name']} ({self.run_id})")
                    
                    # Get players for this run
                    players_response = requests.get(
                        f"{CONFIG['api_base_url']}/v1/admin/runs/{self.run_id}/players",
                        timeout=CONFIG['timeout']
                    )
                    if players_response.status_code == 200:
                        players = players_response.json().get('players', [])
                        if players:
                            # Use the first available player
                            player_data = players[0]
                            self.player_id = player_data['id']
                            self.player_token = player_data.get('access_token', '')
                            logger.info(f"Using player: {player_data['name']} ({self.player_id})")
                            return True
                        else:
                            logger.error("No players found in run")
                    else:
                        logger.error(f"Failed to get players: {players_response.status_code}")
                else:
                    logger.error("No runs found")
            else:
                logger.error(f"Failed to get runs: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to get admin info: {e}")
            
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
            
            response = requests.post(
                f"{CONFIG['api_base_url']}/v1/admin/runs",
                json=run_data,
                timeout=CONFIG['timeout']
            )
            
            if response.status_code == 201:
                run_result = response.json()
                self.run_id = run_result['run_id']
                logger.info(f"Created run: {self.run_id}")
                
                # Create a test player
                player_data = {
                    'name': 'TestPlayer',
                    'game': 'HeartGold',
                    'region': 'EU'
                }
                
                player_response = requests.post(
                    f"{CONFIG['api_base_url']}/v1/admin/runs/{self.run_id}/players",
                    json=player_data,
                    timeout=CONFIG['timeout']
                )
                
                if player_response.status_code == 201:
                    player_result = player_response.json()
                    self.player_id = player_result['player_id']
                    self.player_token = player_result['access_token']
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
    
    def process_json_file(self, file_path):
        """Process a single JSON event file."""
        try:
            with open(file_path, 'r') as f:
                event_data = json.load(f)
            
            # Add required fields for V3 API
            if 'run_id' not in event_data:
                event_data['run_id'] = self.run_id
            if 'player_id' not in event_data:
                event_data['player_id'] = self.player_id
            
            # Generate event_id if missing
            if 'event_id' not in event_data:
                event_data['event_id'] = str(uuid4())
            
            # Convert 'time' to 'timestamp' if needed
            if 'time' in event_data and 'timestamp' not in event_data:
                event_data['timestamp'] = event_data['time']
            
            logger.info(f"Processing event: {event_data['type']} from {file_path.name}")
            
            # Send to API
            headers = {
                'Authorization': f'Bearer {self.player_token}',
                'Content-Type': 'application/json',
                'Idempotency-Key': str(uuid4())
            }
            
            response = requests.post(
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
    # Check if server is running
    try:
        response = requests.get(f"{CONFIG['api_base_url']}/health", timeout=5)
        if response.status_code != 200:
            logger.error(f"Server health check failed: {response.status_code}")
            logger.error("Make sure the SoulLink server is running first!")
            return 1
    except Exception as e:
        logger.error(f"Cannot connect to server: {e}")
        logger.error("Make sure the SoulLink server is running at http://127.0.0.1:8000")
        return 1
    
    logger.info("✅ Server is running and accessible")
    
    # Start the watcher
    watcher = SimpleWatcher()
    success = watcher.run()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())