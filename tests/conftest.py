"""Pytest configuration and shared fixtures."""

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_db():
    """Create a test database."""
    # Import here to avoid circular imports
    from soullink_tracker.db.database import Base, get_database_url
    
    # Create test database
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    yield TestingSessionLocal
    
    # Clean up
    Base.metadata.drop_all(bind=engine)
    
    # Remove test database file
    test_db_path = Path("test.db")
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.fixture
def client(test_db) -> Generator[TestClient, None, None]:
    """Create a test client."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db
    
    def override_get_db():
        try:
            db = test_db()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db
    
    def override_get_db():
        try:
            db = test_db()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

# Playwright fixtures are automatically provided by pytest-playwright
# No need to define page, browser_context, etc.

@pytest.fixture(scope="session")
def setup_test_env():
    """Set up test environment variables."""
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    yield
    os.environ.pop("TESTING", None)
    os.environ.pop("DATABASE_URL", None)

# Markers for test organization
pytestmark = pytest.mark.asyncio