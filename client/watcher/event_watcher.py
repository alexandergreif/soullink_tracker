#!/usr/bin/env python3
"""
SoulLink Tracker - Event Watcher
Monitors JSON event files from DeSmuME Lua scripts and sends them to the API server.

This script bridges the gap between the Lua scripts running in DeSmuME and the
SoulLink Tracker API by:
1. Monitoring a directory for new JSON event files
2. Reading and validating event data
3. Sending events to the API with proper authentication
4. Handling retries and error cases
5. Cleaning up processed files
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

import aiofiles
import aiohttp
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from soullink_tracker.api.schemas import EventEncounter, EventCatchResult, EventFaint


class EventWatcher:
    """Main event watcher class that monitors and processes JSON files."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_files: Set[str] = set()
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        
        # Rate limiting
        self.last_event_time = 0
        self.events_this_minute = 0
        self.minute_start = time.time()
        
        # Health monitoring
        self.stats = {
            'events_processed': 0,
            'events_failed': 0,
            'api_errors': 0,
            'files_processed': 0,
            'last_event_time': None,
            'started_at': datetime.now(timezone.utc)
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('soullink_watcher')
        logger.setLevel(logging.DEBUG if self.config.get('debug', False) else logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # File handler if configured
        log_file = self.config.get('log_file')
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    async def start(self):
        """Start the event watcher."""
        self.logger.info(f"Starting SoulLink Event Watcher for player: {self.config['player_name']}")
        self.logger.info(f"Monitoring directory: {self.config['watch_directory']}")
        self.logger.info(f"API server: {self.config['api_base_url']}")
        
        # Create directories
        Path(self.config['watch_directory']).mkdir(parents=True, exist_ok=True)
        
        # Initialize HTTP session
        timeout = aiohttp.ClientTimeout(total=self.config.get('connection_timeout', 10))
        connector = aiohttp.TCPConnector(limit=10)
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': f"SoulLinkWatcher/1.0 ({self.config['player_name']})",
                'Authorization': f"Bearer {self.config['player_token']}"
            }
        )
        
        # Test API connectivity
        await self._test_api_connection()
        
        # Start file system monitoring
        self.running = True
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._process_event_queue()),
            asyncio.create_task(self._monitor_existing_files()),
            asyncio.create_task(self._start_file_watcher()),
            asyncio.create_task(self._periodic_health_check())
        ]
        
        self.logger.info("Event watcher started successfully")
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the event watcher."""
        self.logger.info("Stopping event watcher...")
        self.running = False
        
        if self.session:
            await self.session.close()
        
        self.logger.info("Event watcher stopped")
    
    async def _test_api_connection(self):
        """Test connectivity to the API server."""
        try:
            url = f"{self.config['api_base_url']}/health"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"API connection successful: {data.get('service', 'unknown')} v{data.get('version', 'unknown')}")
                else:
                    raise aiohttp.ClientError(f"API health check failed: {response.status}")
        except Exception as e:
            self.logger.error(f"API connection test failed: {e}")
            raise
    
    async def _start_file_watcher(self):
        """Start watching the directory for new files."""
        
        class EventFileHandler(FileSystemEventHandler):
            def __init__(self, watcher):
                self.watcher = watcher
            
            def on_created(self, event):
                if event.is_directory:
                    return
                
                file_path = Path(event.src_path)
                if file_path.suffix.lower() == '.json' and file_path.name.startswith('event_'):
                    asyncio.create_task(self.watcher._queue_file_for_processing(file_path))
        
        event_handler = EventFileHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.config['watch_directory'], recursive=False)
        observer.start()
        
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            observer.stop()
            observer.join()
    
    async def _monitor_existing_files(self):
        """Check for existing files in the directory on startup."""
        watch_dir = Path(self.config['watch_directory'])
        
        if not watch_dir.exists():
            return
        
        for file_path in watch_dir.glob('event_*.json'):
            if file_path.name not in self.processed_files:
                await self._queue_file_for_processing(file_path)
        
        self.logger.info(f"Queued {len(list(watch_dir.glob('event_*.json')))} existing files for processing")
    
    async def _queue_file_for_processing(self, file_path: Path):
        """Queue a file for processing."""
        if file_path.name in self.processed_files:
            return
        
        # Wait a moment for file to be fully written
        await asyncio.sleep(0.1)
        
        try:
            await self.event_queue.put(file_path)
            self.logger.debug(f"Queued file for processing: {file_path.name}")
        except Exception as e:
            self.logger.error(f"Failed to queue file {file_path.name}: {e}")
    
    async def _process_event_queue(self):
        """Process events from the queue."""
        while self.running:
            try:
                # Wait for events with timeout
                file_path = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                await self._process_event_file(file_path)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event queue: {e}")
                await asyncio.sleep(1)
    
    async def _process_event_file(self, file_path: Path):
        """Process a single event file."""
        if file_path.name in self.processed_files:
            return
        
        try:
            self.logger.debug(f"Processing event file: {file_path.name}")
            
            # Rate limiting check
            if not self._check_rate_limit():
                self.logger.warning("Rate limit exceeded, delaying event processing")
                await asyncio.sleep(1)
                await self.event_queue.put(file_path)  # Re-queue
                return
            
            # Read and parse file
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            event_data = json.loads(content)
            
            # Validate and convert to API format
            api_event = await self._convert_to_api_event(event_data)
            
            if api_event:
                # Send to API
                success = await self._send_event_to_api(api_event, file_path.name)
                
                if success:
                    self.stats['events_processed'] += 1
                    self.stats['last_event_time'] = datetime.now(timezone.utc)
                    
                    # Mark as processed and clean up
                    self.processed_files.add(file_path.name)
                    await self._cleanup_file(file_path)
                else:
                    self.stats['events_failed'] += 1
            
            self.stats['files_processed'] += 1
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in file {file_path.name}: {e}")
            await self._cleanup_file(file_path)  # Remove invalid files
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path.name}: {e}")
            self.stats['events_failed'] += 1
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()
        
        # Reset counter if a minute has passed
        if current_time - self.minute_start >= 60:
            self.events_this_minute = 0
            self.minute_start = current_time
        
        max_events = self.config.get('max_events_per_minute', 30)
        if self.events_this_minute >= max_events:
            return False
        
        self.events_this_minute += 1
        return True
    
    async def _convert_to_api_event(self, event_data: Dict) -> Optional[dict]:
        """Convert Lua event data to API event format."""
        try:
            event_type = event_data.get('type')
            
            # Get run and player IDs from config
            run_id = self.config['run_id']
            player_id = self.config['player_id']
            
            # Convert timestamp
            timestamp = event_data.get('timestamp')
            if timestamp:
                # Ensure ISO format
                if 'T' not in timestamp:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now(timezone.utc)
            
            if event_type == 'encounter':
                return {
                    'type': 'encounter',
                    'run_id': run_id,
                    'player_id': player_id,
                    'route_id': event_data['route_id'],
                    'species_id': event_data['species_id'],
                    'level': event_data['level'],
                    'shiny': event_data.get('shiny', False),
                    'method': event_data.get('method', 'grass'),
                    'rod_kind': event_data.get('rod_kind'),
                    'time': timestamp.isoformat()
                }
            
            elif event_type == 'catch_result':
                return {
                    'type': 'catch_result',
                    'run_id': run_id,
                    'player_id': player_id,
                    'encounter_id': event_data.get('encounter_id'),  # May need to be resolved
                    'result': event_data['result'],
                    'time': timestamp.isoformat()
                }
            
            elif event_type == 'faint':
                return {
                    'type': 'faint',
                    'run_id': run_id,
                    'player_id': player_id,
                    'pokemon_key': event_data['pokemon_key'],
                    'party_index': event_data.get('party_index', 0),
                    'time': timestamp.isoformat()
                }
            
            else:
                self.logger.warning(f"Unknown event type: {event_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error converting event data: {e}")
            return None
    
    async def _send_event_to_api(self, event_data: Dict, file_name: str) -> bool:
        """Send event to the API server."""
        url = f"{self.config['api_base_url']}/v1/events"
        
        # Generate idempotency key from filename
        idempotency_key = f"watcher_{self.config['player_name']}_{file_name}"
        
        headers = {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotency_key
        }
        
        max_retries = self.config.get('retry_attempts', 3)
        retry_delay = self.config.get('retry_delay', 1000) / 1000  # Convert to seconds
        
        for attempt in range(max_retries):
            try:
                async with self.session.post(url, json=event_data, headers=headers) as response:
                    if response.status in (200, 201, 202):
                        self.logger.debug(f"Event sent successfully: {event_data['type']}")
                        return True
                    elif response.status == 401:
                        self.logger.error("Authentication failed - check player token")
                        return False
                    elif response.status == 422:
                        error_text = await response.text()
                        self.logger.error(f"Validation error: {error_text}")
                        return False  # Don't retry validation errors
                    else:
                        error_text = await response.text()
                        self.logger.warning(f"API error {response.status}: {error_text}")
                        
            except Exception as e:
                self.logger.warning(f"API request failed (attempt {attempt + 1}): {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
        
        self.stats['api_errors'] += 1
        self.logger.error(f"Failed to send event after {max_retries} attempts")
        return False
    
    async def _cleanup_file(self, file_path: Path):
        """Clean up processed event file."""
        try:
            if self.config.get('delete_processed_files', True):
                file_path.unlink()
                self.logger.debug(f"Deleted processed file: {file_path.name}")
            else:
                # Move to processed directory
                processed_dir = Path(self.config['watch_directory']) / 'processed'
                processed_dir.mkdir(exist_ok=True)
                
                new_path = processed_dir / file_path.name
                file_path.rename(new_path)
                self.logger.debug(f"Moved processed file to: {new_path}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up file {file_path.name}: {e}")
    
    async def _periodic_health_check(self):
        """Periodic health check and statistics reporting."""
        while self.running:
            await asyncio.sleep(60)  # Every minute
            
            self.logger.info(
                f"Health: {self.stats['events_processed']} events processed, "
                f"{self.stats['events_failed']} failed, "
                f"{self.stats['api_errors']} API errors"
            )
            
            # Test API connection periodically
            try:
                await self._test_api_connection()
            except Exception:
                self.logger.warning("Periodic API health check failed")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python event_watcher.py <config_file>")
        sys.exit(1)
    
    config_file = Path(sys.argv[1])
    
    if not config_file.exists():
        print(f"Configuration file not found: {config_file}")
        sys.exit(1)
    
    # Load configuration
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Validate required configuration
    required_fields = ['player_name', 'player_token', 'api_base_url', 'watch_directory', 'run_id', 'player_id']
    missing_fields = [field for field in required_fields if field not in config]
    
    if missing_fields:
        print(f"Missing required configuration fields: {missing_fields}")
        sys.exit(1)
    
    # Start the watcher
    watcher = EventWatcher(config)
    await watcher.start()


if __name__ == "__main__":
    asyncio.run(main())