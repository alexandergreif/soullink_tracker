"""
Comprehensive E2E pipeline tests with performance benchmarks and chaos testing.

Tests include:
- Complete event flow from Lua → JSON → Watcher → API → WebSocket → Dashboard
- Performance benchmarks for <1s latency requirement
- Chaos testing for network issues and failures
- 95% accuracy verification for encounter detection
- 2+ hour session stability testing
"""

import asyncio
import json
import os
import random
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock, Mock
import threading
from contextlib import contextmanager

import pytest
import requests
from fastapi.testclient import TestClient

from tests.fixtures.event_fixtures import (
    EventFixtureFactory,
    EventFileGenerator,
    EncounterFixture,
    CatchResultFixture,
    FaintFixture,
    create_test_fixtures
)


class PerformanceMetrics:
    """Track performance metrics for E2E testing."""
    
    def __init__(self):
        self.latencies = []
        self.errors = []
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start timing."""
        self.start_time = time.perf_counter()
    
    def record_latency(self, latency_ms: float):
        """Record a latency measurement."""
        self.latencies.append(latency_ms)
    
    def record_error(self, error: str):
        """Record an error."""
        self.errors.append(error)
    
    def stop(self):
        """Stop timing."""
        self.end_time = time.perf_counter()
    
    @property
    def duration(self) -> float:
        """Get total duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def avg_latency(self) -> float:
        """Get average latency in ms."""
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0
    
    @property
    def p95_latency(self) -> float:
        """Get 95th percentile latency in ms."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
    
    @property
    def p99_latency(self) -> float:
        """Get 99th percentile latency in ms."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
    
    @property
    def error_rate(self) -> float:
        """Get error rate as percentage."""
        total = len(self.latencies) + len(self.errors)
        return (len(self.errors) / total * 100) if total > 0 else 0
    
    def report(self) -> Dict[str, Any]:
        """Generate performance report."""
        return {
            "duration_seconds": self.duration,
            "total_events": len(self.latencies) + len(self.errors),
            "successful_events": len(self.latencies),
            "failed_events": len(self.errors),
            "error_rate_percent": self.error_rate,
            "avg_latency_ms": self.avg_latency,
            "p95_latency_ms": self.p95_latency,
            "p99_latency_ms": self.p99_latency,
            "min_latency_ms": min(self.latencies) if self.latencies else 0,
            "max_latency_ms": max(self.latencies) if self.latencies else 0
        }


class ChaosMonkey:
    """Inject failures and delays for chaos testing."""
    
    def __init__(self, failure_rate: float = 0.1, delay_range: tuple = (0, 500)):
        self.failure_rate = failure_rate
        self.delay_range = delay_range
        self.enabled = False
    
    @contextmanager
    def chaos_mode(self):
        """Enable chaos mode for testing."""
        self.enabled = True
        try:
            yield self
        finally:
            self.enabled = False
    
    def maybe_fail(self) -> bool:
        """Randomly decide to fail based on failure rate."""
        if self.enabled and random.random() < self.failure_rate:
            return True
        return False
    
    def maybe_delay(self):
        """Add random delay if chaos is enabled."""
        if self.enabled:
            delay_ms = random.randint(*self.delay_range)
            time.sleep(delay_ms / 1000)
    
    def inject_network_error(self):
        """Simulate network error."""
        if self.maybe_fail():
            errors = [
                requests.ConnectionError("Connection refused"),
                requests.Timeout("Request timed out"),
                requests.HTTPError("500 Internal Server Error")
            ]
            raise random.choice(errors)
        self.maybe_delay()


