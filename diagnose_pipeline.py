#!/usr/bin/env python3
"""
Pipeline Diagnostic Tool for SoulLink Tracker
=============================================

This script performs comprehensive diagnostics of the entire SoulLink pipeline:
1. Checks each component's configuration and status
2. Tests config.lua → Lua script communication readiness  
3. Verifies watcher can read and process config.lua
4. Tests API connectivity from watcher perspective
5. Generates detailed diagnostic report with actionable recommendations

Usage:
    python diagnose_pipeline.py                    # Full diagnostic
    python diagnose_pipeline.py --component api    # Test specific component
    python diagnose_pipeline.py --fix              # Attempt auto-fixes
    python diagnose_pipeline.py --export report.json  # Export results
"""

import os
import sys
import json
import sqlite3
import requests
import subprocess
import time
import platform
import psutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import argparse
import tempfile
from uuid import uuid4
import re


class PipelineDiagnostic:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'platform': platform.system(),
            'components': {},
            'overall_status': 'UNKNOWN',
            'recommendations': [],
            'errors': [],
            'warnings': []
        }
        
    def _run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
        """Run shell command and return success, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                cwd=Path.cwd()
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return False, "", str(e)
    
    def _find_python_executable(self) -> str:
        """Find the Python executable being used"""
        return sys.executable
    
    def _check_process_running(self, process_name: str) -> List[Dict[str, Any]]:
        """Check if process is running and return details"""
        running_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    running_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return running_processes
    
    def diagnose_config_files(self) -> Dict[str, Any]:
        """Diagnose configuration files"""
        print("📄 Diagnosing configuration files...")
        
        component = {
            'status': 'UNKNOWN',
            'files_checked': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check main config files
        config_files = [
            ('data/config.json', 'Main application config'),
            ('client/lua/config.lua', 'Lua script config'),
            ('client/lua/config.lua.example', 'Lua config template'),
            ('soullink_tracker.db', 'Main database'),
        ]
        
        for file_path, description in config_files:
            path = Path(file_path)
            file_info = {
                'exists': path.exists(),
                'readable': path.exists() and os.access(path, os.R_OK),
                'writable': path.exists() and os.access(path, os.W_OK),
                'size': path.stat().st_size if path.exists() else 0,
                'description': description
            }
            
            if path.exists():
                file_info['modified'] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            
            component['files_checked'][file_path] = file_info
            
            # Validate specific files
            if file_path == 'data/config.json' and path.exists():
                try:
                    with open(path, 'r') as f:
                        json.load(f)  # Validate JSON
                    file_info['valid_json'] = True
                except json.JSONDecodeError:
                    file_info['valid_json'] = False
                    component['issues'].append(f"Invalid JSON in {file_path}")
            
            elif file_path == 'client/lua/config.lua':
                if not path.exists():
                    component['issues'].append("config.lua not found - run python generate_lua_config.py -i")
                    component['recommendations'].append("Generate config.lua with: python generate_lua_config.py -i")
                else:
                    # Check for placeholder UUIDs
                    content = path.read_text()
                    if '550e8400-e29b-41d4-a716-446655440000' in content:
                        component['issues'].append("config.lua contains example UUIDs")
                        component['recommendations'].append("Regenerate config.lua with actual UUIDs")
        
        # Determine component status
        critical_missing = []
        for file_path, info in component['files_checked'].items():
            if not info['exists'] and file_path in ['data/config.json', 'soullink_tracker.db']:
                critical_missing.append(file_path)
        
        if critical_missing:
            component['status'] = 'FAIL'
            component['issues'].append(f"Critical files missing: {', '.join(critical_missing)}")
        elif component['issues']:
            component['status'] = 'WARN'
        else:
            component['status'] = 'PASS'
        
        return component
    
    def diagnose_api_server(self) -> Dict[str, Any]:
        """Diagnose API server status and connectivity"""
        print("🌐 Diagnosing API server...")
        
        component = {
            'status': 'UNKNOWN',
            'server_running': False,
            'endpoints_tested': {},
            'process_info': [],
            'issues': [],
            'recommendations': []
        }
        
        # Check if server process is running
        python_processes = self._check_process_running('python')
        uvicorn_processes = []
        
        for proc in python_processes:
            if 'uvicorn' in proc['cmdline'] or 'soullink_tracker' in proc['cmdline']:
                uvicorn_processes.append(proc)
        
        component['process_info'] = uvicorn_processes
        component['server_running'] = len(uvicorn_processes) > 0
        
        # Test API endpoints
        base_urls = ['http://127.0.0.1:8000', 'http://localhost:8000']
        
        for base_url in base_urls:
            endpoints = [
                ('/v1/health', 'Health check'),
                ('/v1/runs', 'Runs API'),
                ('/v1/events', 'Events API'),
                ('/admin', 'Admin panel'),
                ('/', 'Web interface')
            ]
            
            for endpoint, description in endpoints:
                url = f"{base_url}{endpoint}"
                try:
                    response = requests.get(url, timeout=5)
                    component['endpoints_tested'][url] = {
                        'status_code': response.status_code,
                        'accessible': response.status_code < 500,
                        'description': description
                    }
                except requests.exceptions.ConnectionError:
                    component['endpoints_tested'][url] = {
                        'status_code': None,
                        'accessible': False,
                        'error': 'Connection refused',
                        'description': description
                    }
                except requests.exceptions.Timeout:
                    component['endpoints_tested'][url] = {
                        'status_code': None,
                        'accessible': False,
                        'error': 'Timeout',
                        'description': description
                    }
                except Exception as e:
                    component['endpoints_tested'][url] = {
                        'status_code': None,
                        'accessible': False,
                        'error': str(e),
                        'description': description
                    }
        
        # Analyze results
        accessible_endpoints = sum(1 for ep in component['endpoints_tested'].values() if ep['accessible'])
        
        if not component['server_running']:
            component['status'] = 'FAIL'
            component['issues'].append("Server is not running")
            component['recommendations'].append("Start server with: python start_server.py")
        elif accessible_endpoints == 0:
            component['status'] = 'FAIL'  
            component['issues'].append("Server running but no endpoints accessible")
            component['recommendations'].append("Check server logs and firewall settings")
        elif accessible_endpoints < len(component['endpoints_tested']) // 2:
            component['status'] = 'WARN'
            component['issues'].append("Some endpoints not accessible")
        else:
            component['status'] = 'PASS'
        
        return component
    
    def diagnose_database(self) -> Dict[str, Any]:
        """Diagnose database connectivity and schema"""
        print("💾 Diagnosing database...")
        
        component = {
            'status': 'UNKNOWN',
            'database_exists': False,
            'tables_found': [],
            'sample_data': {},
            'issues': [],
            'recommendations': []
        }
        
        db_path = Path("soullink_tracker.db")
        component['database_exists'] = db_path.exists()
        
        if not db_path.exists():
            component['status'] = 'FAIL'
            component['issues'].append("Database file does not exist")
            component['recommendations'].append("Start server to create database: python start_server.py")
            return component
        
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            cursor = conn.cursor()
            
            # List all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            component['tables_found'] = tables
            
            # Check for required tables
            required_tables = ['runs', 'players', 'encounters', 'species', 'routes']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                component['issues'].append(f"Missing required tables: {', '.join(missing_tables)}")
                component['recommendations'].append("Run database migrations: alembic upgrade head")
            
            # Get sample data counts
            for table in ['runs', 'players', 'encounters']:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    component['sample_data'][table] = count
                    
                    if table == 'runs' and count == 0:
                        component['issues'].append("No runs found in database")
                        component['recommendations'].append("Create a run in admin panel: http://127.0.0.1:8000/admin")
            
            conn.close()
            
            if component['issues']:
                component['status'] = 'WARN'
            else:
                component['status'] = 'PASS'
                
        except sqlite3.Error as e:
            component['status'] = 'FAIL'
            component['issues'].append(f"Database error: {e}")
            component['recommendations'].append("Check database file permissions and integrity")
        
        return component
    
    def diagnose_lua_environment(self) -> Dict[str, Any]:
        """Diagnose Lua script environment and config"""
        print("🎮 Diagnosing Lua environment...")
        
        component = {
            'status': 'UNKNOWN',
            'lua_files': {},
            'config_validation': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check Lua files
        lua_files = [
            'client/lua/pokemon_tracker_v3_fixed.lua',
            'client/lua/config.lua',
            'client/lua/memory_addresses.lua'
        ]
        
        for lua_file in lua_files:
            path = Path(lua_file)
            component['lua_files'][lua_file] = {
                'exists': path.exists(),
                'size': path.stat().st_size if path.exists() else 0
            }
        
        # Validate config.lua if it exists
        config_path = Path('client/lua/config.lua')
        if config_path.exists():
            try:
                # Run config validator
                python_exe = self._find_python_executable()
                success, stdout, stderr = self._run_command([
                    python_exe, 'validate_pipeline_config.py', '--json', '--quiet'
                ])
                
                if success:
                    validation_result = json.loads(stdout)
                    component['config_validation'] = validation_result
                    
                    if validation_result['overall_status'] == 'FAIL':
                        component['issues'].extend(validation_result['errors'])
                    elif validation_result['overall_status'] == 'WARN':
                        component['issues'].extend(validation_result['warnings'])
                else:
                    component['issues'].append("Config validation failed")
                    if stderr:
                        component['issues'].append(f"Validation error: {stderr}")
            except Exception as e:
                component['issues'].append(f"Could not validate config: {e}")
        else:
            component['issues'].append("config.lua not found")
            component['recommendations'].append("Generate config.lua: python generate_lua_config.py -i")
        
        # Check for DeSmuME
        desmume_processes = self._check_process_running('desmume')
        component['desmume_running'] = len(desmume_processes) > 0
        component['desmume_processes'] = desmume_processes
        
        if not component['desmume_running']:
            component['recommendations'].append("Start DeSmuME to run Lua scripts")
        
        # Determine status
        if 'config.lua not found' in str(component['issues']):
            component['status'] = 'FAIL'
        elif component['config_validation'].get('overall_status') == 'FAIL':
            component['status'] = 'FAIL'
        elif component['issues']:
            component['status'] = 'WARN'
        else:
            component['status'] = 'PASS'
        
        return component
    
    def diagnose_watcher(self) -> Dict[str, Any]:
        """Diagnose watcher component"""
        print("👀 Diagnosing watcher...")
        
        component = {
            'status': 'UNKNOWN',
            'watcher_files': {},
            'test_run': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check watcher files
        watcher_files = [
            'simple_watcher.py',
            'watcher/src/soullink_watcher/main.py'
        ]
        
        for watcher_file in watcher_files:
            path = Path(watcher_file)
            component['watcher_files'][watcher_file] = {
                'exists': path.exists(),
                'executable': path.exists() and os.access(path, os.X_OK)
            }
        
        # Test watcher can run
        python_exe = self._find_python_executable()
        
        # Test simple_watcher.py --help
        if Path('simple_watcher.py').exists():
            success, stdout, stderr = self._run_command([
                python_exe, 'simple_watcher.py', '--help'
            ], timeout=5)
            
            component['test_run']['simple_watcher_help'] = {
                'success': success,
                'stdout_length': len(stdout) if stdout else 0,
                'has_help': 'usage:' in stdout.lower() if stdout else False
            }
            
            if not success:
                component['issues'].append("simple_watcher.py cannot run")
                if stderr:
                    component['issues'].append(f"Watcher error: {stderr[:200]}")
        
        # Check if watcher is currently running
        watcher_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'simple_watcher.py' in cmdline or 'soullink_watcher' in cmdline:
                    watcher_processes.append({
                        'pid': proc.info['pid'],
                        'cmdline': cmdline
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        component['running_processes'] = watcher_processes
        component['watcher_running'] = len(watcher_processes) > 0
        
        # Test event directory
        temp_dir = Path(tempfile.gettempdir()) / 'soullink_events'
        component['event_directory'] = {
            'path': str(temp_dir),
            'exists': temp_dir.exists(),
            'writable': temp_dir.exists() and os.access(temp_dir, os.W_OK)
        }
        
        if not temp_dir.exists():
            try:
                temp_dir.mkdir(parents=True, exist_ok=True)
                component['event_directory']['created'] = True
            except OSError:
                component['issues'].append(f"Cannot create event directory: {temp_dir}")
        
        # Determine status
        if not any(info['exists'] for info in component['watcher_files'].values()):
            component['status'] = 'FAIL'
            component['issues'].append("No watcher files found")
        elif component['issues']:
            component['status'] = 'WARN'
        else:
            component['status'] = 'PASS'
        
        return component
    
    def diagnose_integration(self) -> Dict[str, Any]:
        """Test end-to-end integration"""
        print("🔗 Testing integration...")
        
        component = {
            'status': 'UNKNOWN', 
            'tests': {},
            'issues': [],
            'recommendations': []
        }
        
        # Test 1: Config → API connectivity
        config_path = Path('client/lua/config.lua')
        if config_path.exists():
            try:
                # Parse config to get API URL
                content = config_path.read_text()
                api_match = re.search(r'api_base_url\s*=\s*["\']([^"\']+)["\']', content)
                
                if api_match:
                    api_url = api_match.group(1)
                    try:
                        response = requests.get(f"{api_url}/v1/health", timeout=5)
                        component['tests']['config_to_api'] = {
                            'success': response.status_code == 200,
                            'status_code': response.status_code,
                            'api_url': api_url
                        }
                    except Exception as e:
                        component['tests']['config_to_api'] = {
                            'success': False,
                            'error': str(e),
                            'api_url': api_url
                        }
                else:
                    component['tests']['config_to_api'] = {
                        'success': False,
                        'error': 'No api_base_url found in config'
                    }
            except Exception as e:
                component['tests']['config_to_api'] = {
                    'success': False,
                    'error': f'Config parsing failed: {e}'
                }
        
        # Test 2: Create a test event file and see if watcher could process it
        temp_dir = Path(tempfile.gettempdir()) / 'soullink_events'
        if temp_dir.exists() and os.access(temp_dir, os.W_OK):
            test_event = {
                'type': 'test',
                'timestamp': datetime.now().isoformat(),
                'data': {'test': True}
            }
            
            test_file = temp_dir / f'test_event_{uuid4().hex[:8]}.json'
            try:
                test_file.write_text(json.dumps(test_event))
                component['tests']['event_file_creation'] = {
                    'success': True,
                    'file_path': str(test_file)
                }
                
                # Clean up
                try:
                    test_file.unlink()
                except:
                    pass
                    
            except Exception as e:
                component['tests']['event_file_creation'] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Analyze integration status
        successful_tests = sum(1 for test in component['tests'].values() if test.get('success', False))
        total_tests = len(component['tests'])
        
        if successful_tests == 0:
            component['status'] = 'FAIL'
            component['issues'].append("No integration tests passed")
        elif successful_tests == total_tests:
            component['status'] = 'PASS'
        else:
            component['status'] = 'WARN'
            component['issues'].append(f"Only {successful_tests}/{total_tests} integration tests passed")
        
        return component
    
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run complete pipeline diagnostic"""
        print("🔍 SoulLink Pipeline Diagnostics")
        print("=" * 50)
        print("This will test all pipeline components...")
        print()
        
        # Run all diagnostic components
        self.results['components']['config_files'] = self.diagnose_config_files()
        self.results['components']['api_server'] = self.diagnose_api_server()  
        self.results['components']['database'] = self.diagnose_database()
        self.results['components']['lua_environment'] = self.diagnose_lua_environment()
        self.results['components']['watcher'] = self.diagnose_watcher()
        self.results['components']['integration'] = self.diagnose_integration()
        
        # Compile overall results
        statuses = [comp['status'] for comp in self.results['components'].values()]
        
        if 'FAIL' in statuses:
            self.results['overall_status'] = 'FAIL'
        elif 'WARN' in statuses:
            self.results['overall_status'] = 'WARN'
        else:
            self.results['overall_status'] = 'PASS'
        
        # Compile all issues and recommendations
        for component in self.results['components'].values():
            self.results['errors'].extend(component.get('issues', []))
            self.results['recommendations'].extend(component.get('recommendations', []))
        
        # Remove duplicates
        self.results['recommendations'] = list(set(self.results['recommendations']))
        
        return self.results
    
    def print_diagnostic_report(self):
        """Print detailed diagnostic report"""
        print("\\n" + "=" * 60)
        print("📊 PIPELINE DIAGNOSTIC REPORT")
        print("=" * 60)
        
        status_emoji = {'PASS': '✅', 'FAIL': '❌', 'WARN': '⚠️', 'UNKNOWN': '❓'}
        
        overall = self.results['overall_status']
        print(f"Overall Pipeline Status: {status_emoji[overall]} {overall}")
        print(f"Platform: {self.results['platform']}")
        print(f"Diagnostic Time: {self.results['timestamp']}")
        print()
        
        # Component summary
        print("COMPONENT STATUS:")
        print("-" * 30)
        for comp_name, comp_data in self.results['components'].items():
            status = comp_data['status']
            emoji = status_emoji[status]
            print(f"{emoji} {comp_name.replace('_', ' ').title()}: {status}")
        
        # Detailed component info
        for comp_name, comp_data in self.results['components'].items():
            print(f"\\n📋 {comp_name.replace('_', ' ').title()}")
            print("-" * 20)
            
            # Show relevant details for each component
            if comp_name == 'api_server':
                if comp_data.get('server_running'):
                    print("✅ Server process detected")
                else:
                    print("❌ No server process found")
                
                accessible = sum(1 for ep in comp_data['endpoints_tested'].values() if ep.get('accessible'))
                total = len(comp_data['endpoints_tested'])
                print(f"📡 API Endpoints: {accessible}/{total} accessible")
                
            elif comp_name == 'database':
                if comp_data.get('database_exists'):
                    tables = len(comp_data.get('tables_found', []))
                    print(f"📊 Database: {tables} tables found")
                    
                    for table, count in comp_data.get('sample_data', {}).items():
                        print(f"   • {table}: {count} records")
                else:
                    print("❌ Database file not found")
                    
            elif comp_name == 'config_files':
                for file_path, info in comp_data.get('files_checked', {}).items():
                    status = "✅" if info.get('exists') else "❌"
                    print(f"{status} {file_path}")
                    
            elif comp_name == 'lua_environment':
                config_status = comp_data.get('config_validation', {}).get('overall_status', 'UNKNOWN')
                print(f"⚙️  Config validation: {status_emoji.get(config_status, '❓')} {config_status}")
                
                if comp_data.get('desmume_running'):
                    print("✅ DeSmuME detected")
                else:
                    print("⚠️  DeSmuME not running")
                    
            elif comp_name == 'watcher':
                if comp_data.get('watcher_running'):
                    print("✅ Watcher process detected")
                else:
                    print("⚠️  No watcher process running")
                    
                event_dir = comp_data.get('event_directory', {})
                if event_dir.get('writable'):
                    print(f"📁 Event directory: {event_dir['path']}")
                else:
                    print(f"❌ Event directory not writable: {event_dir['path']}")
        
        # Issues and recommendations
        if self.results['errors']:
            print(f"\\n❌ ISSUES FOUND ({len(self.results['errors'])}):")
            for i, error in enumerate(self.results['errors'], 1):
                print(f"{i:2}. {error}")
        
        if self.results['recommendations']:
            print(f"\\n🔧 RECOMMENDATIONS ({len(self.results['recommendations'])}):")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"{i:2}. {rec}")
        
        # Next steps based on status
        print("\\n🚀 NEXT STEPS:")
        if overall == 'PASS':
            print("✅ Pipeline looks healthy! You can:")
            print("   • Start DeSmuME and load the Lua script")
            print("   • Start the watcher: python simple_watcher.py")
            print("   • Begin your SoulLink run")
        elif overall == 'FAIL':
            print("❌ Critical issues found. Please address:")
            print("   • Follow the recommendations above")
            print("   • Re-run diagnostics after fixes")
        else:  # WARN
            print("⚠️  Some issues found, but pipeline may still work:")
            print("   • Review warnings above")
            print("   • Test carefully before starting a run")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose SoulLink Tracker pipeline components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python diagnose_pipeline.py                           # Full diagnostic
  python diagnose_pipeline.py --export results.json    # Save results  
  python diagnose_pipeline.py --component api           # Test one component
        """
    )
    
    parser.add_argument("--component", 
                       choices=['config', 'api', 'database', 'lua', 'watcher', 'integration'],
                       help="Test specific component only")
    parser.add_argument("--export", help="Export results to JSON file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    
    args = parser.parse_args()
    
    diagnostic = PipelineDiagnostic()
    
    try:
        if args.component:
            # Test single component
            component_map = {
                'config': diagnostic.diagnose_config_files,
                'api': diagnostic.diagnose_api_server,
                'database': diagnostic.diagnose_database, 
                'lua': diagnostic.diagnose_lua_environment,
                'watcher': diagnostic.diagnose_watcher,
                'integration': diagnostic.diagnose_integration
            }
            
            if args.component in component_map:
                result = component_map[args.component]()
                diagnostic.results['components'][args.component] = result
                diagnostic.results['overall_status'] = result['status']
            else:
                print(f"❌ Unknown component: {args.component}")
                sys.exit(1)
        else:
            # Full diagnostic
            diagnostic.run_full_diagnostic()
        
        # Output results
        if args.json:
            print(json.dumps(diagnostic.results, indent=2))
        elif not args.quiet:
            diagnostic.print_diagnostic_report()
        
        # Export if requested
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(diagnostic.results, f, indent=2)
            if not args.quiet:
                print(f"\\n💾 Results exported to: {args.export}")
        
        # Exit codes
        status = diagnostic.results['overall_status']
        if status == 'FAIL':
            sys.exit(1)
        elif status == 'WARN':
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\\n❌ Diagnostic cancelled")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()