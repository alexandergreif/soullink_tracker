"""Unit tests for v3-only configuration (no legacy v2 support)."""

import os
from unittest.mock import patch
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.soullink_tracker.config import ConfigManager, AppConfig


class TestConfigV3Only:
    """Test v3-only configuration without dual-write or legacy v2 support."""
    
    def test_app_config_defaults_to_v3_only(self):
        """Test that AppConfig defaults to v3 event store enabled with no legacy flags."""
        config = AppConfig()
        
        # v3 should be enabled by default
        assert hasattr(config, 'feature_v3_eventstore')
        assert config.feature_v3_eventstore is True
        
        # No dual-write or legacy flags should exist
        assert not hasattr(config, 'feature_v3_dualwrite')
        assert not hasattr(config, 'feature_v2_legacy')
    
    def test_detect_environment_v3_always_enabled(self):
        """Test that detect_environment always enables v3, ignoring legacy env vars."""
        # Even if someone tries to disable v3, it should be forced on
        with patch.dict(os.environ, {'FEATURE_V3_EVENTSTORE': '0'}):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_eventstore'] is True
        
        # Standard case - v3 enabled
        with patch.dict(os.environ, {'FEATURE_V3_EVENTSTORE': '1'}):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_eventstore'] is True
        
        # No env var - should default to v3 enabled
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            assert env_info['feature_v3_eventstore'] is True
    
    def test_detect_environment_ignores_legacy_flags(self):
        """Test that legacy v2/dual-write env vars are ignored."""
        legacy_env_vars = {
            'FEATURE_V3_DUALWRITE': '1',
            'FEATURE_V2_LEGACY': '1',
            'ENABLE_LEGACY_MODE': '1'
        }
        
        with patch.dict(os.environ, legacy_env_vars):
            manager = ConfigManager()
            env_info = manager.detect_environment()
            
            # Only v3 should be present and enabled
            assert env_info['feature_v3_eventstore'] is True
            assert 'feature_v3_dualwrite' not in env_info
            assert 'feature_v2_legacy' not in env_info
            assert 'enable_legacy_mode' not in env_info
    
    def test_create_default_config_is_v3_only(self):
        """Test that create_default_config produces v3-only configuration."""
        manager = ConfigManager()
        config = manager.create_default_config()
        
        # v3 should be enabled
        assert config.app.feature_v3_eventstore is True
        
        # No legacy configuration should exist
        assert not hasattr(config.app, 'feature_v3_dualwrite')
        assert not hasattr(config.app, 'feature_v2_legacy')
    
    def test_load_config_forces_v3_even_if_disabled_in_file(self):
        """Test that load_config forces v3 enabled even if config file tries to disable it."""
        # Create a config file that tries to disable v3
        config_data = {
            "app": {
                "app_name": "Test",
                "feature_v3_eventstore": False,  # Try to disable v3
                "feature_v3_dualwrite": True,    # Legacy flag that should be ignored
            },
            "server": {"port": 9000},
            "database": {"url": "sqlite:///test.db"}
        }
        
        with NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(config_data, f)
            config_file = Path(f.name)
        
        try:
            manager = ConfigManager()
            manager.config_file = config_file
            config = manager.load_config()
            
            # v3 should be forced on regardless of config file
            assert config.app.feature_v3_eventstore is True
            
            # Legacy flags should not exist in final config
            assert not hasattr(config.app, 'feature_v3_dualwrite')
            
        finally:
            config_file.unlink()
    
    def test_config_validation_rejects_legacy_fields(self):
        """Test that configuration validation rejects any legacy v2 fields."""
        # This test ensures our AppConfig model doesn't accept legacy fields
        valid_config_dict = {
            "feature_v3_eventstore": True,
            "app_name": "SoulLink Tracker"
        }
        
        # Should work fine
        config = AppConfig(**valid_config_dict)
        assert config.feature_v3_eventstore is True
        
        # Should reject legacy fields by raising validation error
        invalid_config_dict = {
            "feature_v3_eventstore": True,
            "feature_v3_dualwrite": True,  # Legacy field
            "app_name": "SoulLink Tracker"
        }
        
        try:
            AppConfig(**invalid_config_dict)
            assert False, "Should have rejected legacy config fields"
        except (TypeError, ValueError):
            # Expected - pydantic should reject unknown fields
            pass
    
    def test_database_url_override_still_works(self):
        """Test that database URL override functionality is preserved."""
        test_db_url = "sqlite:///test_v3_only.db"
        
        with patch.dict(os.environ, {'SOULLINK_DATABASE_URL': test_db_url}):
            manager = ConfigManager()
            config = manager.create_default_config()
            assert config.database.url == test_db_url
            # v3 should still be enabled
            assert config.app.feature_v3_eventstore is True