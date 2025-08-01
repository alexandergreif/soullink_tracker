"""Basic end-to-end tests for the SoulLink tracker."""

import pytest
from playwright.async_api import Page, expect

@pytest.mark.e2e
async def test_homepage_loads(page: Page):
    """Test that the homepage loads successfully."""
    await page.goto("/")
    
    # Check that we get some content (this will fail until we implement the UI)
    await expect(page).to_have_title("SoulLink Tracker")

@pytest.mark.e2e  
async def test_api_health_check(page: Page):
    """Test that the API health endpoint responds."""
    response = await page.request.get("/health")
    assert response.status == 200
    
    json_response = await response.json()
    assert json_response["status"] == "healthy"

@pytest.mark.e2e
@pytest.mark.slow
async def test_websocket_connection(websocket_page: Page):
    """Test WebSocket connection establishment."""
    # This test will be implemented once we have WebSocket endpoints
    await websocket_page.goto("/")
    
    # Add WebSocket connection test logic here
    # For now, just ensure we can load the page
    await expect(websocket_page.locator("body")).to_be_visible()