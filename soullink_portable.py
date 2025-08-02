#!/usr/bin/env python3
"""
SoulLink Tracker Portable Edition - Main Entry Point

This is the entry point for the portable version of SoulLink Tracker.
When compiled with PyInstaller/Nuitka, this creates a standalone executable.

Usage:
    python soullink_portable.py        # Run in development
    soullink-tracker.exe               # Run as compiled executable
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path for imports
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Import and run the launcher
from soullink_tracker.launcher import main

if __name__ == "__main__":
    # Set up basic environment before launching
    os.environ.setdefault('PYTHONUNBUFFERED', '1')
    
    # Run the portable launcher
    exit_code = main()
    sys.exit(exit_code)