"""Playwright-specific configuration for e2e tests."""

import pytest
from playwright.async_api import Page, BrowserContext

@pytest.fixture
async def authenticated_page(page: Page) -> Page:
    """Create a page with authentication setup."""
    # Set up any authentication headers or tokens needed
    await page.set_extra_http_headers({
        "Authorization": "Bearer test-token"
    })
    return page

@pytest.fixture  
async def admin_page(page: Page) -> Page:
    """Create a page with admin authentication."""
    await page.set_extra_http_headers({
        "Authorization": "Bearer admin-test-token"
    })
    return page

@pytest.fixture
async def websocket_page(page: Page) -> Page:
    """Create a page ready for WebSocket testing."""
    # Enable console logging for WebSocket debugging
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.on("pageerror", lambda err: print(f"Page Error: {err}"))
    return page