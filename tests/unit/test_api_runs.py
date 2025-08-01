"""Tests for runs API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from soullink_tracker.db.models import Run


class TestRunsAPI:
    """Test cases for runs management API endpoints."""

    def test_create_run_success(self, client: TestClient, test_db):
        """Test successful run creation."""
        run_data = {
            "name": "Test SoulLink Run",
            "rules_json": {
                "dupes_clause": True,
                "species_clause": True
            }
        }
        
        response = client.post("/v1/runs", json=run_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test SoulLink Run"
        assert data["rules_json"]["dupes_clause"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_run_invalid_name(self, client: TestClient):
        """Test run creation with invalid name."""
        run_data = {
            "name": "",  # Empty name should fail
            "rules_json": {}
        }
        
        response = client.post("/v1/runs", json=run_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_create_run_missing_fields(self, client: TestClient):
        """Test run creation with missing required fields."""
        run_data = {}  # Missing name
        
        response = client.post("/v1/runs", json=run_data)
        
        assert response.status_code == 422

    def test_get_run_success(self, client: TestClient, test_db):
        """Test successful run retrieval."""
        # First create a run
        db = test_db()
        run = Run(
            name="Test Run",
            rules_json={"test": True}
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        db.close()
        
        response = client.get(f"/v1/runs/{run.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(run.id)
        assert data["name"] == "Test Run"
        assert data["rules_json"]["test"] is True

    def test_get_run_not_found(self, client: TestClient):
        """Test run retrieval with non-existent ID."""
        fake_id = uuid4()
        
        response = client.get(f"/v1/runs/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_run_invalid_uuid(self, client: TestClient):
        """Test run retrieval with invalid UUID format."""
        response = client.get("/v1/runs/invalid-uuid")
        
        assert response.status_code == 422

    def test_list_runs_empty(self, client: TestClient):
        """Test listing runs when none exist."""
        response = client.get("/v1/runs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []

    def test_list_runs_with_data(self, client: TestClient, test_db):
        """Test listing runs when some exist."""
        # Create test runs
        db = test_db()
        run1 = Run(name="Run 1", rules_json={})
        run2 = Run(name="Run 2", rules_json={})
        db.add_all([run1, run2])
        db.commit()
        db.close()
        
        response = client.get("/v1/runs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 2
        run_names = [run["name"] for run in data["runs"]]
        assert "Run 1" in run_names
        assert "Run 2" in run_names

    def test_create_run_content_type_validation(self, client: TestClient):
        """Test that POST /v1/runs requires JSON content type."""
        response = client.post(
            "/v1/runs",
            data="name=test",  # Form data instead of JSON
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 422

    def test_run_response_format(self, client: TestClient, test_db):
        """Test that run response has correct format and fields."""
        run_data = {
            "name": "Format Test Run",
            "rules_json": {"test_rule": "test_value"}
        }
        
        response = client.post("/v1/runs", json=run_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Check required fields are present
        required_fields = ["id", "name", "rules_json", "created_at"]
        for field in required_fields:
            assert field in data
        
        # Check field types
        assert isinstance(data["name"], str)
        assert isinstance(data["rules_json"], dict)
        assert isinstance(data["created_at"], str)
        
        # Validate UUID format
        from uuid import UUID
        UUID(data["id"])  # Should not raise exception

    def test_run_rules_json_persistence(self, client: TestClient, test_db):
        """Test that complex rules_json is properly persisted and retrieved."""
        complex_rules = {
            "dupes_clause": True,
            "species_clause": True,
            "fishing_enabled": False,
            "custom_routes": [1, 2, 3],
            "nested": {
                "level": 2,
                "items": ["item1", "item2"]
            }
        }
        
        run_data = {
            "name": "Complex Rules Run",
            "rules_json": complex_rules
        }
        
        # Create run
        response = client.post("/v1/runs", json=run_data)
        assert response.status_code == 201
        run_id = response.json()["id"]
        
        # Retrieve run
        response = client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200
        
        retrieved_rules = response.json()["rules_json"]
        assert retrieved_rules == complex_rules