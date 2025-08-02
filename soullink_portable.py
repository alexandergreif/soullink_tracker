#!/usr/bin/env python3
"""
SoulLink Tracker Portable Edition - Main Entry Point

This is the entry point for the portable version of SoulLink Tracker.
When compiled with PyInstaller/Nuitka, this creates a standalone executable.

Usage:
    python soullink_portable.py        # Run in development
    soullink-tracker.exe               # Run as compiled executable
    python soullink_portable.py --debug   # Run with debug diagnostics
"""

import sys
import os
import traceback
from pathlib import Path
from datetime import datetime


def immediate_startup_log(message: str):
    """Log startup messages immediately to file and console."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"{timestamp} [STARTUP] {message}"
    
    # Print to console (visible in debug builds)
    print(log_msg)
    
    # Write to immediate startup log
    try:
        with open("soullink_startup_immediate.log", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass  # Don't fail startup if logging fails


def emergency_error_log(error: Exception, context: str = "startup"):
    """Emergency logging when main logging system isn't available."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    error_msg = f"""
{timestamp} CRITICAL ERROR in {context}
{'='*60}
Error Type: {type(error).__name__}
Error Message: {error}

System Information:
- Python Version: {sys.version}
- Python Executable: {sys.executable}
- Working Directory: {os.getcwd()}
- Script Location: {__file__ if '__file__' in globals() else 'Unknown'}
- PyInstaller Bundle: {hasattr(sys, '_MEIPASS')}
- Frozen Executable: {hasattr(sys, 'frozen')}

Python Path (first 5 entries):
{chr(10).join(f'  {i}: {path}' for i, path in enumerate(sys.path[:5]))}

