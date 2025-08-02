#!/usr/bin/env python3
"""
Pre-commit hook to check for problematic Unicode characters in Python files.
Prevents regression of Windows cp1252 encoding issues.

Usage:
    python scripts/check_unicode.py [file1.py file2.py ...]
    
Returns:
    0 if no issues found
    1 if problematic Unicode characters detected
"""

import re
import sys
from pathlib import Path
from typing import List


def check_file_for_unicode(file_path: Path) -> List[str]:
    """Check a single Python file for problematic Unicode characters.
    
    Args:
        file_path: Path to the Python file to check
        
    Returns:
        List of problematic Unicode characters found (empty if none)
    """
    # Unicode characters that cause cp1252 encoding issues
    problematic_pattern = re.compile(r'[🚀🎉🎮✅❌⚠️🗑️🗄️⚙️❤️🛠️🕹️⏱️💾🔧🔍📦📁📊👥🌐💿🔄👀🧹🏁]')
    
    try:
        content = file_path.read_text(encoding='utf-8')
        matches = problematic_pattern.findall(content)
        return list(set(matches))  # Remove duplicates
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return []


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_unicode.py <file1.py> [file2.py ...]")
        print("Checks Python files for problematic Unicode characters.")
        sys.exit(1)
    
    issues_found = 0
    total_files = 0
    
    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)
        
        if not file_path.exists():
            print(f"File not found: {file_path}", file=sys.stderr)
            issues_found += 1
            continue
            
        if not file_path.suffix == '.py':
            continue  # Skip non-Python files
            
        total_files += 1
        unicode_chars = check_file_for_unicode(file_path)
        
        if unicode_chars:
            print(f"❌ {file_path}: Found problematic Unicode: {unicode_chars}")
            issues_found += 1
        else:
            print(f"✅ {file_path}: Clean")
    
    print(f"\nScanned {total_files} Python files")
    
    if issues_found > 0:
        print(f"❌ Found Unicode issues in {issues_found} files")
        print("\nTo fix these issues:")
        print("1. Replace Unicode emoji with ASCII alternatives:")
        print("   🚀 → [START] or Starting...")
        print("   ✅ → [OK] or SUCCESS")
        print("   ❌ → [ERROR] or FAILED")
        print("   ⚠️ → [WARNING] or WARN")
        print("   🎉 → [COMPLETE] or Complete!")
        print("2. Test with: python scripts/test_windows_compatibility.py")
        sys.exit(1)
    else:
        print("✅ All files clean of problematic Unicode")
        sys.exit(0)


if __name__ == "__main__":
    main()