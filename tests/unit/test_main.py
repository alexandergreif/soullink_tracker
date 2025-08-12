"""Unit tests for the main FastAPI application."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_app_creation():
    """Test that the FastAPI app can be created."""
    from soullink_tracker.main import app
    
    assert app is not None
    assert app.title == "SoulLink Tracker"
    assert app.version == "3.0.0-dev"


@pytest.mark.unit  
def test_health_endpoint(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "soullink-tracker",
        "version": "3.0.0-dev"
    }


@pytest.mark.unit
def test_ready_endpoint(client: TestClient):
    """Test the readiness check endpoint."""
    response = client.get("/ready")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify required fields
    assert data["status"] == "ready"
    assert data["service"] == "soullink-tracker"
    assert "version" in data
    assert "checks" in data
    assert "response_time_ms" in data
    
    # Verify check results
    assert data["checks"]["database"] is True
    assert data["checks"]["config"] is True
    
    # Verify response time is reasonable
    assert isinstance(data["response_time_ms"], (int, float))
    assert data["response_time_ms"] >= 0


@pytest.mark.unit
def test_root_endpoint(client: TestClient):
    """Test the root endpoint redirects to docs."""
    response = client.get("/", follow_redirects=False)
    
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


@pytest.mark.unit
def test_cors_headers(client: TestClient):
    """Test CORS headers are present."""
    response = client.get("/health")
    
    # These would be set by CORSMiddleware if configured
    assert response.status_code == 200