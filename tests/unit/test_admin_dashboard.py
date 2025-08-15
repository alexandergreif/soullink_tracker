"""Tests for admin dashboard endpoints and functionality."""

import pytest
from fastapi import status
from unittest.mock import patch, MagicMock

from src.soullink_tracker.db.models import Run, Player


class TestAdminHealthEndpoints:
    """Test health and ready endpoints for admin monitoring."""

    def test_health_endpoint_returns_healthy_status(self, client):
        """Test that /health returns healthy status with version info."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "soullink-tracker"
        assert "version" in data

    def test_ready_endpoint_with_healthy_dependencies(self, client):
        """Test that /ready returns ready status when all checks pass."""
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "soullink-tracker"
        assert "checks" in data
        assert data["checks"]["database"] is True
        assert data["checks"]["config"] is True
        assert "response_time_ms" in data

    @patch('src.soullink_tracker.main.get_db')
    def test_ready_endpoint_with_database_failure(self, mock_get_db, client):
        """Test that /ready returns not_ready status when database check fails."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_get_db.return_value = iter([mock_db])
        
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is False
        assert "errors" in data
        assert any("Database check failed" in error for error in data["errors"])

    @patch('src.soullink_tracker.main.get_config')
    def test_ready_endpoint_with_config_failure(self, mock_get_config, client):
        """Test that /ready returns not_ready status when config check fails."""
        mock_get_config.side_effect = Exception("Config loading failed")
        
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["config"] is False
        assert "errors" in data
        assert any("Config check failed" in error for error in data["errors"])


class TestAdminRebuildProjections:
    """Test projection rebuild functionality."""

    def test_rebuild_projections_requires_localhost(self, client):
        """Test that rebuild projections endpoint requires localhost access."""
        # Mock a non-localhost request
        with patch('src.soullink_tracker.api.admin.require_localhost') as mock_localhost:
            mock_localhost.side_effect = Exception("Admin API only available on localhost")
            
            response = client.post("/v1/admin/runs/00000000-0000-0000-0000-000000000001/rebuild-projections")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_rebuild_projections_requires_v3_eventstore(self, client_v2_only, sample_data):
        """Test that rebuild projections requires v3 event store to be enabled."""
        run = sample_data["runs"][0]
        
        # Mock localhost check to pass
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v2_only.post(f"/v1/admin/runs/{run.id}/rebuild-projections")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert "v3 event store is not enabled" in data["detail"]

    def test_rebuild_projections_run_not_found(self, client_v3_eventstore):
        """Test rebuild projections with non-existent run."""
        fake_run_id = "00000000-0000-0000-0000-000000000000"
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v3_eventstore.post(f"/v1/admin/runs/{fake_run_id}/rebuild-projections")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "Run not found" in data["detail"]

    def test_rebuild_projections_success(self, client_v3_eventstore, sample_data):
        """Test successful projection rebuild."""
        run = sample_data["runs"][0]
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v3_eventstore.post(f"/v1/admin/runs/{run.id}/rebuild-projections")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert "success" in data["status"]
            assert "events_processed" in data
            assert "projections_rebuilt" in data


class TestAdminRunManagement:
    """Test admin run management endpoints."""

    def test_list_runs_requires_localhost(self, client):
        """Test that list runs endpoint requires localhost access."""
        with patch('src.soullink_tracker.api.admin.require_localhost') as mock_localhost:
            mock_localhost.side_effect = Exception("Admin API only available on localhost")
            
            response = client.get("/v1/admin/runs")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_list_runs_success(self, client, sample_data):
        """Test successful run listing."""
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client.get("/v1/admin/runs")
            
            assert response.status_code == status.HTTP_200_OK
            runs = response.json()
            assert len(runs) >= 1
            assert all("id" in run and "name" in run for run in runs)

    def test_create_run_requires_localhost(self, client):
        """Test that create run endpoint requires localhost access."""
        run_data = {"name": "Test Run", "rules_json": {}}
        
        with patch('src.soullink_tracker.api.admin.require_localhost') as mock_localhost:
            mock_localhost.side_effect = Exception("Admin API only available on localhost")
            
            response = client.post("/v1/admin/runs", json=run_data)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_create_run_success(self, client):
        """Test successful run creation."""
        run_data = {"name": "New Test Run", "rules_json": {"max_players": 3}}
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client.post("/v1/admin/runs", json=run_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == run_data["name"]
            assert data["rules_json"] == run_data["rules_json"]
            assert "id" in data


class TestAdminPlayerManagement:
    """Test admin player management endpoints."""

    def test_create_player_requires_localhost(self, client, sample_data):
        """Test that create player endpoint requires localhost access."""
        run = sample_data["runs"][0]
        player_data = {"name": "Test Player", "game": "HeartGold", "region": "EU"}
        
        with patch('src.soullink_tracker.api.admin.require_localhost') as mock_localhost:
            mock_localhost.side_effect = Exception("Admin API only available on localhost")
            
            response = client.post(f"/v1/admin/runs/{run.id}/players", json=player_data)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_create_player_success(self, client, sample_data):
        """Test successful player creation with token generation."""
        run = sample_data["runs"][0]
        player_data = {"name": "New Test Player", "game": "SoulSilver", "region": "US"}
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client.post(f"/v1/admin/runs/{run.id}/players", json=player_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == player_data["name"]
            assert data["game"] == player_data["game"]
            assert data["region"] == player_data["region"]
            assert "new_token" in data  # One-time token display
            assert "id" in data

    def test_create_player_run_not_found(self, client):
        """Test create player with non-existent run."""
        fake_run_id = "00000000-0000-0000-0000-000000000000"
        player_data = {"name": "Test Player", "game": "HeartGold", "region": "EU"}
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client.post(f"/v1/admin/runs/{fake_run_id}/players", json=player_data)
            
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_player_duplicate_name(self, client, sample_data):
        """Test create player with duplicate name in same run."""
        run = sample_data["runs"][0]
        existing_player = sample_data["players"][0]  # Assumes first player belongs to first run
        player_data = {"name": existing_player.name, "game": "HeartGold", "region": "EU"}
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client.post(f"/v1/admin/runs/{run.id}/players", json=player_data)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAdminEventStoreManagement:
    """Test admin event store management endpoints."""

    def test_get_events_requires_v3_eventstore(self, client_v2_only, sample_data):
        """Test that get events endpoint requires v3 event store."""
        run = sample_data["runs"][0]
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v2_only.get(f"/v1/admin/runs/{run.id}/events")
            
            assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
            data = response.json()
            assert "v3 Event Store is not enabled" in data["detail"]

    def test_get_events_success(self, client_v3_eventstore, sample_data):
        """Test successful event retrieval from event store."""
        run = sample_data["runs"][0]
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v3_eventstore.get(f"/v1/admin/runs/{run.id}/events")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "events" in data
            assert "total" in data
            assert "latest_seq" in data

    def test_get_events_with_pagination(self, client_v3_eventstore, sample_data):
        """Test event retrieval with pagination parameters."""
        run = sample_data["runs"][0]
        
        with patch('src.soullink_tracker.api.admin.require_localhost', return_value=True):
            response = client_v3_eventstore.get(
                f"/v1/admin/runs/{run.id}/events?limit=10&since_seq=0"
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["events"]) <= 10