"""Command-line interface for the SoulLink Production Watcher."""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from .config import WatcherConfig, default_spool_dir


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="soullink-watcher",
        description="SoulLink Production Watcher - reliable event submission with spool queue"
    )
    
    # Required arguments
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of the SoulLink API server (e.g., http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--run-id", 
        required=True,
        help="UUID of the SoulLink run"
    )
    parser.add_argument(
        "--player-id",
        required=True, 
        help="UUID of the player"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Bearer token for API authentication"
    )
    
    # Optional arguments
    parser.add_argument(
        "--from-file",
        type=Path,
        help="Path to NDJSON file containing events to ingest"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode (verbose logging, dev-friendly defaults)"
    )
    parser.add_argument(
        "--spool-dir",
        type=Path,
        help="Override default spool directory path"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between spool queue scans (default: 1.0)"
    )
    parser.add_argument(
        "--backoff-base",
        type=float,
        default=1.0,
        help="Base seconds for exponential backoff (default: 1.0)"
    )
    parser.add_argument(
        "--backoff-max",
        type=float,
        default=300.0,
        help="Maximum seconds for backoff delay (default: 300.0)"
    )
    parser.add_argument(
        "--backoff-jitter",
        type=float,
        default=0.2,
        help="Jitter ratio for backoff randomization (default: 0.2)"
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=10.0,
        help="HTTP request timeout in seconds (default: 10.0)"
    )
    
    return parser.parse_args(argv)


def build_config(ns: argparse.Namespace) -> WatcherConfig:
    """Build WatcherConfig from parsed arguments with environment variable fallbacks."""
    # Get values from args or environment variables
    base_url = ns.base_url or os.getenv("SOULLINK_WATCHER_BASE_URL")
    run_id = ns.run_id or os.getenv("SOULLINK_WATCHER_RUN_ID")
    player_id = ns.player_id or os.getenv("SOULLINK_WATCHER_PLAYER_ID")
    token = ns.token or os.getenv("SOULLINK_WATCHER_TOKEN")
    
    # Validate required fields
    if not base_url:
        raise ValueError("--base-url is required or set SOULLINK_WATCHER_BASE_URL")
    if not run_id:
        raise ValueError("--run-id is required or set SOULLINK_WATCHER_RUN_ID") 
    if not player_id:
        raise ValueError("--player-id is required or set SOULLINK_WATCHER_PLAYER_ID")
    if not token:
        raise ValueError("--token is required or set SOULLINK_WATCHER_TOKEN")
    
    # Validate UUID formats
    try:
        UUID(run_id)
    except ValueError:
        raise ValueError(f"Invalid run-id format: {run_id} (must be UUID)")
    
    try:
        UUID(player_id)
    except ValueError:
        raise ValueError(f"Invalid player-id format: {player_id} (must be UUID)")
    
    # Determine spool directory
    if ns.spool_dir:
        spool_dir = ns.spool_dir
    elif os.getenv("SOULLINK_WATCHER_SPOOL_DIR"):
        spool_dir = Path(os.getenv("SOULLINK_WATCHER_SPOOL_DIR"))
    else:
        spool_dir = default_spool_dir(ns.dev)
    
    # Validate from-file if provided
    from_file = None
    if ns.from_file:
        from_file = Path(ns.from_file)
        if not from_file.exists():
            raise ValueError(f"File not found: {from_file}")
        if not from_file.is_file():
            raise ValueError(f"Not a regular file: {from_file}")
    
    # Normalize base URL (remove trailing slash)
    base_url = base_url.rstrip("/")
    
    return WatcherConfig(
        base_url=base_url,
        run_id=run_id,
        player_id=player_id,
        token=token,
        spool_dir=spool_dir,
        dev=ns.dev,
        from_file=from_file,
        poll_interval_secs=ns.poll_interval,
        backoff_base_secs=ns.backoff_base,
        backoff_max_secs=ns.backoff_max,
        backoff_jitter_ratio=ns.backoff_jitter,
        http_timeout_secs=ns.http_timeout
    )