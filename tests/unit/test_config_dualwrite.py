"""Unit tests for dual-write config and DB URL override."""

import os
from unittest.mock import patch
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.soullink_tracker.config import ConfigManager, AppConfig


class TestConfigDualWrite:
    """Test dual-write feature flag configuration."""
    
    def test_app_config_has_dual_write_flag(self):
        """Test that AppConfig includes feature_v3_dualwrite flag."""
        config = AppConfig()
        assert hasattr(config, 'feature_v3_dualwrite')
        assert config.feature_v3_dualwrite is False  # Default disabled
    
    def test_detect_environment_reads_dual_write_env_var(self):
        """Test that detect_environment reads FEATURE_V3_DUALWRITE env var."""
        with patch.dict(os.environ, {'FEATURE_V3_DUALWRITE': '1'}):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_dualwrite'] is True
        
        with patch.dict(os.environ, {'FEATURE_V3_DUALWRITE': '0'}):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_dualwrite'] is False
        
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_dualwrite'] is False
    
    def test_create_default_config_honors_db_url_override(self):
        """Test that create_default_config uses SOULLINK_DATABASE_URL if set."""
        test_db_url = "sqlite:///test_integration.db"
        
        with patch.dict(os.environ, {'SOULLINK_DATABASE_URL': test_db_url}):
            manager = ConfigManager()
            config = manager.create_default_config()
            assert config.database.url == test_db_url
    
    def test_load_config_honors_db_url_override(self):
        """Test that load_config overrides database URL from env var."""
        test_db_url = "sqlite:///test_integration.db"
        
        # Create a temporary config file
        config_data = {
            "app": {"app_name": "Test"},
            "server": {"port": 9000},
            "database": {"url": "sqlite:///original.db"}
        }
        
        with NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(config_data, f)
            config_file = Path(f.name)
        
        try:
            with patch.dict(os.environ, {'SOULLINK_DATABASE_URL': test_db_url}):
                manager = ConfigManager()
                # Mock the config file path to use our temp file
                manager.config_file = config_file
                config = manager.load_config()
                assert config.database.url == test_db_url
        finally:
            config_file.unlink()
    
    def test_default_config_without_db_override(self):
        """Test that default config uses standard DB URL without override."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager()
            config = manager.create_default_config()
            assert config.database.url == "sqlite:///soullink_tracker.db"