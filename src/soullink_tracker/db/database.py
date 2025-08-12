"""Database configuration and setup."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional


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


def create_database_engine(database_url: Optional[str] = None):
    """Create database engine with appropriate configuration."""
    if database_url is None:
        # Database URL priority: SOULLINK_DATABASE_URL > TEST_DATABASE_URL > DATABASE_URL > default
        database_url = (
            os.getenv("SOULLINK_DATABASE_URL")
            or os.getenv("TEST_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "sqlite:///./soullink_tracker.db"
        )

    # Create engine with appropriate configuration
    if _is_sqlite_url(database_url):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
        )

        # Enable WAL mode and other SQLite optimizations
        event.listen(engine, "connect", _setup_sqlite_pragma)
    else:
        engine = create_engine(
            database_url, echo=os.getenv("SQL_DEBUG", "false").lower() == "true"
        )

    return engine


# Database URL - support test override, then fall back to config or default
DATABASE_URL = (
    os.getenv("SOULLINK_DATABASE_URL")
    or os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "sqlite:///./soullink_tracker.db"
)

# Create default engine
engine = create_database_engine(DATABASE_URL)

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
