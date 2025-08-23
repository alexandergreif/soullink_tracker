#!/usr/bin/env python3
"""
Simple script to view and analyze SoulLink Tracker logs.

Usage:
    python scripts/view_logs.py                  # View latest session logs
    python scripts/view_logs.py --component api  # View specific component logs
    python scripts/view_logs.py --errors         # View only error logs
    python scripts/view_logs.py --tail 50        # View last 50 lines
"""

import argparse
import os
from pathlib import Path
from datetime import datetime


def get_latest_session(log_dir: Path) -> Path:
    """Get the most recent log session directory."""
    sessions = [d for d in log_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("No log sessions found")
        return None
    return max(sessions, key=lambda x: x.stat().st_mtime)


def view_logs(component: str = None, errors_only: bool = False, tail: int = None):
    """View log files with filtering options."""
    log_dir = Path("logs")
    
    if not log_dir.exists():
        print("No logs directory found. Run the application first to generate logs.")
        return
    
    # Get latest session
    session_dir = get_latest_session(log_dir)
    if not session_dir:
        return
    
    print(f"Viewing logs from session: {session_dir.name}")
    print("=" * 80)
    
    # Read session info
    session_info = session_dir / "session_info.txt"
    if session_info.exists():
        print(session_info.read_text())
        print("=" * 80)
    
    # Determine which log file to read
    if errors_only:
        log_file = session_dir / "errors.log"
        print(f"Viewing: errors.log")
    elif component:
        log_file = session_dir / f"{component}.log"
        print(f"Viewing: {component}.log")
    else:
        log_file = session_dir / "unified.log"
        print(f"Viewing: unified.log (all components)")
    
    print("-" * 80)
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return
    
    # Read and display log content
    with open(log_file, 'r') as f:
        lines = f.readlines()
        
        if tail and len(lines) > tail:
            lines = lines[-tail:]
            print(f"(Showing last {tail} lines)")
            print("-" * 80)
        
        for line in lines:
            # Highlight errors and warnings
            if "ERROR" in line:
                print(f"\033[91m{line}\033[0m", end='')  # Red
            elif "WARNING" in line:
                print(f"\033[93m{line}\033[0m", end='')  # Yellow
            elif "INFO" in line:
                print(f"\033[92m{line}\033[0m", end='')  # Green
            else:
                print(line, end='')
    
    print("\n" + "=" * 80)
    print(f"Log location: {log_file.absolute()}")


def list_sessions():
    """List all available log sessions."""
    log_dir = Path("logs")
    
    if not log_dir.exists():
        print("No logs directory found.")
        return
    
    sessions = sorted([d for d in log_dir.iterdir() if d.is_dir()])
    
    print("Available log sessions:")
    print("-" * 80)
    
    for session in sessions:
        # Get session size
        total_size = sum(f.stat().st_size for f in session.rglob('*') if f.is_file())
        size_mb = total_size / 1024 / 1024
        
        # Parse session timestamp
        try:
            timestamp = datetime.strptime(session.name, "%Y%m%d_%H%M%S")
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_time = session.name
        
        print(f"  {session.name} - {formatted_time} - {size_mb:.2f} MB")
    
    print("-" * 80)
    print(f"Total sessions: {len(sessions)}")


def main():
    parser = argparse.ArgumentParser(description="View SoulLink Tracker logs")
    parser.add_argument("--component", "-c", help="View specific component logs (api, database, events, auth, etc.)")
    parser.add_argument("--errors", "-e", action="store_true", help="View only error logs")
    parser.add_argument("--tail", "-t", type=int, help="Show only last N lines")
    parser.add_argument("--list", "-l", action="store_true", help="List all log sessions")
    
    args = parser.parse_args()
    
    if args.list:
        list_sessions()
    else:
        view_logs(component=args.component, errors_only=args.errors, tail=args.tail)


if __name__ == "__main__":
    main()