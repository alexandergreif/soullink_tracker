"""Persistent spool queue implementation for reliable event delivery."""

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4


@dataclass
class SpoolRecord:
    """Represents a single spooled event record."""
    
    record_id: str
    created_at: str  # ISO 8601 UTC
    next_attempt_at: str  # ISO 8601 UTC
    attempt: int
    idempotency_key: str
    base_url: str
    endpoint_path: str = "/v1/events"
    method: str = "POST"
    headers: Dict[str, str] = None
    request_json: Dict[str, Any] = None
    request_sha256: str = ""
    run_id: str = ""
    player_id: str = ""
    last_error: Optional[str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.request_json is None:
            self.request_json = {}
        
        # Compute SHA256 hash of sorted request JSON if not provided
        if not self.request_sha256 and self.request_json:
            json_str = json.dumps(self.request_json, sort_keys=True, separators=(',', ':'))
            self.request_sha256 = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpoolRecord':
        """Create SpoolRecord from dictionary (loaded from JSON)."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SpoolRecord to dictionary (for JSON serialization)."""
        return asdict(self)


class SpoolQueue:
    """File-based persistent spool queue for events."""
    
    def __init__(self, root: Path, run_id: str, player_id: str):
        """
        Initialize spool queue for a specific run and player.
        
        Args:
            root: Root spool directory
            run_id: UUID of the run
            player_id: UUID of the player
        """
        self.root = Path(root)
        self.run_id = run_id
        self.player_id = player_id
        self.player_dir = self.root / run_id / player_id
        self.dead_dir = self.player_dir / "dead"
        
        # Ensure directories exist
        self.player_dir.mkdir(parents=True, exist_ok=True)
        self.dead_dir.mkdir(exist_ok=True)
        
        # Optional simple lock file to discourage multiple processes
        self.lock_file = self.player_dir / "watcher.lock"
    
    def enqueue(
        self, 
        payload: Dict[str, Any], 
        idempotency_key: str, 
        headers: Dict[str, str],
        base_url: str
    ) -> Path:
        """
        Add an event to the spool queue.
        
        Args:
            payload: Event payload (request body)
            idempotency_key: Unique idempotency key for this event
            headers: HTTP headers to include
            base_url: Base URL for the API
        
        Returns:
            Path to the created spool file
        """
        now = datetime.now(timezone.utc)
        record_id = str(uuid4())
        
        record = SpoolRecord(
            record_id=record_id,
            created_at=now.isoformat(),
            next_attempt_at=now.isoformat(),  # Available immediately
            attempt=0,
            idempotency_key=idempotency_key,
            base_url=base_url,
            headers=headers.copy(),
            request_json=payload.copy(),
            run_id=self.run_id,
            player_id=self.player_id
        )
        
        # Generate filename with timestamp and record ID
        timestamp = now.isoformat().replace(':', '-').replace('.', '-')
        filename = f"{timestamp}_{record_id}.json"
        file_path = self.player_dir / filename
        
        # Atomic write: write to temp file then rename
        temp_path = file_path.with_suffix('.json.tmp')
        try:
            with temp_path.open('w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
            
            temp_path.rename(file_path)
            return file_path
            
        except Exception:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
    
    def list_due(self, now: datetime) -> List[Path]:
        """
        Get list of spool files that are due for processing.
        
        Args:
            now: Current datetime
        
        Returns:
            List of file paths sorted by next_attempt_at then created_at
        """
        due_files = []
        
        # Find all .json files in the player directory
        for file_path in self.player_dir.glob("*.json"):
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    record_data = json.load(f)
                
                record = SpoolRecord.from_dict(record_data)
                next_attempt = datetime.fromisoformat(record.next_attempt_at.replace('Z', '+00:00'))
                
                if next_attempt <= now:
                    due_files.append((next_attempt, record.created_at, file_path))
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Invalid record file - move to dead letter
                self._move_to_dead_unsafe(file_path, f"Invalid record format: {e}")
                continue
        
        # Sort by next_attempt_at, then created_at
        due_files.sort(key=lambda x: (x[0], x[1]))
        return [path for _, _, path in due_files]
    
    def claim(self, path: Path) -> Path:
        """
        Claim a spool file for processing by renaming to .sending.
        
        Args:
            path: Path to the spool file
        
        Returns:
            Path to the claimed (.sending) file
        
        Raises:
            FileNotFoundError: If the file doesn't exist or was already claimed
        """
        sending_path = path.with_suffix('.sending')
        
        try:
            path.rename(sending_path)
            return sending_path
        except FileNotFoundError:
            raise FileNotFoundError(f"Spool file not found or already claimed: {path}")
    
    def release_for_retry(
        self, 
        sending_path: Path, 
        next_attempt_at: datetime, 
        last_error: str
    ) -> Path:
        """
        Release a claimed file back to the queue with updated retry information.
        
        Args:
            sending_path: Path to the .sending file
            next_attempt_at: When to retry next
            last_error: Error message from the failed attempt
        
        Returns:
            Path to the released (.json) file
        """
        # Load the record
        try:
            with sending_path.open('r', encoding='utf-8') as f:
                record_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"Cannot load sending file {sending_path}: {e}")
        
        # Update retry information
        record = SpoolRecord.from_dict(record_data)
        record.attempt += 1
        record.next_attempt_at = next_attempt_at.isoformat()
        record.last_error = last_error
        
        # Write back to a .json file atomically
        json_path = sending_path.with_suffix('.json')
        temp_path = json_path.with_suffix('.json.tmp')
        
        try:
            with temp_path.open('w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
            
            temp_path.rename(json_path)
            
            # Remove the .sending file
            sending_path.unlink(missing_ok=True)
            
            return json_path
            
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
    
    def delete(self, sending_path: Path) -> None:
        """
        Delete a successfully processed file.
        
        Args:
            sending_path: Path to the .sending file to delete
        """
        sending_path.unlink(missing_ok=True)
    
    def move_to_dead(self, sending_path: Path, reason: str) -> Path:
        """
        Move a non-retryable failed file to the dead letter directory.
        
        Args:
            sending_path: Path to the .sending file
            reason: Reason for moving to dead letter
        
        Returns:
            Path in the dead letter directory
        """
        try:
            # Load the record and add the reason
            with sending_path.open('r', encoding='utf-8') as f:
                record_data = json.load(f)
            
            record = SpoolRecord.from_dict(record_data)
            record.last_error = reason
            
            # Generate dead letter filename
            dead_filename = f"dead_{int(time.time())}_{sending_path.stem}.json"
            dead_path = self.dead_dir / dead_filename
            
            # Write to dead letter directory
            with dead_path.open('w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Remove the sending file
            sending_path.unlink(missing_ok=True)
            
            return dead_path
            
        except Exception as e:
            # Fallback: just move the file as-is
            return self._move_to_dead_unsafe(sending_path, f"Failed to process: {reason}; Move error: {e}")
    
    def _move_to_dead_unsafe(self, file_path: Path, reason: str) -> Path:
        """Fallback method to move problematic files to dead letter."""
        dead_filename = f"dead_{int(time.time())}_{file_path.name}"
        dead_path = self.dead_dir / dead_filename
        
        try:
            file_path.rename(dead_path)
        except Exception:
            # Last resort: copy and delete
            try:
                import shutil
                shutil.copy2(file_path, dead_path)
                file_path.unlink(missing_ok=True)
            except Exception:
                pass  # Give up
        
        return dead_path
    
    def recover_stale(self, max_age_secs: int = 300) -> int:
        """
        Recover stale .sending files (from crashed processes) back to .json.
        
        Args:
            max_age_secs: Files older than this are considered stale
        
        Returns:
            Number of files recovered
        """
        now = time.time()
        recovered = 0
        
        for sending_file in self.player_dir.glob("*.sending"):
            try:
                # Check file age
                file_age = now - sending_file.stat().st_mtime
                if file_age > max_age_secs:
                    # Recover by renaming back to .json
                    json_file = sending_file.with_suffix('.json')
                    sending_file.rename(json_file)
                    recovered += 1
                    
            except Exception:
                # Move problematic files to dead letter
                self._move_to_dead_unsafe(sending_file, "Stale sending file recovery failed")
        
        return recovered
    
    def acquire_lock(self) -> bool:
        """
        Attempt to acquire a simple PID lock file.
        
        Returns:
            True if lock acquired, False otherwise
        """
        try:
            if self.lock_file.exists():
                # Check if the PID in the lock file is still running
                try:
                    with self.lock_file.open('r') as f:
                        old_pid = int(f.read().strip())
                    
                    # Try to check if process is still running (POSIX only)
                    if os.name == 'posix':
                        try:
                            os.kill(old_pid, 0)  # Signal 0 just checks if PID exists
                            return False  # Process still running
                        except ProcessLookupError:
                            pass  # Process not running, we can take the lock
                    else:
                        # On Windows, assume lock is stale after 5 minutes
                        lock_age = time.time() - self.lock_file.stat().st_mtime
                        if lock_age < 300:  # 5 minutes
                            return False
                            
                except (ValueError, OSError):
                    pass  # Invalid lock file, remove it
                
                # Remove stale lock file
                self.lock_file.unlink(missing_ok=True)
            
            # Create new lock file with our PID
            with self.lock_file.open('w') as f:
                f.write(str(os.getpid()))
            
            return True
            
        except Exception:
            return False  # Failed to acquire lock
    
    def release_lock(self) -> None:
        """Release the PID lock file."""
        self.lock_file.unlink(missing_ok=True)