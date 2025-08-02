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


def test_api_imports():
    """Test that all API modules can be imported."""
    print("🔍 Testing API module imports...")
    
    # Add src to path for testing
    src_dir = Path.cwd() / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    api_modules = [
        "soullink_tracker.main",
        "soullink_tracker.config", 
        "soullink_tracker.launcher",
        "soullink_tracker.api.runs",
        "soullink_tracker.api.players",
        "soullink_tracker.api.events",
        "soullink_tracker.api.data",
        "soullink_tracker.api.websockets",
    ]
    
    failed_imports = []
    for module in api_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            failed_imports.append((module, str(e)))
        except Exception as e:
            print(f"  ⚠️ {module}: {e}")
            
    if failed_imports:
        print(f"\n⚠️ Warning: {len(failed_imports)} API modules failed to import")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return False
    
    print("✅ All API modules imported successfully")
    return True

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
    
    # Test API imports before building
    if not test_api_imports():
        print("❌ API import test failed - build may not work correctly")
        # Continue anyway but warn user
    
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
    
    # Build command with comprehensive hidden imports
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", exe_name.replace(".exe", ""),  # Remove .exe for PyInstaller
        "--add-data", "web:web",
        "--add-data", "client:client", 
        "--add-data", "data:data",
        # Core FastAPI and Uvicorn imports
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        # SQLAlchemy imports
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "sqlalchemy.dialects.sqlite.pysqlite",
        "--hidden-import", "sqlalchemy.pool",
        "--hidden-import", "sqlalchemy.pool.impl",
        "--hidden-import", "sqlalchemy.event",
        "--hidden-import", "sqlalchemy.ext.declarative",
        "--hidden-import", "aiosqlite",
        # FastAPI and Pydantic imports
        "--hidden-import", "fastapi.staticfiles",
        "--hidden-import", "fastapi.middleware.cors",
        "--hidden-import", "fastapi.responses",
        "--hidden-import", "pydantic.json",
        "--hidden-import", "pydantic.types",
        "--hidden-import", "pydantic.validators",
        # WebSocket imports
        "--hidden-import", "websockets",
        "--hidden-import", "websockets.server",
        "--hidden-import", "websockets.protocol",
        # Cryptography imports
        "--hidden-import", "cryptography.fernet",
        "--hidden-import", "cryptography.hazmat.primitives",
        "--hidden-import", "cryptography.hazmat.backends",
        "--hidden-import", "cryptography.hazmat.backends.openssl",
        # Authentication imports
        "--hidden-import", "passlib.hash",
        "--hidden-import", "passlib.context",
        "--hidden-import", "jose.jwt",
        # JSON and multipart
        "--hidden-import", "python_multipart",
        "--hidden-import", "multipart.multipart",
        # Optional system tray imports (don't fail if missing)
        "--hidden-import", "PIL._tkinter_finder",
        "--collect-submodules", "pystray",
        "--collect-submodules", "PIL",
        "--noconfirm",
        str(entry_point)
    ]
    
    # Platform specific options
    if platform.system() == "Windows":
        cmd.extend(["--windowed"])
    elif platform.system() == "Darwin":
        cmd.extend(["--windowed"])
    
    # Run PyInstaller with better error handling
    print("🚀 Running PyInstaller...")
    print(f"Command: {' '.join(cmd[:10])}... (truncated, {len(cmd)} total args)")
    
    try:
        # Test basic imports first
        print("📋 Testing basic imports...")
        test_imports = [
            "fastapi", "uvicorn", "sqlalchemy", "pydantic", 
            "websockets", "cryptography", "passlib"
        ]
        for imp in test_imports:
            try:
                __import__(imp)
                print(f"  ✅ {imp}")
            except ImportError as ie:
                print(f"  ❌ {imp}: {ie}")
                return 1

        # Run PyInstaller
        print("\n🔨 Building executable...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ PyInstaller completed successfully")
        
        # Show relevant output
        if result.stdout:
            lines = result.stdout.split('\n')
            # Show warning and error lines
            important_lines = [line for line in lines if any(keyword in line.lower() 
                             for keyword in ['warning', 'error', 'missing', 'failed', 'building'])]
            if important_lines:
                print("\n📊 Important build messages:")
                for line in important_lines[-10:]:  # Last 10 important lines
                    print(f"  {line}")
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ PyInstaller failed with return code: {e.returncode}")
        
        # Show detailed error information
        if e.stdout:
            print("\n📤 STDOUT (last 1500 chars):")
            print("-" * 50)
            print(e.stdout[-1500:])
            print("-" * 50)
            
        if e.stderr:
            print("\n📥 STDERR (last 1500 chars):")
            print("-" * 50)
            print(e.stderr[-1500:])
            print("-" * 50)
            
        # Look for specific error patterns
        combined_output = (e.stdout or '') + (e.stderr or '')
        if 'ModuleNotFoundError' in combined_output:
            print("\n💡 Tip: Missing module error detected. Check hidden imports.")
        if 'ImportError' in combined_output:
            print("💡 Tip: Import error detected. Verify all dependencies are installed.")
        if 'permission' in combined_output.lower():
            print("💡 Tip: Permission error detected. Check file/directory permissions.")
            
        return 1
    
    except Exception as e:
        print(f"\n❌ Unexpected error during build: {e}")
        print(f"Error type: {type(e).__name__}")
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