#!/usr/bin/env python3
"""
Simplified PyInstaller Build Script for GitHub Actions
This is a minimal, robust version that focuses on getting the build working.
"""

import sys
import os
import subprocess
import platform
from pathlib import Path
import shutil

def main():
    """Simple build script that should work in GitHub Actions."""
    
    print("🔗 SoulLink Tracker Portable - Simple Build")
    print("=" * 50)
    
    # Basic info
    project_root = Path.cwd()
    entry_point = project_root / "soullink_portable.py"
    
    print(f"Project root: {project_root}")
    print(f"Entry point: {entry_point}")
    print(f"Platform: {platform.system()}")
    
    # Check entry point exists
    if not entry_point.exists():
        print(f"❌ Entry point not found: {entry_point}")
        return 1
    
    # Clean dist directory
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        print("🧹 Cleaned dist directory")
    
    # Determine executable name
    exe_name = "soullink-tracker"
    if platform.system() == "Windows":
        exe_name += ".exe"
    elif platform.system() == "Darwin":
        exe_name = "SoulLink Tracker"
    
    print(f"Target executable: {exe_name}")
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", exe_name.replace(".exe", ""),  # Remove .exe for PyInstaller
        "--add-data", "web:web",
        "--add-data", "client:client", 
        "--add-data", "data:data",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--noconfirm",
        str(entry_point)
    ]
    
    # Platform specific options
    if platform.system() == "Windows":
        cmd.extend(["--windowed"])
    elif platform.system() == "Darwin":
        cmd.extend(["--windowed"])
    
    print(f"Build command: {' '.join(cmd)}")
    print()
    
    # Run PyInstaller
    print("🚀 Running PyInstaller...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ PyInstaller completed successfully")
        if result.stdout:
            print("Output:", result.stdout[-500:])  # Last 500 chars
            
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller failed: {e}")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print("Stdout:", e.stdout[-1000:])
        if e.stderr:
            print("Stderr:", e.stderr[-1000:])
        return 1
    
    # Check if executable was created
    expected_exe = dist_dir / (exe_name if platform.system() != "Darwin" else f"{exe_name}.app")
    
    if expected_exe.exists():
        size_mb = get_size_mb(expected_exe)
        print(f"✅ Executable created: {expected_exe}")
        print(f"📦 Size: {size_mb} MB")
        return 0
    else:
        print(f"❌ Executable not found: {expected_exe}")
        print("Files in dist/:")
        if dist_dir.exists():
            for f in dist_dir.iterdir():
                print(f"  - {f}")
        return 1

def get_size_mb(path):
    """Get size in MB."""
    if path.is_file():
        return round(path.stat().st_size / (1024 * 1024), 1)
    elif path.is_dir():
        total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return round(total / (1024 * 1024), 1)
    return 0

if __name__ == "__main__":
    sys.exit(main())