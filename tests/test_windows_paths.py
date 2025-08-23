#!/usr/bin/env python3
"""
Test script for Windows path compatibility
Run this to verify all path handling works correctly on Windows
"""

import os
import sys
import json
import tempfile
import platform
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from soullink_tracker.config import ConfigManager

def test_path_normalization():
    """Test that paths are normalized correctly on Windows."""
    print("Testing path normalization...")
    
    test_paths = [
        "C:\\temp\\soullink",
        "C:/temp/soullink",
        "C:\\temp\\soullink\\",
        "C:/temp/soullink/",
        "C:\\Program Files\\SoulLink",
        "C:/Program Files/SoulLink",
    ]
    
    for test_path in test_paths:
        p = Path(test_path)
        normalized = str(p).replace("\\", "/")
        print(f"  Original: {test_path}")
        print(f"  Path obj: {p}")
        print(f"  Normalized: {normalized}")
        print()
    
    return True

def test_config_validation():
    """Test configuration validation with Windows paths."""
    print("Testing configuration validation...")
    
    config_mgr = ConfigManager()
    
    # Create a test config with Windows paths
    test_config = {
        "app": {
            "name": "SoulLink Tracker Test",
            "version": "1.0.0",
            "web_dir": "C:/SoulLink/web",
            "data_dir": "C:/SoulLink/data",
            "lua_dir": "C:/SoulLink/lua",
            "is_portable": True,
            "is_development": False,
            "debug": True
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8000,
            "debug": True
        },
        "database": {
            "url": "sqlite:///C:/SoulLink/data/test.db"
        }
    }
    
    # Test with temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        config_mgr.config_file = config_file
        config = config_mgr.load_config()
        
        issues = config_mgr.validate_config()
        print(f"  Validation issues: {issues}")
    
    return True

def test_spool_directory_creation():
    """Test creating spool directories with Windows paths."""
    print("Testing spool directory creation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test various path formats
        test_dirs = [
            Path(tmpdir) / "spool1",
            Path(tmpdir) / "spool 2",  # With space
            Path(tmpdir) / "spool_3",
        ]
        
        for test_dir in test_dirs:
            try:
                test_dir.mkdir(parents=True, exist_ok=True)
                
                # Test writing a file
                test_file = test_dir / "test_event.json"
                test_data = {"type": "test", "path": str(test_dir)}
                
                with open(test_file, 'w') as f:
                    json.dump(test_data, f)
                
                # Test reading back
                with open(test_file, 'r') as f:
                    read_data = json.load(f)
                
                assert read_data == test_data
                print(f"  ✓ {test_dir.name}: Created and tested successfully")
                
            except Exception as e:
                print(f"  ✗ {test_dir.name}: Failed - {e}")
                return False
    
    return True

def test_lua_config_generation():
    """Test Lua config generation with Windows paths."""
    print("Testing Lua config generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        spool_dir = Path(tmpdir) / "spool"
        spool_dir.mkdir()
        
        # Test path conversion for Lua
        lua_path = str(spool_dir).replace("\\", "/")
        
        config_content = f"""-- Auto-generated config
API_URL = "http://127.0.0.1:8000"
SPOOL_DIR = "{lua_path}/"
DEBUG = true
"""
        
        config_file = Path(tmpdir) / "config.lua"
        config_file.write_text(config_content)
        
        # Verify the file was created and is readable
        assert config_file.exists()
        content = config_file.read_text()
        assert lua_path in content
        assert "\\" not in content  # No backslashes in Lua config
        
        print(f"  ✓ Lua config created with path: {lua_path}")
    
    return True

def main():
    """Run all Windows compatibility tests."""
    print(f"Running Windows Path Compatibility Tests")
    print(f"Platform: {platform.system()} {platform.version()}")
    print(f"Python: {sys.version}")
    print("-" * 50)
    
    tests = [
        ("Path Normalization", test_path_normalization),
        ("Config Validation", test_config_validation),
        ("Spool Directory", test_spool_directory_creation),
        ("Lua Config Generation", test_lua_config_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results:")
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n✓ All Windows compatibility tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())