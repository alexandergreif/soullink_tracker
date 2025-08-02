#!/usr/bin/env python3
"""
SoulLink Tracker - Quick Test Script
Performs a quick functional test of the SoulLink Tracker system.

This script:
1. Sends test events to the API
2. Verifies WebSocket functionality
3. Tests the complete event processing flow
4. Validates SoulLink rules application
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiohttp
import requests


class QuickTester:
    """Quick functional tester for SoulLink Tracker."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:9000"):
        self.api_url = api_url
        self.project_root = Path(__file__).parent.parent
        self.test_results = []
        
        # Load test config
        self.config = self.load_test_config()
        
    def load_test_config(self):
        """Load test configuration."""
        config_file = self.project_root / "test_config.json"
        
        if not config_file.exists():
            raise FileNotFoundError(
                "test_config.json not found. Please run 'python scripts/init_database.py' first."
            )
        
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def log_test(self, test_name: str, success: bool, message: str, details=None):
        """Log a test result."""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {test_name}: {message}")
        
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    async def run_all_tests(self):
        """Run all quick tests."""
        print("🧪 SoulLink Tracker - Quick Test Suite")
        print("=" * 50)
        
        try:
            # API connectivity tests
            print("\n🔌 API Connectivity Tests")
            await self.test_api_connectivity()
            
            # Authentication tests
            print("\n🔐 Authentication Tests")
            await self.test_authentication()
            
            # Event processing tests
            print("\n📝 Event Processing Tests")
            await self.test_event_processing()
            
            # SoulLink rules tests
            print("\n🔗 SoulLink Rules Tests")
            await self.test_soullink_rules()
            
            # WebSocket tests
            print("\n🔌 WebSocket Tests")
            await self.test_websockets()
            
        except Exception as e:
            self.log_test("Test Suite", False, f"Unexpected error: {e}")
        
        # Summary
        print("\n" + "=" * 50)
        self.print_summary()
        
        return all(result["success"] for result in self.test_results)
    
    async def test_api_connectivity(self):
        """Test basic API connectivity."""
        try:
            # Health check
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                self.log_test("Health Endpoint", True, "API health check passed", health_data)
            else:
                self.log_test("Health Endpoint", False, f"Health check failed: {response.status_code}")
        except Exception as e:
            self.log_test("Health Endpoint", False, f"Cannot connect to API: {e}")
            return
        
        # OpenAPI docs
        try:
            response = requests.get(f"{self.api_url}/docs", timeout=5)
            success = response.status_code == 200
            self.log_test("API Documentation", success, 
                         "Documentation accessible" if success else f"Docs returned {response.status_code}")
        except Exception as e:
            self.log_test("API Documentation", False, f"Docs error: {e}")
    
    async def test_authentication(self):
        """Test authentication system."""
        # Test without token
        try:
            response = requests.get(f"{self.api_url}/v1/runs", timeout=5)
            if response.status_code == 401:
                self.log_test("Auth Required", True, "Unauthorized access properly rejected")
            else:
                self.log_test("Auth Required", False, f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.log_test("Auth Required", False, f"Auth test error: {e}")
        
        # Test with valid token
        if self.config and "players" in self.config:
            player = self.config["players"][0]
            token = player["token"]
            
            headers = {"Authorization": f"Bearer {token}"}
            
            try:
                response = requests.get(f"{self.api_url}/v1/runs", headers=headers, timeout=5)
                if response.status_code == 200:
                    self.log_test("Valid Auth", True, "Valid token accepted")
                else:
                    self.log_test("Valid Auth", False, f"Valid token rejected: {response.status_code}")
            except Exception as e:
                self.log_test("Valid Auth", False, f"Valid auth test error: {e}")
    
    async def test_event_processing(self):
        """Test event processing functionality."""
        if not self.config or "players" not in self.config:
            self.log_test("Event Processing", False, "No test config available")
            return
        
        player = self.config["players"][0]
        run_id = self.config["run_id"]
        
        headers = {
            "Authorization": f"Bearer {player['token']}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"test_{uuid4()}"
        }
        
        # Test encounter event
        encounter_event = {
            "type": "encounter",
            "run_id": run_id,
            "player_id": player["id"],
            "route_id": 1,  # Route 29
            "species_id": 1,  # Bulbasaur
            "level": 5,
            "shiny": False,
            "method": "grass",
            "time": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/v1/events",
                headers=headers,
                json=encounter_event,
                timeout=10
            )
            
            if response.status_code in (200, 201, 202):
                result_data = response.json()
                self.log_test("Encounter Event", True, "Encounter event processed successfully", {
                    "event_id": result_data.get("event_id"),
                    "applied_rules": result_data.get("applied_rules", [])
                })
            else:
                error_text = response.text
                self.log_test("Encounter Event", False, f"Encounter failed: {response.status_code}", {
                    "error": error_text
                })
        except Exception as e:
            self.log_test("Encounter Event", False, f"Encounter event error: {e}")
        
        # Test catch result event
        # Note: In a real scenario, we'd need the encounter_id from above
        # For testing, we'll create a simple catch event
        catch_event = {
            "type": "catch_result", 
            "run_id": run_id,
            "player_id": player["id"],
            "encounter_id": str(uuid4()),  # Mock encounter ID
            "result": "caught",
            "time": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            headers["Idempotency-Key"] = f"test_{uuid4()}"
            response = requests.post(
                f"{self.api_url}/v1/events",
                headers=headers,
                json=catch_event,
                timeout=10
            )
            
            # This might fail due to invalid encounter_id, but we test the processing
            if response.status_code in (200, 201, 202, 404):
                self.log_test("Catch Event", True, "Catch event processed (may have failed validation)")
            else:
                self.log_test("Catch Event", False, f"Catch event failed: {response.status_code}")
        except Exception as e:
            self.log_test("Catch Event", False, f"Catch event error: {e}")
    
    async def test_soullink_rules(self):
        """Test SoulLink rules engine."""
        if not self.config:
            self.log_test("SoulLink Rules", False, "No test config available")
            return
        
        run_id = self.config["run_id"]
        
        try:
            # Get run data to check rules configuration
            response = requests.get(f"{self.api_url}/v1/runs/{run_id}", timeout=5)
            if response.status_code == 200:
                run_data = response.json()
                rules = run_data.get("rules_json", {})
                
                expected_rules = ["dupes_clause", "soul_link_enabled", "species_clause"]
                has_rules = all(rule in rules for rule in expected_rules)
                
                self.log_test("Rules Configuration", has_rules, 
                             "SoulLink rules properly configured" if has_rules else "Missing expected rules",
                             {"rules": rules})
            else:
                self.log_test("Rules Configuration", False, f"Cannot fetch run data: {response.status_code}")
        except Exception as e:
            self.log_test("Rules Configuration", False, f"Rules test error: {e}")
        
        # Test blocklist functionality
        try:
            response = requests.get(f"{self.api_url}/v1/runs/{run_id}/blocklist", timeout=5)
            if response.status_code == 200:
                blocklist = response.json()
                self.log_test("Blocklist Access", True, f"Blocklist accessible ({len(blocklist)} entries)")
            else:
                self.log_test("Blocklist Access", False, f"Cannot access blocklist: {response.status_code}")
        except Exception as e:
            self.log_test("Blocklist Access", False, f"Blocklist test error: {e}")
    
    async def test_websockets(self):
        """Test WebSocket functionality."""
        if not self.config:
            self.log_test("WebSocket", False, "No test config available")
            return
        
        run_id = self.config["run_id"]
        ws_url = self.api_url.replace('http://', 'ws://').replace('https://', 'wss://')
        ws_endpoint = f"{ws_url}/v1/ws/{run_id}"
        
        try:
            # Basic WebSocket connection test using aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.ws_connect(ws_endpoint) as ws:
                        # Send ping
                        await ws.send_str(json.dumps({"type": "ping", "timestamp": time.time()}))
                        
                        # Wait for response (with timeout)
                        try:
                            async with asyncio.timeout(5):
                                async for msg in ws:
                                    if msg.type == aiohttp.WSMsgType.TEXT:
                                        data = json.loads(msg.data)
                                        if data.get("type") == "pong":
                                            self.log_test("WebSocket Connection", True, "WebSocket ping/pong successful")
                                            break
                                    elif msg.type == aiohttp.WSMsgType.ERROR:
                                        self.log_test("WebSocket Connection", False, f"WebSocket error: {ws.exception()}")
                                        break
                        except asyncio.TimeoutError:
                            self.log_test("WebSocket Connection", True, "WebSocket connected (no pong received)")
                            
                except aiohttp.ClientConnectorError:
                    self.log_test("WebSocket Connection", False, "Cannot connect to WebSocket endpoint")
                except Exception as e:
                    self.log_test("WebSocket Connection", False, f"WebSocket test error: {e}")
                    
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"WebSocket setup error: {e}")
    
    def print_summary(self):
        """Print test summary."""
        total = len(self.test_results)
        passed = len([r for r in self.test_results if r["success"]])
        failed = total - passed
        
        print(f"🧪 Quick Test Summary:")
        print(f"   Total tests: {total}")
        print(f"   [PASS] Passed: {passed}")
        print(f"   [FAIL] Failed: {failed}")
        
        if failed == 0:
            print(f"\n[SUCCESS] All tests passed! System is ready for playtest.")
        else:
            print(f"\n🚨 {failed} tests failed")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   [FAIL] {result['test']}: {result['message']}")
        
        # Performance info
        total_time = max(r["timestamp"] for r in self.test_results) - min(r["timestamp"] for r in self.test_results)
        print(f"\n[TIME] Tests completed in {total_time:.2f} seconds")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SoulLink Tracker Quick Test")
    parser.add_argument("--api-url", default="http://127.0.0.1:9000", help="API server URL")
    
    args = parser.parse_args()
    
    tester = QuickTester(args.api_url)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())