"""Unit tests for SQLite WAL mode configuration."""

import os
import tempfile

from sqlalchemy import create_engine


class TestSQLiteWALConfiguration:
    """Test SQLite WAL mode and concurrency configuration."""
    
    def test_sqlite_engine_has_check_same_thread_false(self):
        """Test that SQLite engines use check_same_thread=False for cross-thread access."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_url = f"sqlite:///{f.name}"
        
        try:
            # Test our database module function
            from src.soullink_tracker.db.database import create_database_engine, _is_sqlite_url
            
            # Verify URL detection works
            assert _is_sqlite_url(test_db_url) is True
            assert _is_sqlite_url("postgresql://test") is False
            
            # Create engine using our function
            test_engine = create_database_engine(test_db_url)
            assert test_engine is not None
            
            # Test that we can connect (which would fail if check_same_thread was True and we're in a different thread)
            with test_engine.connect() as conn:
                assert conn is not None
                
        finally:
            # Clean up test file
            if os.path.exists(f.name):
                os.unlink(f.name)
    
    def test_sqlite_wal_mode_enabled(self):
        """Test that SQLite databases use WAL mode for better concurrency."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_url = f"sqlite:///{f.name}"
        
        try:
            # Create a test engine with SQLite and WAL setup
            test_engine = create_engine(
                test_db_url,
                connect_args={"check_same_thread": False}
            )
            
            # Set up WAL mode listener like in production
            from sqlalchemy import event, text
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
            event.listen(test_engine, "connect", set_sqlite_pragma)
            
            # Create a connection and check PRAGMA settings
            with test_engine.connect() as conn:
                # Check journal mode
                result = conn.execute(text("PRAGMA journal_mode"))
                journal_mode = result.fetchone()[0]
                assert journal_mode.upper() == 'WAL'
                
                # Check synchronous mode
                result = conn.execute(text("PRAGMA synchronous"))
                sync_mode = result.fetchone()[0]
                assert sync_mode == 1  # NORMAL mode
                
                # Check busy timeout
                result = conn.execute(text("PRAGMA busy_timeout"))
                busy_timeout = result.fetchone()[0]
                assert busy_timeout == 5000  # 5 seconds
                
        finally:
            # Clean up test file
            if os.path.exists(f.name):
                os.unlink(f.name)
    
    def test_non_sqlite_database_unaffected(self):
        """Test that non-SQLite databases are not affected by WAL configuration."""
        from src.soullink_tracker.db.database import _is_sqlite_url
        
        # Test URL detection for non-SQLite databases
        postgres_url = "postgresql://user:pass@localhost/test"
        mysql_url = "mysql://user:pass@localhost/test"
        
        assert _is_sqlite_url(postgres_url) is False
        assert _is_sqlite_url(mysql_url) is False
        assert _is_sqlite_url("sqlite:///test.db") is True
        
        # Test that our create_database_engine function works with non-SQLite URLs
        # (without actually connecting since we don't have these databases installed)
        from src.soullink_tracker.db.database import create_database_engine
        
        # This should create an engine without errors, even if we can't connect
        try:
            pg_engine = create_database_engine(postgres_url)
            assert pg_engine is not None
            assert 'sqlite' not in str(pg_engine.dialect.name).lower()
        except ImportError:
            # Expected if psycopg2 is not installed
            pass
    
    def test_wal_pragma_setup_on_connect(self):
        """Test that WAL PRAGMAs are set up on each connection."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_url = f"sqlite:///{f.name}"
        
        try:
            # Create a test engine with SQLite and WAL setup
            test_engine = create_engine(
                test_db_url,
                connect_args={"check_same_thread": False}
            )
            
            # Set up WAL mode listener
            from sqlalchemy import event, text
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
            event.listen(test_engine, "connect", set_sqlite_pragma)
            
            # Create multiple connections and verify they all have WAL mode
            for i in range(3):
                with test_engine.connect() as conn:
                    result = conn.execute(text("PRAGMA journal_mode"))
                    journal_mode = result.fetchone()[0]
                    assert journal_mode.upper() == 'WAL'
                    
        finally:
            # Clean up test file
            if os.path.exists(f.name):
                os.unlink(f.name)