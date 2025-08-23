"""Database configuration and setup."""

import os
import logging
import time
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from typing import Optional

# Query performance logger
query_logger = logging.getLogger("sqlalchemy.query_performance")


def _is_sqlite_url(url: str) -> bool:
    """Check if database URL is for SQLite."""
    return url.startswith("sqlite:")


def _setup_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance and concurrency."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5 second timeout for concurrent access
    cursor.execute("PRAGMA cache_size=1000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


def _setup_query_logging(engine: Engine, enable_query_logging: bool = False):
    """Set up query performance logging if enabled."""
    if not enable_query_logging:
        return

    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        total = time.time() - context._query_start_time

        # Log slow queries (>100ms) as warnings, others as debug
        if total > 0.1:
            query_logger.warning(
                f"Slow query ({total:.3f}s): {statement[:200]}{'...' if len(statement) > 200 else ''}"
            )
        else:
            query_logger.debug(
                f"Query ({total:.3f}s): {statement[:100]}{'...' if len(statement) > 100 else ''}"
            )


def create_database_engine(
    database_url: Optional[str] = None, enable_query_logging: bool = False
):
    """Create database engine with appropriate configuration."""
    if database_url is None:
        # Database URL priority: SOULLINK_DATABASE_URL > TEST_DATABASE_URL > DATABASE_URL > default
        database_url = (
            os.getenv("SOULLINK_DATABASE_URL")
            or os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "sqlite:///./soullink_tracker.db"
        )

    # Check for SQL debugging from environment or parameter
    sql_debug = os.getenv("SQL_DEBUG", "false").lower() == "true"

    # Create engine with appropriate configuration
    if _is_sqlite_url(database_url):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=sql_debug,
        )

        # Enable WAL mode and other SQLite optimizations
        event.listen(engine, "connect", _setup_sqlite_pragma)
    else:
        engine = create_engine(database_url, echo=sql_debug)

    # Set up query performance logging if enabled
    _setup_query_logging(engine, enable_query_logging)

    return engine


# Database URL - support test override, then fall back to config or default
DATABASE_URL = (
    os.getenv("SOULLINK_DATABASE_URL")
    or os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "sqlite:///./soullink_tracker.db"
)


# Create default engine with query logging based on development mode
def _get_enable_query_logging() -> bool:
    """Check if query logging should be enabled."""
    try:
        from ..config import get_config

        config = get_config()
        return config.database.log_queries or config.app.is_development
    except ImportError:
        # Fallback to environment variable if config is not available
        return os.getenv("SOULLINK_LOG_QUERIES", "false").lower() == "true"


engine = create_database_engine(
    DATABASE_URL, enable_query_logging=_get_enable_query_logging()
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_url() -> str:
    """Get the current database URL."""
    return DATABASE_URL