Traceback:
{traceback.format_exc()}
{'='*60}
"""
    
    # Print to console (visible in debug builds)
    print(error_msg, file=sys.stderr)
    
    # Try to write to emergency log file
    try:
        with open("soullink_emergency.log", "a", encoding="utf-8") as f:
            f.write(error_msg + "\n")
    except:
        print("WARNING: Could not write to emergency log file", file=sys.stderr)


def setup_environment():
    """Setup environment and Python path."""
    try:
        # Set unbuffered output for better logging
        os.environ.setdefault('PYTHONUNBUFFERED', '1')
        
        # Detect if we're in a bundled environment
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller bundle - use the temporary directory
            bundle_dir = Path(sys._MEIPASS)
            print(f"PyInstaller bundle detected: {bundle_dir}")
        elif hasattr(sys, 'frozen'):
            # Other frozen environment
            bundle_dir = Path(sys.executable).parent
            print(f"Frozen executable detected: {bundle_dir}")
        else:
            # Development environment
            bundle_dir = Path(__file__).parent
            print(f"Development environment: {bundle_dir}")
            
        # Add src directory to Python path for imports
        src_dir = bundle_dir / "src"
        if src_dir.exists():
            sys.path.insert(0, str(src_dir))
            print(f"Added to Python path: {src_dir}")
        else:
            print(f"WARNING: src directory not found at {src_dir}")
            
        return True
        
    except Exception as e:
        emergency_error_log(e, "environment_setup")
        return False


def test_critical_imports():
    """Test critical imports before main execution."""
    print("Testing critical imports...")
    
    critical_modules = [
        ('soullink_tracker', 'Main application package'),
        ('soullink_tracker.launcher', 'Application launcher'),
        ('soullink_tracker.main', 'FastAPI application'),
        ('fastapi', 'FastAPI framework'),
        ('uvicorn', 'ASGI server'),
    ]
    
    failed_imports = []
    
    for module_name, description in critical_modules:
        try:
            __import__(module_name)
            print(f"  [OK] {module_name} ({description})")
        except ImportError as e:
            error_msg = f"  [ERROR] {module_name} ({description}): {e}"
            print(error_msg)
            failed_imports.append((module_name, str(e)))
        except Exception as e:
            error_msg = f"  [WARNING] {module_name} ({description}): {type(e).__name__}: {e}"
            print(error_msg)
            failed_imports.append((module_name, f"{type(e).__name__}: {e}"))
    
    if failed_imports:
        print(f"\nCRITICAL: {len(failed_imports)} import failures detected!")
        print("This will likely cause the application to fail.")
        print("\nFailed imports:")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return False
    else:
        print("All critical imports successful!")
        return True


def run_diagnostics():
    """Run comprehensive diagnostics."""
    print("\n" + "="*60)
    print("SoulLink Tracker Portable - Diagnostic Mode")
    print("="*60)
    
    # System information
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"PyInstaller Bundle: {hasattr(sys, '_MEIPASS')}")
    if hasattr(sys, '_MEIPASS'):
        print(f"Bundle Directory: {sys._MEIPASS}")
    print(f"Frozen Executable: {hasattr(sys, 'frozen')}")
    
    # Check environment setup
    print("\nEnvironment Setup:")
    if setup_environment():
        print("  [OK] Environment setup successful")
    else:
        print("  [ERROR] Environment setup failed")
        return False
    
    # Test imports
    print("\nImport Testing:")
    if test_critical_imports():
        print("  [OK] All critical imports successful")
    else:
        print("  [ERROR] Critical import failures detected")
        return False
    
    # Try to initialize logging
    print("\nLogging System:")
    try:
        from soullink_tracker.portable_logger import setup_portable_logging
        logger = setup_portable_logging(debug=True)
        logger.create_diagnostic_dump()
        print("  [OK] Logging system initialized")
        print(f"  [OK] Logs directory: {logger.log_dir}")
    except Exception as e:
        print(f"  [ERROR] Logging system failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("Diagnostic complete - ready to run application")
    print("="*60)
    return True


def main():
    """Enhanced main entry point with comprehensive error handling."""
    immediate_startup_log("=== SoulLink Tracker Portable Edition Starting ===")
    immediate_startup_log("Python version: " + sys.version.split()[0])
    immediate_startup_log("Working directory: " + os.getcwd())
    immediate_startup_log("Script arguments: " + str(sys.argv))
    
    try:
        # Check for debug/diagnostic mode
        debug_mode = '--debug' in sys.argv or '--diagnostics' in sys.argv
        immediate_startup_log(f"Debug mode: {debug_mode}")
        
        if debug_mode:
            immediate_startup_log("Running comprehensive diagnostics...")
            if not run_diagnostics():
                immediate_startup_log("CRITICAL: Diagnostics failed - cannot continue")
                print("\nDiagnostics failed - cannot continue")
                return 1
        else:
            # Normal startup - quick environment setup
            immediate_startup_log("Running normal startup sequence...")
            print("SoulLink Tracker Portable Edition")
            print("Starting up...")
            
            immediate_startup_log("Setting up environment...")
            if not setup_environment():
                immediate_startup_log("CRITICAL: Environment setup failed")
                print("Environment setup failed - try running with --debug for more info")
                return 1
            
            immediate_startup_log("Testing critical imports...")
            if not test_critical_imports():
                immediate_startup_log("CRITICAL: Import test failed")
                print("Import test failed - try running with --debug for more info")
                return 1
        
        # Initialize portable logging
        immediate_startup_log("Initializing portable logging system...")
        try:
            from soullink_tracker.portable_logger import setup_portable_logging
            logger = setup_portable_logging(debug=debug_mode)
            immediate_startup_log(f"Portable logging initialized: {logger.log_dir}")
            print(f"Logging initialized: {logger.log_dir}")
        except Exception as e:
            immediate_startup_log(f"WARNING: Could not initialize logging system: {e}")
            print(f"Warning: Could not initialize logging system: {e}")
            print("Continuing without enhanced logging...")
        
        # Import and run the main launcher
        immediate_startup_log("Importing main launcher...")
        try:
            from soullink_tracker.launcher import main as launcher_main
            immediate_startup_log("Main launcher imported successfully")
            print("Starting SoulLink Tracker...")
            immediate_startup_log("Calling launcher main function...")
            result = launcher_main()
            immediate_startup_log(f"Launcher completed with exit code: {result}")
            return result
            
        except ImportError as e:
            immediate_startup_log(f"FATAL: Could not import launcher: {e}")
            emergency_error_log(e, "launcher_import")
            print(f"\nFATAL: Could not import launcher: {e}")
            print("This indicates the application bundle is incomplete.")
            print("Try running with --debug for detailed diagnostics.")
            return 1
            
    except KeyboardInterrupt:
        immediate_startup_log("Shutdown requested by user (KeyboardInterrupt)")
        print("\nShutdown requested by user")
        return 0
        
    except Exception as e:
        immediate_startup_log(f"FATAL UNEXPECTED ERROR: {type(e).__name__}: {e}")
        emergency_error_log(e, "main_execution")
        print(f"\nFATAL UNEXPECTED ERROR: {type(e).__name__}: {e}")
        print("Check soullink_emergency.log for detailed error information.")
        print("Try running with --debug for comprehensive diagnostics.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)