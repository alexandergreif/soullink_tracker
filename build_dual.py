#!/usr/bin/env python3
"""
Dual PyInstaller Build Script for SoulLink Tracker
Builds both admin and user portable executables.
"""

import sys
import os
import subprocess
import platform
from pathlib import Path
import shutil


def test_watcher_imports():
    """Test that watcher modules can be imported."""
    print("Testing watcher module imports...")
    
    # Add watcher src to path for testing
    watcher_src_dir = Path.cwd() / "watcher" / "src"
    if str(watcher_src_dir) not in sys.path:
        sys.path.insert(0, str(watcher_src_dir))
    
    watcher_modules = [
        "soullink_watcher",
        "soullink_watcher.main",
        "soullink_watcher.config",
        "soullink_watcher.cli",
        "soullink_watcher.http_client",
        "soullink_watcher.ndjson_reader",
        "soullink_watcher.spool",
        "soullink_watcher.retry"
    ]
    
    failed_imports = []
    for module in watcher_modules:
        try:
            __import__(module)
            print(f"  OK {module}")
        except ImportError as e:
            print(f"  ERROR {module}: {e}")
            failed_imports.append((module, str(e)))
        except Exception as e:
            print(f"  WARNING {module}: {e}")
            
    if failed_imports:
        print(f"\nWARNING: {len(failed_imports)} watcher modules failed to import")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return False
    
    print("All watcher imports successful!")
    return True


def build_target(entry_point_path, base_name, is_debug, include_web, include_data, include_client, extra_paths, extra_hidden, collect_submodules):
    """Build a single target with PyInstaller."""
    
    # Set up directories
    dist_dir = Path("dist")
    
    # Determine executable name based on platform and debug mode
    if platform.system() == "Windows":
        exe_name = f"{base_name}{'-debug' if is_debug else ''}.exe"
    elif platform.system() == "Darwin":
        exe_name = f"{base_name.title().replace('-', ' ')}{' Debug' if is_debug else ''}"
    else:
        exe_name = f"{base_name}{'-debug' if is_debug else ''}"
    
    print(f"Building target: {exe_name}")
    print(f"Entry point: {entry_point_path}")
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", base_name + ("-debug" if is_debug else ""),
        "--noconfirm"
    ]
    
    # Add paths
    for path in extra_paths:
        cmd.extend(["--paths", path])
    
    # Add data directories
    if include_web:
        cmd.extend(["--add-data", "web:web"])
    if include_data:
        cmd.extend(["--add-data", "data:data"])
    if include_client:
        cmd.extend(["--add-data", "client:client"])
    
    # Add hidden imports
    for hidden in extra_hidden:
        cmd.extend(["--hidden-import", hidden])
    
    # Add collect submodules
    for submod in collect_submodules:
        cmd.extend(["--collect-submodules", submod])
    
    # Platform specific options
    if not is_debug:
        if platform.system() in ["Windows", "Darwin"]:
            cmd.append("--windowed")
    
    # Add entry point
    cmd.append(str(entry_point_path))
    
    print(f"Running PyInstaller for {base_name}...")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"PyInstaller completed successfully for {base_name}")
        
        # Check if executable was created
        if platform.system() == "Darwin":
            expected_exe = dist_dir / f"{exe_name}.app"
        else:
            expected_exe = dist_dir / exe_name
        
        if expected_exe.exists():
            size_mb = get_size_mb(expected_exe)
            print(f"Executable created: {expected_exe}")
            print(f"Size: {size_mb} MB")
            return expected_exe
        else:
            print(f"ERROR: Executable not found: {expected_exe}")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"ERROR: PyInstaller failed for {base_name}: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr[-500:]}")
        return None


def get_size_mb(path):
    """Get size in MB."""
    if path.is_file():
        return round(path.stat().st_size / (1024 * 1024), 1)
    elif path.is_dir():
        total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return round(total / (1024 * 1024), 1)
    return 0