class MockWatcherWithChaos:
    """Enhanced watcher with chaos testing capabilities."""
    
    def __init__(self, api_url: str, token: str, chaos: Optional[ChaosMonkey] = None):
        self.api_url = api_url
        self.token = token
        self.chaos = chaos or ChaosMonkey()
        self.processed_events = []
        self.failed_events = []
        self.retry_count = 3
        self.retry_delay = 0.1
    
    def process_event(self, event_data: Dict[str, Any]) -> bool:
        """Process single event with retry logic."""
        for attempt in range(self.retry_count):
            try:
                # Inject chaos if enabled
                if self.chaos:
                    self.chaos.inject_network_error()
                
                # Send to API
                response = requests.post(
                    f"{self.api_url}/v1/events",
                    json=event_data,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Idempotency-Key": str(uuid.uuid4())
                    },
                    timeout=5
                )
                
                if response.status_code == 202:
                    self.processed_events.append(event_data)
                    return True
                elif response.status_code == 429:  # Rate limited
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    self.failed_events.append((event_data, response.status_code))
                    return False
                    
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                self.failed_events.append((event_data, str(e)))
                return False
        
        return False
    
    def process_batch(self, events: List[Dict[str, Any]], parallel: bool = False) -> Dict[str, Any]:
        """Process batch of events with optional parallelization."""
        results = {"success": 0, "failed": 0, "latencies": []}
        
        if parallel:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for event in events:
                    start = time.perf_counter()
                    future = executor.submit(self.process_event, event)
                    futures.append((future, start))
                
                for future, start in futures:
                    success = future.result()
                    latency = (time.perf_counter() - start) * 1000
                    results["latencies"].append(latency)
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
        else:
            for event in events:
                start = time.perf_counter()
                success = self.process_event(event)
                latency = (time.perf_counter() - start) * 1000
                results["latencies"].append(latency)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
        
        return results


