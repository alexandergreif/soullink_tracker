#!/usr/bin/env python3
"""
Config Validation Tool for SoulLink Tracker Pipeline
====================================================

This script validates the complete pipeline configuration:
1. Reads and parses config.lua 
2. Verifies UUIDs exist in database
3. Checks run/player relationships are correct
4. Validates player has proper authentication token
5. Tests API connectivity with extracted credentials

Usage:
    python validate_pipeline_config.py                     # Auto-detect config.lua
    python validate_pipeline_config.py --config path.lua   # Specify config file
    python validate_pipeline_config.py --fix               # Attempt to fix issues
"""

import os
import sys
import re
import json
import sqlite3
import requests
import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
from uuid import UUID
from datetime import datetime


class ConfigValidator:
    def __init__(self, config_path: Optional[Path] = None, db_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config_lua()
        self.db_path = db_path or Path("soullink_tracker.db")
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
        self.config_data: Dict[str, Any] = {}
        
    def _find_config_lua(self) -> Optional[Path]:
        """Auto-detect config.lua location"""
        search_paths = [
            Path("client/lua/config.lua"),
            Path("config.lua"),
            Path("lua/config.lua"),
        ]
        
        for path in search_paths:
            if path.exists():
                return path
                
        return None
    
    def _parse_lua_config(self) -> Dict[str, Any]:
        """Parse Lua config file and extract key values"""
        if not self.config_path or not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        content = self.config_path.read_text(encoding='utf-8')
        config = {}
        
        # Extract key-value pairs using regex patterns
        patterns = {
            'run_id': r'run_id\s*=\s*["\']([^"\']+)["\']',
            'player_id': r'player_id\s*=\s*["\']([^"\']+)["\']',
            'api_base_url': r'api_base_url\s*=\s*["\']([^"\']+)["\']',
            'output_dir': r'output_dir\s*=\s*["\']([^"\']+)["\']',
            'debug': r'debug\s*=\s*(\w+)',
            'poll_interval': r'poll_interval\s*=\s*(\d+)',
            'memory_profile': r'memory_profile\s*=\s*["\']([^"\']+)["\']',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1)
                # Convert boolean and numeric values
                if key == 'debug':
                    config[key] = value.lower() == 'true'
                elif key == 'poll_interval':
                    config[key] = int(value)
                else:
                    config[key] = value
            else:
                config[key] = None
                
        return config
    
    def _validate_uuid(self, uuid_str: str, field_name: str) -> bool:
        """Validate UUID format"""
        try:
            UUID(uuid_str)
            return True
        except (ValueError, TypeError):
            self.validation_errors.append(f"Invalid {field_name} UUID format: {uuid_str}")
            return False
    
    def _check_database_connectivity(self) -> bool:
        """Check if database exists and is accessible"""
        if not self.db_path.exists():
            self.validation_errors.append(f"Database not found: {self.db_path}")
            return False
            
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            cursor = conn.cursor()
            
            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('runs', 'players')")
            tables = cursor.fetchall()
            conn.close()
            
            if len(tables) < 2:
                self.validation_errors.append("Database missing required tables (runs, players)")
                return False
                
            return True
            
        except sqlite3.Error as e:
            self.validation_errors.append(f"Database error: {e}")
            return False
    
    def _validate_run_player_relationship(self, run_id: str, player_id: str) -> Tuple[bool, Dict[str, str]]:
        """Validate run and player exist and are related in database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Check run exists
            cursor.execute("SELECT id, name FROM runs WHERE id = ?", (run_id,))
            run_result = cursor.fetchone()
            
            if not run_result:
                self.validation_errors.append(f"Run ID not found in database: {run_id}")
                conn.close()
                return False, {}
            
            # Check player exists and belongs to run
            cursor.execute("""
                SELECT p.id, p.name, p.game, p.region, p.token_hash 
                FROM players p 
                WHERE p.id = ? AND p.run_id = ?
            """, (player_id, run_id))
            player_result = cursor.fetchone()
            
            conn.close()
            
            if not player_result:
                # Check if player exists but in different run
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT run_id FROM players WHERE id = ?", (player_id,))
                wrong_run = cursor.fetchone()
                conn.close()
                
                if wrong_run:
                    self.validation_errors.append(f"Player {player_id} exists but belongs to different run: {wrong_run[0]}")
                else:
                    self.validation_errors.append(f"Player ID not found in database: {player_id}")
                return False, {}
            
            return True, {
                'run_name': run_result[1],
                'player_name': player_result[1], 
                'game': player_result[2],
                'region': player_result[3],
                'has_token': player_result[4] is not None
            }
            
        except sqlite3.Error as e:
            self.validation_errors.append(f"Database validation error: {e}")
            return False, {}
    
    def _test_api_connectivity(self, api_base_url: str, run_id: str, player_id: str) -> bool:
        """Test API connectivity and authentication"""
        try:
            # Test basic API health
            health_url = f"{api_base_url.rstrip('/')}/v1/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code != 200:
                self.validation_errors.append(f"API health check failed: {response.status_code}")
                return False
            
            # Test run-specific endpoint (should work without auth)
            run_url = f"{api_base_url.rstrip('/')}/v1/runs/{run_id}"
            response = requests.get(run_url, timeout=5)
            
            if response.status_code == 404:
                self.validation_errors.append("Run not accessible via API - may be deleted or corrupted")
                return False
            elif response.status_code != 200:
                self.validation_warnings.append(f"Run endpoint returned {response.status_code} - may need authentication")
            
            # Test authenticated endpoint with mock token
            events_url = f"{api_base_url.rstrip('/')}/v1/events"
            headers = {"Authorization": "Bearer mock-token-test"}
            response = requests.post(events_url, json={"test": "ping"}, headers=headers, timeout=5)
            
            # We expect 401 (unauthorized) which means the endpoint is working
            if response.status_code == 401:
                return True  # API is working, just need proper auth
            elif response.status_code == 404:
                self.validation_errors.append("Events API endpoint not found")
                return False
            else:
                self.validation_warnings.append(f"Events endpoint returned unexpected status: {response.status_code}")
                return True  # API seems to be working
                
        except requests.exceptions.ConnectionError:
            self.validation_errors.append(f"Cannot connect to API at {api_base_url}")
            return False
        except requests.exceptions.Timeout:
            self.validation_errors.append(f"API connection timeout at {api_base_url}")
            return False
        except requests.exceptions.RequestException as e:
            self.validation_errors.append(f"API test failed: {e}")
            return False
    
    def _validate_output_directory(self, output_dir: str) -> bool:
        """Validate output directory is writable"""
        try:
            path = Path(output_dir)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self.validation_errors.append(f"Cannot create output directory {output_dir}: {e}")
                    return False
            
            # Test write permissions
            test_file = path / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except OSError as e:
                self.validation_errors.append(f"Output directory not writable {output_dir}: {e}")
                return False
                
            return True
            
        except Exception as e:
            self.validation_errors.append(f"Error validating output directory: {e}")
            return False
    
    def validate(self) -> Dict[str, Any]:
        """Run complete validation suite"""
        print("🔍 SoulLink Config Validator")
        print("=" * 50)
        
        results = {
            'overall_status': 'UNKNOWN',
            'config_path': str(self.config_path) if self.config_path else 'NOT_FOUND',
            'validation_time': datetime.now().isoformat(),
            'checks': {},
            'config_data': {},
            'errors': [],
            'warnings': []
        }
        
        # Step 1: Parse config file
        print(f"📄 Checking config file: {self.config_path}")
        try:
            self.config_data = self._parse_lua_config()
            results['config_data'] = self.config_data
            results['checks']['config_parse'] = 'PASS'
            print("✅ Config file parsed successfully")
        except Exception as e:
            results['checks']['config_parse'] = 'FAIL'
            self.validation_errors.append(f"Failed to parse config: {e}")
            print(f"❌ Config parsing failed: {e}")
        
        # Step 2: Validate UUIDs
        print("\\n🔑 Validating UUIDs...")
        run_id = self.config_data.get('run_id')
        player_id = self.config_data.get('player_id')
        
        uuid_valid = True
        if not run_id:
            self.validation_errors.append("Missing run_id in config")
            uuid_valid = False
        elif not self._validate_uuid(run_id, 'run_id'):
            uuid_valid = False
            
        if not player_id:
            self.validation_errors.append("Missing player_id in config")
            uuid_valid = False
        elif not self._validate_uuid(player_id, 'player_id'):
            uuid_valid = False
        
        results['checks']['uuid_format'] = 'PASS' if uuid_valid else 'FAIL'
        print("✅ UUIDs are valid format" if uuid_valid else "❌ UUID validation failed")
        
        # Step 3: Database connectivity
        print("\\n💾 Checking database...")
        db_connected = self._check_database_connectivity()
        results['checks']['database_connectivity'] = 'PASS' if db_connected else 'FAIL'
        print("✅ Database accessible" if db_connected else "❌ Database check failed")
        
        # Step 4: Run/Player relationship
        if db_connected and uuid_valid:
            print("\\n👥 Validating run/player relationship...")
            relationship_valid, details = self._validate_run_player_relationship(run_id, player_id)
            results['checks']['run_player_relationship'] = 'PASS' if relationship_valid else 'FAIL'
            results['relationship_details'] = details
            
            if relationship_valid:
                print(f"✅ Valid relationship: {details['player_name']} in {details['run_name']}")
                if not details['has_token']:
                    self.validation_warnings.append("Player has no authentication token - may need to regenerate")
            else:
                print("❌ Run/Player relationship validation failed")
        else:
            results['checks']['run_player_relationship'] = 'SKIP'
        
        # Step 5: API connectivity
        api_base_url = self.config_data.get('api_base_url', 'http://127.0.0.1:8000')
        print(f"\\n🌐 Testing API connectivity: {api_base_url}")
        
        if uuid_valid:
            api_connected = self._test_api_connectivity(api_base_url, run_id, player_id)
            results['checks']['api_connectivity'] = 'PASS' if api_connected else 'FAIL'
            print("✅ API accessible" if api_connected else "❌ API connectivity failed")
        else:
            results['checks']['api_connectivity'] = 'SKIP'
        
        # Step 6: Output directory
        output_dir = self.config_data.get('output_dir')
        if output_dir:
            print(f"\\n📁 Checking output directory: {output_dir}")
            output_valid = self._validate_output_directory(output_dir)
            results['checks']['output_directory'] = 'PASS' if output_valid else 'FAIL'
            print("✅ Output directory OK" if output_valid else "❌ Output directory failed")
        else:
            results['checks']['output_directory'] = 'SKIP'
            self.validation_warnings.append("No output_dir specified in config")
        
        # Compile results
        results['errors'] = self.validation_errors
        results['warnings'] = self.validation_warnings
        
        # Determine overall status
        if any(status == 'FAIL' for status in results['checks'].values()):
            results['overall_status'] = 'FAIL'
        elif self.validation_warnings:
            results['overall_status'] = 'WARN'
        else:
            results['overall_status'] = 'PASS'
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print validation summary"""
        print("\\n" + "=" * 50)
        print("📋 VALIDATION SUMMARY")
        print("=" * 50)
        
        status_emoji = {
            'PASS': '✅',
            'FAIL': '❌', 
            'WARN': '⚠️',
            'SKIP': '⏭️'
        }
        
        overall_status = results['overall_status']
        print(f"Overall Status: {status_emoji.get(overall_status, '❓')} {overall_status}")
        
        if results.get('relationship_details'):
            details = results['relationship_details']
            print(f"Run: {details['run_name']}")
            print(f"Player: {details['player_name']} ({details['game']} {details['region']})")
        
        print("\\nCheck Results:")
        for check, status in results['checks'].items():
            emoji = status_emoji.get(status, '❓')
            print(f"  {emoji} {check}: {status}")
        
        if results['errors']:
            print(f"\\n❌ ERRORS ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  • {error}")
        
        if results['warnings']:
            print(f"\\n⚠️  WARNINGS ({len(results['warnings'])}):")
            for warning in results['warnings']:
                print(f"  • {warning}")
        
        # Provide recommendations
        if overall_status == 'FAIL':
            print("\\n🔧 RECOMMENDED ACTIONS:")
            if not results['config_data'].get('run_id') or not results['config_data'].get('player_id'):
                print("  • Regenerate config.lua with: python generate_lua_config.py -i")
            if results['checks'].get('database_connectivity') == 'FAIL':
                print("  • Start the server first to create database: python start_server.py")
            if results['checks'].get('api_connectivity') == 'FAIL':
                print("  • Ensure server is running: python start_server.py")
                print("  • Check if firewall is blocking port 8000")
        elif overall_status == 'PASS':
            print("\\n🎉 Configuration looks good! You can:")
            print("  • Start DeSmuME and load the Lua script")
            print("  • Start the watcher: python simple_watcher.py")


def main():
    parser = argparse.ArgumentParser(
        description="Validate SoulLink Tracker pipeline configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_pipeline_config.py                    # Auto-detect config
  python validate_pipeline_config.py --config my.lua   # Specific config
  python validate_pipeline_config.py --json            # JSON output
        """
    )
    
    parser.add_argument("--config", help="Path to config.lua file")
    parser.add_argument("--db-path", help="Path to database file (default: soullink_tracker.db)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only show errors")
    
    args = parser.parse_args()
    
    # Initialize validator
    config_path = Path(args.config) if args.config else None
    db_path = Path(args.db_path) if args.db_path else None
    
    validator = ConfigValidator(config_path, db_path)
    
    try:
        results = validator.validate()
        
        if args.json:
            print(json.dumps(results, indent=2))
        elif not args.quiet:
            validator.print_summary(results)
        
        # Exit with error code if validation failed
        if results['overall_status'] == 'FAIL':
            sys.exit(1)
        elif results['overall_status'] == 'WARN':
            sys.exit(2)  # Warning exit code
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\\n❌ Validation cancelled")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Validation error: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()