def main():
    """Main build function."""
    # Parse arguments
    debug_mode = '--debug' in sys.argv
    admin_only = '--admin-only' in sys.argv
    user_only = '--user-only' in sys.argv
    
    print("SoulLink Tracker - Dual PyInstaller Build Script")
    print(f"Debug mode: {debug_mode}")
    print(f"Admin only: {admin_only}")
    print(f"User only: {user_only}")
    
    # Verify we're in the right directory
    admin_entry = Path("soullink_portable.py")
    user_entry = Path("soullink_user_portable.py")
    
    if not admin_entry.exists():
        print(f"ERROR: Admin entry point not found: {admin_entry}")
        return 1
    
    if not user_entry.exists() and not admin_only:
        print(f"ERROR: User entry point not found: {user_entry}")
        return 1
    
    # Setup directories
    dist_dir = Path("dist")
    build_dir = Path("build")
    
    # Clean up previous builds
    if dist_dir.exists():
        print("Cleaning up previous build...")
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    built_executables = []
    
    # Test watcher imports if building user
    if not admin_only:
        if not test_watcher_imports():
            print("\\nWARNING: Some watcher imports failed - user build may have runtime issues")
            print("Continuing anyway...")
    
    # Define build targets
    admin_hidden_imports = [
        # SoulLink Tracker modules
        "soullink_tracker.main",
        "soullink_tracker.launcher",
        "soullink_tracker.config",
        "soullink_tracker.api.runs",
        "soullink_tracker.api.players",
        "soullink_tracker.api.events",
        "soullink_tracker.api.data",
        "soullink_tracker.api.websockets",
        "soullink_tracker.core.rules_engine",
        "soullink_tracker.db.models",
        "soullink_tracker.events.websocket_manager",
        "soullink_tracker.auth.security",
        # FastAPI and Uvicorn
        "uvicorn",
        "uvicorn.lifespan.on",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        # SQLAlchemy
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
        "aiosqlite",
        # FastAPI deps
        "fastapi.staticfiles",
        "fastapi.middleware.cors",
        "pydantic.json",
        # WebSockets
        "websockets",
        "websockets.server",
        # Auth
        "passlib.hash",
        "jose.jwt",
        # Optional tray
        "PIL._tkinter_finder",
    ]
    
    user_hidden_imports = [
        # SoulLink Tracker modules
        "soullink_tracker.user_launcher",
        "soullink_tracker.portable_logger",
        # Watcher modules
        "soullink_watcher",
        "soullink_watcher.main",
        "soullink_watcher.cli",
        "soullink_watcher.config",
        "soullink_watcher.ndjson_reader",
        "soullink_watcher.spool",
        "soullink_watcher.http_client",
        "soullink_watcher.retry",
        # HTTP client
        "requests",
        "urllib3",
        # Optional tray
        "PIL._tkinter_finder",
    ]
    
    # Build admin target
    if not user_only:
        print("\\n" + "="*50)
        print("Building Admin Target")
        print("="*50)
        
        admin_exe = build_target(
            entry_point_path=admin_entry,
            base_name="soullink-tracker-admin",
            is_debug=debug_mode,
            include_web=True,
            include_data=True,
            include_client=True,
            extra_paths=["src"],
            extra_hidden=admin_hidden_imports,
            collect_submodules=["soullink_tracker", "pystray", "PIL"]
        )
        
        if admin_exe:
            built_executables.append(admin_exe)
        else:
            print("ERROR: Failed to build admin target")
            return 1
    
    # Build user target
    if not admin_only:
        print("\\n" + "="*50)
        print("Building User Target")
        print("="*50)
        
        user_exe = build_target(
            entry_point_path=user_entry,
            base_name="soullink-tracker-user",
            is_debug=debug_mode,
            include_web=False,
            include_data=False,
            include_client=True,
            extra_paths=["src", "watcher/src"],
            extra_hidden=user_hidden_imports,
            collect_submodules=["soullink_watcher", "pystray", "PIL"]
        )
        
        if user_exe:
            built_executables.append(user_exe)
        else:
            print("ERROR: Failed to build user target")
            return 1
    
    print("\\n" + "="*50)
    print("Build Summary")
    print("="*50)
    for exe in built_executables:
        size_mb = get_size_mb(exe)
        print(f"✓ {exe.name} ({size_mb} MB)")
    
    print(f"\\nTotal executables built: {len(built_executables)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())