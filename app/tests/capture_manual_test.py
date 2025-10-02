#!/usr/bin/env python3
"""
Automated capture tooling for manual ROM testing (T016a).

This script monitors the data/encounters/ directory for new JSON files created
by the DeSmuME Lua script during manual testing. It validates each file against
the encounter schema and captures performance metrics.

Usage:
    python tests/capture_manual_test.py --start
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import jsonschema
from pydantic import ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class TestCaptureHandler(FileSystemEventHandler):
    """
    Monitors data/encounters/ directory for new JSON files and validates them.

    Captures performance metrics including:
    - Latency: Battle screen appearance → JSON file creation
    - File creation timestamps
    - Validation pass/fail tracking
    """

    def __init__(self, schema_path: Path, debug_log_path: Path):
        """
        Initialize the capture handler.

        Args:
            schema_path: Path to encounter JSON schema
            debug_log_path: Path to save debug report
        """
        super().__init__()
        self.schema_path = schema_path
        self.debug_log_path = debug_log_path
        self.session_start = datetime.now(timezone.utc)
        self.events: List[Dict] = []
        self.total_encounters = 0
        self.valid_encounters = 0
        self.failed_validations = 0

        # Load JSON schema
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)

    def on_created(self, event):
        """
        Handle file creation events.

        Args:
            event: FileSystemEvent from watchdog
        """
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        # Only process JSON files
        if filepath.suffix != '.json':
            return

        # Track event timing
        event_timestamp = datetime.now(timezone.utc)

        # Wait briefly to ensure file is fully written
        time.sleep(0.1)

        # Read and validate the JSON file
        try:
            with open(filepath, 'r') as f:
                encounter_data = json.load(f)

            # Validate against schema
            jsonschema.validate(instance=encounter_data, schema=self.schema)

            # Extract key data
            species_id = encounter_data.get('species_id')
            level = encounter_data.get('level')

            # Record successful validation
            self.total_encounters += 1
            self.valid_encounters += 1

            event_record = {
                "timestamp": event_timestamp.isoformat(),
                "filepath": filepath.name,
                "validation_status": "valid",
                "latency_seconds": self._calculate_latency(filepath),
                "species_id": species_id,
                "level": level
            }

            self.events.append(event_record)
            print(f"✓ Valid encounter: {filepath.name} (Species: {species_id}, Level: {level})")

        except jsonschema.ValidationError as e:
            self.total_encounters += 1
            self.failed_validations += 1

            event_record = {
                "timestamp": event_timestamp.isoformat(),
                "filepath": filepath.name,
                "validation_status": "invalid",
                "error": str(e.message),
                "latency_seconds": self._calculate_latency(filepath)
            }

            self.events.append(event_record)
            print(f"✗ Invalid encounter: {filepath.name} - {e.message}")

        except json.JSONDecodeError as e:
            self.total_encounters += 1
            self.failed_validations += 1

            event_record = {
                "timestamp": event_timestamp.isoformat(),
                "filepath": filepath.name,
                "validation_status": "invalid_json",
                "error": f"JSON decode error: {str(e)}",
                "latency_seconds": None
            }

            self.events.append(event_record)
            print(f"✗ Invalid JSON: {filepath.name} - {str(e)}")

    def _calculate_latency(self, filepath: Path) -> Optional[float]:
        """
        Calculate latency from filename timestamp to file creation.

        Assumes filename format: encounter_YYYYMMDD_HHMMSS_PlayerName.json

        Args:
            filepath: Path to the encounter JSON file

        Returns:
            Latency in seconds, or None if timestamp cannot be parsed
        """
        try:
            # Extract timestamp from filename
            # Format: encounter_20251001_143215_TestPlayer.json
            parts = filepath.stem.split('_')
            if len(parts) < 3:
                return None

            date_str = parts[1]  # YYYYMMDD
            time_str = parts[2]  # HHMMSS

            # Parse timestamp
            timestamp_str = f"{date_str}_{time_str}"
            file_timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            file_timestamp = file_timestamp.replace(tzinfo=timezone.utc)

            # Get file creation time
            creation_time = datetime.fromtimestamp(filepath.stat().st_ctime, tz=timezone.utc)

            # Calculate latency
            latency = (creation_time - file_timestamp).total_seconds()

            return round(latency, 2)

        except (ValueError, IndexError, OSError):
            return None

    def generate_report(self) -> Dict:
        """
        Generate AI-friendly debug report.

        Returns:
            Report dictionary with session summary and event details
        """
        session_end = datetime.now(timezone.utc)
        duration = (session_end - self.session_start).total_seconds()

        # Calculate average and max latency
        latencies = [e['latency_seconds'] for e in self.events if e.get('latency_seconds') is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
        max_latency = round(max(latencies), 2) if latencies else 0

        report = {
            "test_session": {
                "start_time": self.session_start.isoformat(),
                "end_time": session_end.isoformat(),
                "duration_seconds": round(duration, 2)
            },
            "summary": {
                "total_encounters": self.total_encounters,
                "valid_encounters": self.valid_encounters,
                "failed_validations": self.failed_validations,
                "avg_latency_seconds": avg_latency,
                "max_latency_seconds": max_latency
            },
            "events": self.events
        }

        return report

    def save_report(self):
        """Save debug report to disk."""
        report = self.generate_report()

        # Ensure debug_logs directory exists
        self.debug_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Write report
        with open(self.debug_log_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📊 Debug report saved to: {self.debug_log_path}")

        # Print summary
        print("\n=== Test Session Summary ===")
        print(f"Duration: {report['test_session']['duration_seconds']:.2f} seconds")
        print(f"Total Encounters: {report['summary']['total_encounters']}")
        print(f"Valid: {report['summary']['valid_encounters']}")
        print(f"Failed: {report['summary']['failed_validations']}")
        print(f"Avg Latency: {report['summary']['avg_latency_seconds']:.2f}s")
        print(f"Max Latency: {report['summary']['max_latency_seconds']:.2f}s")


def start_monitoring(encounters_dir: Path, schema_path: Path, debug_log_path: Path):
    """
    Start file system monitoring for manual testing.

    Args:
        encounters_dir: Directory to monitor for JSON files
        schema_path: Path to encounter JSON schema
        debug_log_path: Path to save debug report
    """
    # Ensure encounters directory exists
    encounters_dir.mkdir(parents=True, exist_ok=True)

    # Create event handler
    event_handler = TestCaptureHandler(schema_path, debug_log_path)

    # Create observer
    observer = Observer()
    observer.schedule(event_handler, str(encounters_dir), recursive=False)
    observer.start()

    print(f"🔍 Monitoring: {encounters_dir}")
    print(f"📋 Schema: {schema_path}")
    print(f"📊 Debug log: {debug_log_path}")
    print("\nPress Ctrl+C to stop monitoring and generate report...\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n\n⏹ Stopping monitor...")

    observer.join()

    # Generate and save final report
    event_handler.save_report()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Automated capture tooling for manual ROM testing (T016a)"
    )
    parser.add_argument(
        '--start',
        action='store_true',
        help='Start monitoring data/encounters/ directory'
    )
    parser.add_argument(
        '--encounters-dir',
        type=Path,
        default=Path('data/encounters'),
        help='Directory to monitor (default: data/encounters)'
    )
    parser.add_argument(
        '--schema',
        type=Path,
        default=Path('specs/001-anything-we-still/contracts/encounter_json_schema.json'),
        help='Path to encounter JSON schema'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('tests/debug_logs/capture_report.json'),
        help='Path to save debug report (default: tests/debug_logs/capture_report.json)'
    )

    args = parser.parse_args()

    if args.start:
        start_monitoring(args.encounters_dir, args.schema, args.output)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
