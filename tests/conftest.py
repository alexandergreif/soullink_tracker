"""Pytest configuration and shared fixtures."""

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional, Callable, Dict, Any, Tuple
import csv
import logging
import importlib
from contextlib import contextmanager, asynccontextmanager

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config

# Added imports for integration helpers

# Register scenario markers for test selection/documentation
def pytest_configure(config):
    config.addinivalue_line("markers", "v2_only: Run test with V2-only configuration")
    config.addinivalue_line("markers", "v3_only: Run test with V3-only configuration")
    # V3-only architecture - no dual-write marker needed

# Global test state
_test_db_url: Optional[str] = None

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_db(setup_test_env):
    """Create a test database session factory with migrations applied."""
    global _test_db_url

    # Create engine using the migrated database
    engine = create_engine(
        _test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield TestingSessionLocal

    # No cleanup needed - handled by session fixture

@pytest.fixture
def db_session(test_db):
    """Create a database session with automatic rollback for test isolation."""
    session = test_db()
    
    yield session
    
    session.close()

@pytest.fixture
def client(test_db) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db

    def override_get_db():
        # Use a fresh session per request in tests
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clear overrides to avoid affecting other tests
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database dependency override."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db

    def override_get_db():
        # Use a fresh session per request in tests
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    # Clear overrides to avoid affecting other tests
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def setup_test_env():
    """Set up test environment variables and database with migrations."""
    global _test_db_url

    # Determine database URL: prefer override if supplied, otherwise temp SQLite
    external_db_url = os.environ.get("SOULLINK_DATABASE_URL") or os.environ.get("DATABASE_URL")
    temp_db = None
    if external_db_url:
        db_url = external_db_url
    else:
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"

    _test_db_url = db_url

    # Set environment variables (store originals for restoration)
    original_env: Dict[str, Optional[str]] = {}
    env_vars = {
        "TESTING": "1",
        "DATABASE_URL": db_url,
        "TEST_DATABASE_URL": db_url,
        "SOULLINK_DB_URL": db_url,         # For Alembic scripts
        "SOULLINK_DATABASE_URL": db_url,   # For integration override compatibility
        # V3 event store is always enabled in v3-only architecture
        "FEATURE_V3_EVENTSTORE": "1",
    }
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Run Alembic migrations to get proper schema with constraints
        _run_alembic_migrations(db_url)

        # Populate reference data (species, routes) from CSVs if present
        try:
            _populate_reference_data(db_url)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Reference data load skipped or failed: {e}")

        yield db_url
    finally:
        # Restore environment
        for key, original_value in original_env.items():
            if original_value is not None:
                os.environ[key] = original_value
            else:
                os.environ.pop(key, None)

        # Clean up temp database only if we created it
        if temp_db is not None:
            try:
                Path(temp_db.name).unlink(missing_ok=True)
            except Exception:
                pass  # Ignore cleanup errors

def _run_alembic_migrations(db_url: str):
    """Run Alembic migrations programmatically for test database."""
    # Create Alembic config
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', 'alembic')
    alembic_cfg.set_main_option('sqlalchemy.url', db_url)

    # Run migrations
    command.upgrade(alembic_cfg, 'head')

def _project_root() -> Path:
    """Return the repository root path."""
    return Path(__file__).resolve().parents[1]

def _populate_reference_data(db_url: str) -> None:
    """Load reference data from CSV files into the database (best-effort)."""
    engine_kwargs: Dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(db_url, **engine_kwargs)

    routes_csv = _project_root() / "data" / "routes.csv"
    species_csv = _project_root() / "data" / "species.csv"

    with engine.begin() as conn:
        insp = inspect(conn)

        if routes_csv.exists() and "routes" in insp.get_table_names():
            _load_csv_into_table(conn, "routes", routes_csv)
        if species_csv.exists() and "species" in insp.get_table_names():
            _load_csv_into_table(conn, "species", species_csv)

def _load_csv_into_table(conn, table_name: str, csv_path: Path) -> None:
    """Load a CSV file into the given table using header-based column mapping."""
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return

        # Normalize column names and build query
        columns = [c.strip() for c in reader.fieldnames]
        placeholders = ", ".join([f":{c}" for c in columns])
        col_names = ", ".join([f'"{c}"' for c in columns])

        dialect = conn.engine.dialect.name
        if dialect == "sqlite":
            insert_sql = f'INSERT OR IGNORE INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
        elif dialect == "postgresql":
            insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        else:
            insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

        for row in reader:
            try:
                conn.execute(text(insert_sql), row)
            except Exception:
                # Ignore per-row failures so tests remain robust across schema variations
                continue

def _get_fresh_app_and_deps() -> Tuple[Any, Callable, Callable]:
    """
    Reload config, DB, auth, and main modules to get a fresh FastAPI app and fresh dependencies
    after feature flag environment changes.
    Returns (app, get_db, get_current_player).
    """
    import soullink_tracker.config as cfg
    import soullink_tracker.db.database as db_module
    import soullink_tracker.auth.dependencies as auth_deps
    import soullink_tracker.main as main_module

    importlib.reload(cfg)
    importlib.reload(db_module)
    importlib.reload(auth_deps)
    importlib.reload(main_module)

    return main_module.app, db_module.get_db, auth_deps.get_current_player

@contextmanager
def _client_context_for_v3_only(test_db):
    """Context manager yielding a TestClient with v3-only configuration."""
    old_eventstore = os.environ.get("FEATURE_V3_EVENTSTORE")

    os.environ["FEATURE_V3_EVENTSTORE"] = "1"  # Always enabled in v3-only

    app, get_db, _ = _get_fresh_app_and_deps()

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client_instance:
            yield client_instance
    finally:
        app.dependency_overrides.clear()
        if old_eventstore is not None:
            os.environ["FEATURE_V3_EVENTSTORE"] = old_eventstore
        else:
            os.environ.pop("FEATURE_V3_EVENTSTORE", None)

@asynccontextmanager
async def _async_client_context_for_v3_only(test_db):
    """Async context manager yielding an AsyncClient with v3-only configuration."""
    old_eventstore = os.environ.get("FEATURE_V3_EVENTSTORE")

    os.environ["FEATURE_V3_EVENTSTORE"] = "1"  # Always enabled in v3-only

    app, get_db, _ = _get_fresh_app_and_deps()

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        if old_eventstore is not None:
            os.environ["FEATURE_V3_EVENTSTORE"] = old_eventstore
        else:
            os.environ.pop("FEATURE_V3_EVENTSTORE", None)

@asynccontextmanager
async def _async_client_context_for_feature_flags(test_db, feature_v3_eventstore: int, feature_v3_dualwrite: int):
    """Async context manager yielding an AsyncClient with given feature flags applied."""
    old_eventstore = os.environ.get("FEATURE_V3_EVENTSTORE")
    old_dualwrite = os.environ.get("FEATURE_V3_DUALWRITE")

    os.environ["FEATURE_V3_EVENTSTORE"] = "1" if feature_v3_eventstore else "0"
    os.environ["FEATURE_V3_DUALWRITE"] = "1" if feature_v3_dualwrite else "0"

    app, get_db, _ = _get_fresh_app_and_deps()

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        if old_eventstore is not None:
            os.environ["FEATURE_V3_EVENTSTORE"] = old_eventstore
        else:
            os.environ.pop("FEATURE_V3_EVENTSTORE", None)
        if old_dualwrite is not None:
            os.environ["FEATURE_V3_DUALWRITE"] = old_dualwrite
        else:
            os.environ.pop("FEATURE_V3_DUALWRITE", None)

# V3-only architecture - legacy fixtures removed
# Use the default 'client' fixture which uses v3-only configuration

# V3-only async clients - use default 'async_client' fixture

# Test data fixtures for creating runs, players, etc.

@pytest.fixture
def sample_run(db_session):
    """Create a sample run for testing."""
    from soullink_tracker.db.models import Run

    run = Run(
        name="Test SoulLink Run",
        rules_json={"dupe_clause": True, "first_encounter_only": True}
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run

@pytest.fixture
def sample_player(db_session, sample_run):
    """Create a sample player for testing."""
    from soullink_tracker.db.models import Player

    # Generate a secure token
    token, token_hash = Player.generate_token()

    player = Player(
        run_id=sample_run.id,
        name="TestPlayer",
        game="HeartGold",
        region="EU",
        token_hash=token_hash
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)

    # Store the plain token for tests to use
    player._test_token = token
    return player

@pytest.fixture
def auth_headers(sample_player):
    """Create authentication headers for testing."""
    return {
        "Authorization": f"Bearer {sample_player._test_token}",
        "Content-Type": "application/json"
    }

@pytest.fixture
def sample_data(sample_run, sample_player):
    """Create sample test data structure."""
    return {
        "runs": [sample_run],
        "players": [sample_player]
    }

# Factory helpers to create runs/players and headers on demand
@pytest.fixture
def make_run(db_session):
    """Factory to create a run with optional name/rules."""
    from soullink_tracker.db.models import Run
    def _maker(name: str = "Integration Run", rules_json: Optional[Dict[str, Any]] = None):
        run = Run(
            name=name,
            rules_json=rules_json or {"dupe_clause": True, "first_encounter_only": True},
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        return run
    return _maker

@pytest.fixture
def make_player(db_session):
    """Factory to create a player and return the instance with a plain token attached at _test_token."""
    from soullink_tracker.db.models import Player
    def _maker(run_id: uuid.UUID, name: str = "Player1", game: str = "HeartGold", region: str = "EU"):
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run_id,
            name=name,
            game=game,
            region=region,
            token_hash=token_hash
        )
        db_session.add(player)
        db_session.commit()
        db_session.refresh(player)
        player._test_token = token
        return player
    return _maker

@pytest.fixture
def auth_headers_for():
    """Return a function that builds auth headers for a given player with _test_token."""
    def _headers(player) -> Dict[str, str]:
        token = getattr(player, "_test_token", None)
        if not token:
            # Best-effort: generate a token header if missing (won't update DB)
            token = "invalid"
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return _headers

# WebSocket helpers using the existing clients
@pytest.fixture
def ws(client):
    """Return a function to open a websocket using the default client."""
    def _ws(path: str, headers: Optional[Dict[str, str]] = None):
        headers_list = list(headers.items()) if headers else None
        return client.websocket_connect(path, headers=headers_list)
    return _ws

@pytest.fixture
def auth_ws(auth_client, auth_headers):
    """Return a function to open an authenticated websocket using the auth_client."""
    def _ws(path: str):
        headers_list = list(auth_headers.items())
        return auth_client.websocket_connect(path, headers=headers_list)
    return _ws

# Autouse cleanup: wipe non-reference tables after each test to keep tests isolated
@pytest.fixture(autouse=True)
def db_cleanup(test_db):
    """Clean up database tables between tests, preserving reference and migration tables."""
    session = test_db()
    try:
        yield
    finally:
        engine = session.get_bind()
        dialect = engine.dialect.name
        inspector = inspect(engine)
        # Preserve alembic_version and reference data tables
        exclude_tables = {"alembic_version", "routes", "species"}
        table_names = [t for t in inspector.get_table_names() if t not in exclude_tables]

        try:
            if dialect == "sqlite":
                session.execute(text("PRAGMA foreign_keys=OFF"))
            for table in table_names:
                session.execute(text(f'DELETE FROM "{table}"'))
            session.commit()
        finally:
            if dialect == "sqlite":
                session.execute(text("PRAGMA foreign_keys=ON"))
            session.close()

@pytest.fixture
def auth_client(test_db, sample_player):
    """Create a test client with authentication override."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db
    from soullink_tracker.auth.dependencies import get_current_player

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_player():
        return sample_player

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_player] = override_get_current_player

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture
def auth_client_v2(test_db, sample_player):
    """Authenticated TestClient for V2-only scenario."""
    with _client_context_for_v3_only(test_db) as c:
        _, _, get_current_player = _get_fresh_app_and_deps()
        from soullink_tracker.main import app as fresh_app
        fresh_app.dependency_overrides[get_current_player] = lambda: sample_player
        try:
            yield c
        finally:
            fresh_app.dependency_overrides.clear()

@pytest.fixture
def auth_client_v3(test_db, sample_player):
    """Authenticated TestClient for V3-only scenario."""
    with _client_context_for_v3_only(test_db) as c:
        _, _, get_current_player = _get_fresh_app_and_deps()
        from soullink_tracker.main import app as fresh_app
        fresh_app.dependency_overrides[get_current_player] = lambda: sample_player
        try:
            yield c
        finally:
            fresh_app.dependency_overrides.clear()

@pytest.fixture
def client_v2_only(test_db):
    """TestClient for V2-only scenario (no event store)."""
    with _client_context_for_v3_only(test_db) as c:
        yield c

@pytest.fixture
def client_v3_only(test_db):
    """TestClient for V3-only scenario (event store enabled)."""
    with _client_context_for_v3_only(test_db) as c:
        yield c

@pytest.fixture
def client_dualwrite(test_db):
    """TestClient for dual-write scenario (V2 + V3 parallel)."""
    with _client_context_for_v3_only(test_db) as c:
        yield c

@pytest.fixture
def client_v3_eventstore(test_db):
    """TestClient with v3 event store enabled."""
    with _client_context_for_v3_only(test_db) as c:
        yield c

# auth_client_dualwrite removed - use auth_client_v3 or default auth_client

@pytest_asyncio.fixture
async def auth_async_client(test_db, sample_player):
    """Create an async test client with authentication override."""
    from soullink_tracker.main import app
    from soullink_tracker.db.database import get_db
    from soullink_tracker.auth.dependencies import get_current_player

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_player():
        return sample_player

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_player] = override_get_current_player

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_async_client_v2(test_db, sample_player):
    """Authenticated AsyncClient for V2-only scenario."""
    async with _async_client_context_for_v3_only(test_db) as ac:
        _, _, get_current_player = _get_fresh_app_and_deps()
        from soullink_tracker.main import app as fresh_app
        fresh_app.dependency_overrides[get_current_player] = lambda: sample_player
        try:
            yield ac
        finally:
            fresh_app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_async_client_v3(test_db, sample_player):
    """Authenticated AsyncClient for V3-only scenario."""
    async with _async_client_context_for_v3_only(test_db) as ac:
        _, _, get_current_player = _get_fresh_app_and_deps()
        from soullink_tracker.main import app as fresh_app
        fresh_app.dependency_overrides[get_current_player] = lambda: sample_player
        try:
            yield ac
        finally:
            fresh_app.dependency_overrides.clear()

# auth_async_client_dualwrite removed - use auth_async_client_v3 or default

# Markers for test organization
pytestmark = pytest.mark.asyncio


# Concurrency testing fixtures
@pytest.fixture
def session_factory(engine):
    """Factory for creating new SQLAlchemy sessions for multi-threaded tests.
    
    Returns:
        Callable that creates new Session instances bound to the same engine
    """
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return lambda: SessionLocal()


@pytest.fixture
def barrier_factory():
    """Factory for creating threading barriers for synchronizing concurrent tests.
    
    Returns:
        Callable that creates threading.Barrier for N threads
    """
    from threading import Barrier
    return lambda n: Barrier(n)