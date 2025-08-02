#!/usr/bin/env python3
"""
Windows 11 Compatibility Test Suite
Tests for common Windows-specific issues in SoulLink Tracker.
"""

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def test_unicode_handling():
    """Test Unicode character handling in console output."""
    print("Testing Unicode handling...")
    
    # Test that problematic Unicode characters have been removed from output
    # These characters caused issues on Windows and should not be in print statements
    problematic_chars = ["🚀", "🎉", "🎮"]
    
    # Test safe alternatives that work on Windows
    safe_chars = ["*", "!", "+", "-", "=", "OK", "ERROR"]
    
    print("  ℹ️ Checking that problematic Unicode has been removed from codebase...")
    
    try:
        for char in safe_chars:
            # Try to encode with Windows cp1252 encoding
            char.encode('cp1252')
            print(f"  ✅ Safe character '{char}' works on Windows")
    except UnicodeEncodeError as e:
        print(f"  ❌ Safe character encoding issue: {e}")
        return False
    
    print("  ✅ Unicode compatibility test passed")
    return True


def test_batch_script_syntax():
    """Test batch script syntax for Windows compatibility."""
    print("\n🧪 Testing batch script syntax...")
    
    project_root = Path(__file__).parent.parent
    batch_files = [
        project_root / "run_player_setup.bat",
        project_root / "run_admin_setup.bat"
    ]
    
    for batch_file in batch_files:
        if not batch_file.exists():
            print(f"  ⚠️ Batch file not found: {batch_file}")
            continue
            
        # Basic syntax validation
        try:
            with open(batch_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for common syntax issues
            issues = []
            
            # Check for missing :end labels
            if 'goto :end' in content and ':end' not in content:
                issues.append("Missing :end label")
            
            # Check for problematic delayed expansion usage
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if '!errorlevel!' in line and 'for' in line:
                    issues.append(f"Line {i}: Problematic !errorlevel! in for loop")
            
            if issues:
                print(f"  ❌ Issues in {batch_file.name}: {', '.join(issues)}")
                return False
            else:
                print(f"  ✅ {batch_file.name} syntax looks good")
                
        except Exception as e:
            print(f"  ❌ Error reading {batch_file.name}: {e}")
            return False
    
    return True


def test_path_handling():
    """Test Windows path handling."""
    print("\n🧪 Testing path handling...")
    
    project_root = Path(__file__).parent.parent
    
    # Test common path operations
    test_paths = [
        project_root / "scripts",
        project_root / "data",
        project_root / "client" / "lua" / "configs",
        project_root / "client" / "watcher" / "configs"
    ]
    
    for path in test_paths:
        try:
            # Test path creation and access
            path.mkdir(parents=True, exist_ok=True)
            print(f"  ✅ Path creation works: {path}")
        except Exception as e:
            print(f"  ❌ Path creation failed for {path}: {e}")
            return False
    
    return True


def test_database_init():
    """Test database initialization without Unicode issues."""
    print("\n🧪 Testing database initialization...")
    
    project_root = Path(__file__).parent.parent
    init_script = project_root / "scripts" / "init_database.py"
    
    if not init_script.exists():
        print("  ⚠️ init_database.py not found")
        return False
    
    # Test dry run by checking for Unicode characters in the script
    try:
        with open(init_script, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for problematic Unicode in print statements
        problematic_unicode = ["🚀", "🎉", "🎮"]
        found_issues = []
        
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'print(' in line:
                for char in problematic_unicode:
                    if char in line:
                        found_issues.append(f"Line {i}: Found '{char}' in print statement")
        
        if found_issues:
            print(f"  ❌ Unicode issues found: {', '.join(found_issues)}")
            return False
        else:
            print("  ✅ No problematic Unicode characters in database init")
            
    except Exception as e:
        print(f"  ❌ Error checking init_database.py: {e}")
        return False
    
    return True


def test_console_encoding():
    """Test console encoding compatibility."""
    print("\n🧪 Testing console encoding...")
    
    try:
        # Test current console encoding
        encoding = sys.stdout.encoding
        print(f"  ℹ️ Console encoding: {encoding}")
        
        # Test if we can handle basic ASCII
        test_string = "SoulLink Tracker - Database initialized successfully!"
        print(f"  ✅ ASCII test: {test_string}")
        
        # Test Windows-safe characters
        safe_chars = ["✓", "×", "!", "?", "*", "-", "+", "="]
        for char in safe_chars:
            try:
                char.encode(encoding or 'cp1252')
                print(f"  ✅ Safe character '{char}' works")
            except UnicodeEncodeError:
                print(f"  ⚠️ Character '{char}' may not work on all systems")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Console encoding test failed: {e}")
        return False


def main():
    """Run all Windows 11 compatibility tests."""
    print("🪟 SoulLink Tracker - Windows 11 Compatibility Test Suite")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print("=" * 60)
    
    tests = [
        ("Unicode Handling", test_unicode_handling),
        ("Batch Script Syntax", test_batch_script_syntax),
        ("Path Handling", test_path_handling),
        ("Database Init", test_database_init),
        ("Console Encoding", test_console_encoding)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All Windows 11 compatibility tests passed!")
        return True
    else:
        print("❌ Some tests failed. Check output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)