@pytest.mark.e2e
@pytest.mark.slow
class TestComprehensivePipeline:
    """Comprehensive E2E pipeline tests with all components."""
    
    def test_complete_pipeline_with_performance_metrics(
        self, client: TestClient, sample_run, sample_player
    ):
        """Test complete pipeline with performance measurement."""
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Create test fixtures
        factory = EventFixtureFactory()
        events = []
        
        # Generate 100 events to test performance
        for i in range(100):
            if i % 3 == 0:  # Every third is an encounter
                events.append(factory.create_encounter(
                    run_id=str(sample_run.id),
                    player_id=str(sample_player.id)
                ))
            elif i % 3 == 1:  # Catch result for previous encounter
                if events and events[-1].type == "encounter":
                    prev = events[-1]
                    events.append(factory.create_catch_result(
                        run_id=str(sample_run.id),
                        player_id=str(sample_player.id),
                        route_id=prev.route_id,
                        species_id=prev.species_id
                    ))
            else:  # Party update or faint
                if random.random() < 0.5:
                    events.append(factory.create_party_update(
                        run_id=str(sample_run.id),
                        player_id=str(sample_player.id)
                    ))
                else:
                    events.append(factory.create_faint(
                        run_id=str(sample_run.id),
                        player_id=str(sample_player.id)
                    ))
        
        # Process events and measure latency
        with client.websocket_connect(
            f"/v1/ws/legacy?run_id={sample_run.id}&token={sample_player._test_token}"
        ) as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            for event in events:
                start_time = time.perf_counter()
                
                # Send event to API
                response = client.post(
                    "/v1/events",
                    json=event.to_dict(),
                    headers={
                        "Authorization": f"Bearer {sample_player._test_token}",
                        "Idempotency-Key": event.idempotency_key
                    }
                )
                
                if response.status_code == 202:
                    # Measure time until WebSocket receives broadcast
                    try:
                        ws_message = websocket.receive_json(timeout=1.0)
                        end_time = time.perf_counter()
                        latency_ms = (end_time - start_time) * 1000
                        metrics.record_latency(latency_ms)
                    except:
                        metrics.record_error("WebSocket timeout")
                else:
                    metrics.record_error(f"API error: {response.status_code}")
        
        metrics.stop()
        report = metrics.report()
        
        # Performance assertions
        assert report["avg_latency_ms"] < 1000, f"Average latency {report['avg_latency_ms']}ms exceeds 1s requirement"
        assert report["p95_latency_ms"] < 1500, f"P95 latency {report['p95_latency_ms']}ms too high"
        assert report["error_rate_percent"] < 5, f"Error rate {report['error_rate_percent']}% exceeds 5%"
        
        # Print performance report for debugging
        print("\nPerformance Report:")
        print(json.dumps(report, indent=2))
    
    def test_chaos_testing_with_network_failures(
        self, client: TestClient, sample_run, sample_player
    ):
        """Test pipeline resilience with chaos testing."""
        chaos = ChaosMonkey(failure_rate=0.2, delay_range=(100, 500))
        
        # Mock watcher with chaos capabilities
        watcher = MockWatcherWithChaos(
            api_url="http://testserver",
            token=sample_player._test_token,
            chaos=chaos
        )
        
        # Generate test events
        factory = EventFixtureFactory()
        events = [
            factory.create_encounter(
                run_id=str(sample_run.id),
                player_id=str(sample_player.id)
            ).to_dict()
            for _ in range(50)
        ]
        
        # Process with chaos enabled
        with chaos.chaos_mode():
            with patch('requests.post') as mock_post:
                # Configure mock to use client for actual API calls
                def side_effect(*args, **kwargs):
                    # Inject chaos
                    chaos.inject_network_error()
                    
                    # Forward to test client
                    response = client.post(
                        args[0].replace("http://testserver", ""),
                        json=kwargs.get('json'),
                        headers=kwargs.get('headers')
                    )
                    
                    # Convert TestClient response to requests.Response-like object
                    mock_response = Mock()
                    mock_response.status_code = response.status_code
                    mock_response.json.return_value = response.json() if response.status_code == 202 else {}
                    return mock_response
                
                mock_post.side_effect = side_effect
                
                # Process events with chaos
                results = watcher.process_batch(events, parallel=True)
        
        # Verify resilience
        success_rate = results["success"] / len(events) * 100
        assert success_rate >= 70, f"Success rate {success_rate}% too low with chaos testing"
        
        # Verify retry logic worked
        assert len(watcher.processed_events) > 0, "No events processed successfully"
        
        print(f"\nChaos Testing Results:")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Failed events: {results['failed']}")
        print(f"Avg latency: {sum(results['latencies']) / len(results['latencies']):.1f}ms")
    
    def test_accuracy_of_encounter_detection(
        self, client: TestClient, sample_run, sample_player
    ):
        """Test 95% accuracy requirement for encounter detection."""
        factory = EventFixtureFactory()
        
        # Generate diverse test cases
        test_cases = []
        
        # Valid encounters (should be accepted)
        for method in ["grass", "surf", "fish", "static", "gift"]:
            for _ in range(20):
                event = factory.create_encounter(
                    run_id=str(sample_run.id),
                    player_id=str(sample_player.id),
                    method=method
                )
                # Fishing encounters need rod_kind
                if method == "fish" and not event.rod_kind:
                    event.rod_kind = "old"
                test_cases.append((event, True))  # Should be accepted
        
        # Edge cases (should handle correctly)
        edge_cases = [
            # Fishing with rod_kind
            factory.create_encounter(
                run_id=str(sample_run.id),
                player_id=str(sample_player.id),
                method="fish",
                rod_kind="super"
            ),
            # Shiny encounter
            factory.create_encounter(
                run_id=str(sample_run.id),
                player_id=str(sample_player.id),
                shiny=True
            ),
            # High level encounter
            factory.create_encounter(
                run_id=str(sample_run.id),
                player_id=str(sample_player.id),
                level=100
            ),
        ]
        
        for event in edge_cases:
            test_cases.append((event, True))
        
        # Process all test cases
        correct_detections = 0
        total_cases = len(test_cases)
        
        for event, expected_valid in test_cases:
            response = client.post(
                "/v1/events",
                json=event.to_dict(),
                headers={
                    "Authorization": f"Bearer {sample_player._test_token}",
                    "Idempotency-Key": event.idempotency_key
                }
            )
            
            # Check if detection was correct
            if expected_valid:
                if response.status_code == 202:
                    correct_detections += 1
            else:
                if response.status_code != 202:
                    correct_detections += 1
        
        accuracy = (correct_detections / total_cases) * 100
        assert accuracy >= 95, f"Encounter detection accuracy {accuracy:.1f}% below 95% requirement"
        
        print(f"\nEncounter Detection Accuracy: {accuracy:.1f}%")
        print(f"Correct: {correct_detections}/{total_cases}")
    
    def test_long_session_stability(
        self, client: TestClient, sample_run, sample_player
    ):
        """Test 2+ hour session stability (simulated with accelerated testing)."""
        # Simulate 2 hours of gameplay with events every 30 seconds
        # Accelerated: 1 real second = 1 simulated minute
        simulated_duration_minutes = 120  # 2 hours
        events_per_minute = 2
        total_events = simulated_duration_minutes * events_per_minute
        
        factory = EventFixtureFactory()
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Track session health
        session_errors = []
        memory_usage = []
        event_sequences = []
        
        with client.websocket_connect(
            f"/v1/ws/legacy?run_id={sample_run.id}&token={sample_player._test_token}"
        ) as websocket:
            # Skip welcome
            websocket.receive_json()
            
            for minute in range(simulated_duration_minutes):
                # Generate events for this minute
                for _ in range(events_per_minute):
                    event = factory.create_encounter(
                        run_id=str(sample_run.id),
                        player_id=str(sample_player.id)
                    )
                    
                    # Send event
                    start = time.perf_counter()
                    response = client.post(
                        "/v1/events",
                        json=event.to_dict(),
                        headers={
                            "Authorization": f"Bearer {sample_player._test_token}",
                            "Idempotency-Key": event.idempotency_key
                        }
                    )
                    
                    if response.status_code == 202:
                        # Check WebSocket still responsive
                        try:
                            ws_msg = websocket.receive_json(timeout=2.0)
                            latency = (time.perf_counter() - start) * 1000
                            metrics.record_latency(latency)
                            
                            # Track sequence numbers for ordering
                            if "sequence_number" in ws_msg:
                                event_sequences.append(ws_msg["sequence_number"])
                        except:
                            session_errors.append(f"WebSocket timeout at minute {minute}")
                            metrics.record_error("WebSocket timeout")
                    else:
                        session_errors.append(f"API error {response.status_code} at minute {minute}")
                        metrics.record_error(f"API error: {response.status_code}")
                
                # Simulate time passing (accelerated)
                time.sleep(0.1)  # 100ms real time = 1 minute simulated
                
                # Periodic health check every 10 minutes
                if minute % 10 == 0:
                    health_response = client.get("/health")
                    if health_response.status_code != 200:
                        session_errors.append(f"Health check failed at minute {minute}")
        
        metrics.stop()
        report = metrics.report()
        
        # Stability assertions
        assert len(session_errors) < 10, f"Too many session errors: {session_errors[:10]}"
        assert report["error_rate_percent"] < 2, f"Error rate {report['error_rate_percent']}% too high for long session"
        
        # Check sequence ordering is maintained
        if event_sequences:
            sorted_sequences = sorted(event_sequences)
            assert event_sequences == sorted_sequences, "Event sequences out of order"
        
        # Performance should remain stable
        if metrics.latencies:
            first_quarter = metrics.latencies[:len(metrics.latencies)//4]
            last_quarter = metrics.latencies[-len(metrics.latencies)//4:]
            
            avg_first = sum(first_quarter) / len(first_quarter)
            avg_last = sum(last_quarter) / len(last_quarter)
            
            # Latency shouldn't degrade more than 50%
            assert avg_last < avg_first * 1.5, f"Performance degraded: {avg_first:.1f}ms → {avg_last:.1f}ms"
        
        print(f"\nLong Session Stability Test:")
        print(f"Duration: {simulated_duration_minutes} simulated minutes")
        print(f"Total events: {total_events}")
        print(f"Error rate: {report['error_rate_percent']:.2f}%")
        print(f"Avg latency: {report['avg_latency_ms']:.1f}ms")
        print(f"Session errors: {len(session_errors)}")


@pytest.mark.e2e
@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Dedicated performance benchmark tests."""
    
    def test_single_event_latency(self, client: TestClient, sample_run, sample_player):
        """Benchmark single event end-to-end latency."""
        factory = EventFixtureFactory()
        latencies = []
        
        with client.websocket_connect(
            f"/v1/ws/legacy?run_id={sample_run.id}&token={sample_player._test_token}"
        ) as websocket:
            websocket.receive_json()  # Welcome
            
            # Warm-up
            for _ in range(10):
                event = factory.create_encounter(
                    run_id=str(sample_run.id),
                    player_id=str(sample_player.id)
                )
                client.post("/v1/events", json=event.to_dict(),
                          headers={"Authorization": f"Bearer {sample_player._test_token}",
                                 "Idempotency-Key": str(uuid.uuid4())})
                websocket.receive_json(timeout=1.0)
            
            # Benchmark
            for _ in range(100):
                event = factory.create_encounter(
                    run_id=str(sample_run.id),
                    player_id=str(sample_player.id)
                )
                
                start = time.perf_counter()
                response = client.post(
                    "/v1/events",
                    json=event.to_dict(),
                    headers={
                        "Authorization": f"Bearer {sample_player._test_token}",
                        "Idempotency-Key": event.idempotency_key
                    }
                )
                
                if response.status_code == 202:
                    websocket.receive_json(timeout=2.0)
                    latency = (time.perf_counter() - start) * 1000
                    latencies.append(latency)
        
        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        p50 = sorted(latencies)[len(latencies) // 2]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"\nSingle Event Latency Benchmark:")
        print(f"Average: {avg_latency:.1f}ms")
        print(f"P50: {p50:.1f}ms")
        print(f"P95: {p95:.1f}ms")
        print(f"P99: {p99:.1f}ms")
        print(f"Min: {min(latencies):.1f}ms")
        print(f"Max: {max(latencies):.1f}ms")
        
        # Performance requirements
        assert avg_latency < 500, f"Average latency {avg_latency:.1f}ms exceeds 500ms target"
        assert p95 < 1000, f"P95 latency {p95:.1f}ms exceeds 1s requirement"
        assert p99 < 2000, f"P99 latency {p99:.1f}ms exceeds 2s threshold"
    
    def test_concurrent_player_performance(
        self, client: TestClient, sample_run, make_player
    ):
        """Test performance with multiple concurrent players."""
        # Create 3 players
        players = [make_player(sample_run.id, name=f"Player{i+1}") for i in range(3)]
        factory = EventFixtureFactory()
        
        def player_session(player, num_events: int = 50) -> Dict[str, Any]:
            """Simulate a player session."""
            latencies = []
            errors = 0
            
            with client.websocket_connect(
                f"/v1/ws/legacy?run_id={sample_run.id}&token={player._test_token}"
            ) as websocket:
                websocket.receive_json()  # Welcome
                
                for _ in range(num_events):
                    event = factory.create_encounter(
                        run_id=str(sample_run.id),
                        player_id=str(player.id)
                    )
                    
                    start = time.perf_counter()
                    response = client.post(
                        "/v1/events",
                        json=event.to_dict(),
                        headers={
                            "Authorization": f"Bearer {player._test_token}",
                            "Idempotency-Key": str(uuid.uuid4())
                        }
                    )
                    
                    if response.status_code == 202:
                        try:
                            websocket.receive_json(timeout=2.0)
                            latency = (time.perf_counter() - start) * 1000
                            latencies.append(latency)
                        except:
                            errors += 1
                    else:
                        errors += 1
            
            return {
                "player": player.name,
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "max_latency": max(latencies) if latencies else 0,
                "errors": errors,
                "success_rate": (len(latencies) / num_events) * 100
            }
        
        # Run concurrent sessions
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(player_session, player) for player in players]
            results = [f.result() for f in futures]
        
        # Analyze results
        print("\nConcurrent Player Performance:")
        for result in results:
            print(f"{result['player']}: avg={result['avg_latency']:.1f}ms, "
                  f"max={result['max_latency']:.1f}ms, "
                  f"success={result['success_rate']:.1f}%")
        
        # All players should maintain good performance
        for result in results:
            assert result['avg_latency'] < 1000, f"{result['player']} avg latency too high"
            assert result['success_rate'] > 95, f"{result['player']} success rate too low"