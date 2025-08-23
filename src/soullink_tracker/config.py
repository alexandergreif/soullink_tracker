"""
Configuration management for SoulLink Tracker Portable Edition

Handles auto-configuration with sensible defaults and environment detection.
Replaces complex setup scripts with runtime configuration.
"""

import json
import os
import platform
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, asdict
import logging
import sys

if TYPE_CHECKING:
    from .auth.rate_limiter import RateLimitConfig

# List of known weak/default JWT secrets that should be rejected
WEAK_JWT_SECRETS = {
    "your-secret-key-change-in-production",
    "secret",
    "key",
    "password",
    "jwt-secret",
    "secret-key",
    "change-me",
    "default",
    "test",
    "development",
    "dev",
    "demo",
    "example",
    "sample",
}


def _validate_jwt_secret_key(jwt_secret_key: str) -> None:
    """Validate JWT secret key security and reject weak/default keys.

    Args:
        jwt_secret_key: The JWT secret key to validate

    Raises:
        SystemExit: If the secret key is weak, default, or insecure
    """
    if not jwt_secret_key:
        logging.critical(
            "JWT secret key is empty - this is a critical security vulnerability"
        )
        sys.exit(1)

    if len(jwt_secret_key) < 32:
        logging.critical(
            f"JWT secret key is too short ({len(jwt_secret_key)} chars). "
            f"Minimum 32 characters required for security."
        )
        sys.exit(1)

    if jwt_secret_key.lower() in WEAK_JWT_SECRETS:
        logging.critical(
            f"JWT secret key '{jwt_secret_key}' is a known weak/default secret. "
            f"This allows attackers to forge tokens across installations. "
            f"Set SOULLINK_JWT_SECRET_KEY environment variable with a secure key."
        )
        sys.exit(1)

    # Additional entropy check - ensure it's not just repeated characters
    unique_chars = len(set(jwt_secret_key))
    if unique_chars < 8:
        logging.critical(
            f"JWT secret key has insufficient entropy ({unique_chars} unique characters). "
            f"Use a cryptographically secure random key."
        )
        sys.exit(1)

    # Check for common patterns that suggest a weak key
    if any(
        pattern in jwt_secret_key.lower()
        for pattern in ["123", "abc", "password", "secret", "key", "qwerty", "admin"]
    ):
        logging.warning(
            "JWT secret key contains common patterns that may indicate weak security. "
            "Consider using a fully random key generated with secrets.token_urlsafe(64)."
        )

    logging.debug(
        f"JWT secret key validation passed ({len(jwt_secret_key)} chars, {unique_chars} unique)"
    )


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = "sqlite:///soullink_tracker.db"
    echo: bool = False
    pool_pre_ping: bool = True
    log_queries: bool = False  # Enable query logging for performance analysis


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True  # Enable debug logging by default for troubleshooting
    auto_reload: bool = False
    workers: int = 1


@dataclass
class AppConfig:
    """Main application configuration."""

    app_name: str = "SoulLink Tracker"
    version: str = "2.0.0"
    description: str = "Real-time tracker for 3-player Pokemon SoulLink runs"

    # Paths (will be set automatically)
    web_dir: Optional[str] = None
    data_dir: Optional[str] = None
    lua_dir: Optional[str] = None
    user_data_dir: Optional[str] = None

    # Features
    auto_open_browser: bool = True
    enable_system_tray: bool = True
    enable_cors: bool = True

    # Event Store Configuration (v3-only)
    feature_v3_eventstore: bool = (
        True  # v3 event sourcing is the only supported architecture
    )

    # Security Configuration
    session_ttl_days: int = 30  # Session token TTL in days
    password_hash_iterations: int = 120_000  # PBKDF2 iterations
    auth_allow_legacy_bearer: bool = True  # Allow legacy bearer token auth

    # JWT Configuration - secret key will be auto-generated or from environment
    jwt_secret_key: str = ""  # Must be set at runtime - no default for security
    jwt_access_token_expires_minutes: int = 15  # Access token TTL
    jwt_refresh_token_expires_days: int = 30  # Refresh token TTL

    # Rate Limiting Configuration
    enable_global_rate_limiting: bool = True  # Enable global rate limiting middleware
    rate_limit_auth_requests: int = 10  # Auth endpoints: max requests per minute
    rate_limit_api_requests: int = 60  # API endpoints: max requests per minute
    rate_limit_websocket_requests: int = 120  # WebSocket: max requests per minute
    rate_limit_window_seconds: int = 60  # Rate limit window duration
    rate_limit_failure_penalty_minutes: int = 15  # Block duration after auth failures
    rate_limit_max_failures: int = 5  # Max auth failures before blocking
    rate_limit_enable_user_limits: bool = True  # Enable per-user rate limiting
    rate_limit_enable_ip_bypass: bool = True  # Enable localhost bypass
    rate_limit_admin_bypass_ips: Optional[List[str]] = (
        None  # Admin IPs that bypass limits
    )

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_dir: str = "logs"  # Directory for log files

    # Environment
    is_portable: bool = False
    is_development: bool = False


@dataclass
class SoulLinkConfig:
    """Complete configuration for SoulLink Tracker."""

    app: AppConfig
    server: ServerConfig
    database: DatabaseConfig

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "app": asdict(self.app),
            "server": asdict(self.server),
            "database": asdict(self.database),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoulLinkConfig":
        """Create from dictionary."""
        return cls(
            app=AppConfig(**data.get("app", {})),
            server=ServerConfig(**data.get("server", {})),
            database=DatabaseConfig(**data.get("database", {})),
        )


class ConfigManager:
    """Manages configuration loading, saving, and auto-detection."""

    def __init__(self):
        self.config_file: Optional[Path] = None
        self.config: Optional[SoulLinkConfig] = None

    def detect_environment(self) -> Dict[str, Any]:
        """Detect the current environment and return environment info."""
        env_info = {}

        # Detect if we're in a portable/bundled environment
        is_portable = bool(os.getenv("SOULLINK_PORTABLE", "0") == "1")
        is_development = not is_portable and "site-packages" in __file__

        env_info["is_portable"] = is_portable
        env_info["is_development"] = is_development

        # Get paths from environment (set by launcher)
        env_info["web_dir"] = os.getenv("SOULLINK_WEB_DIR")
        env_info["data_dir"] = os.getenv("SOULLINK_DATA_DIR")
        env_info["lua_dir"] = os.getenv("SOULLINK_LUA_DIR")
        env_info["user_data_dir"] = os.getenv("SOULLINK_USER_DATA_DIR")

        # Debug mode
        env_info["debug"] = bool(os.getenv("SOULLINK_DEBUG", "0") == "1")

        # v3 Event Store (always enabled, ignores env vars)
        env_info["feature_v3_eventstore"] = (
            True  # v3 is the only supported architecture
        )

        return env_info

    def get_config_file_path(self) -> Path:
        """Get the path for the config file."""
        user_data_dir = os.getenv("SOULLINK_USER_DATA_DIR")
        if user_data_dir:
            config_dir = Path(user_data_dir)
        elif os.getenv("SOULLINK_PORTABLE", "0") == "1":
            # Portable mode - use current directory
            config_dir = Path.cwd() / "data"
        else:
            # Development mode
            config_dir = Path(__file__).parent.parent.parent / "data"

        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.json"

    def create_default_config(self) -> SoulLinkConfig:
        """Create default configuration with auto-detected values."""
        env_info = self.detect_environment()

        # Check for database URL override
        db_url = os.getenv("SOULLINK_DATABASE_URL") or DatabaseConfig().url

        # Generate or get JWT secret key from environment
        jwt_secret_key = os.getenv("SOULLINK_JWT_SECRET_KEY")
        if not jwt_secret_key:
            # Generate cryptographically secure 64-byte secret
            jwt_secret_key = secrets.token_urlsafe(64)  # 512-bit key
            logging.info("Generated new JWT secret key (not from environment)")
        else:
            logging.info(
                "Using JWT secret key from SOULLINK_JWT_SECRET_KEY environment variable"
            )

        # Validate JWT secret key security
        _validate_jwt_secret_key(jwt_secret_key)

        # Create default configuration
        config = SoulLinkConfig(
            app=AppConfig(
                web_dir=env_info.get("web_dir"),
                data_dir=env_info.get("data_dir"),
                lua_dir=env_info.get("lua_dir"),
                user_data_dir=env_info.get("user_data_dir"),
                is_portable=env_info["is_portable"],
                is_development=env_info["is_development"],
                log_level="DEBUG" if env_info["debug"] else "INFO",
                feature_v3_eventstore=env_info["feature_v3_eventstore"],
                jwt_secret_key=jwt_secret_key,
            ),
            server=ServerConfig(
                debug=env_info["debug"], auto_reload=env_info["is_development"]
            ),
            database=DatabaseConfig(url=db_url),
        )

        # Adjust database path for portable mode
        if env_info["is_portable"] and env_info.get("user_data_dir"):
            db_path = Path(env_info["user_data_dir"]) / "soullink_tracker.db"
            config.database.url = f"sqlite:///{db_path}"

        return config

    def load_config(self) -> SoulLinkConfig:
        """Load configuration from file or create default."""
        self.config_file = self.get_config_file_path()

        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Update with current environment
                env_info = self.detect_environment()
                data["app"].update(
                    {
                        "web_dir": env_info.get("web_dir"),
                        "data_dir": env_info.get("data_dir"),
                        "lua_dir": env_info.get("lua_dir"),
                        "user_data_dir": env_info.get("user_data_dir"),
                        "is_portable": env_info["is_portable"],
                        "is_development": env_info["is_development"],
                        "feature_v3_eventstore": env_info["feature_v3_eventstore"],
                    }
                )

                # Override database URL if environment variable is set
                if os.getenv("SOULLINK_DATABASE_URL"):
                    if "database" not in data:
                        data["database"] = {}
                    data["database"]["url"] = os.getenv("SOULLINK_DATABASE_URL")

                self.config = SoulLinkConfig.from_dict(data)
                logging.info(f"Loaded configuration from {self.config_file}")

            except Exception as e:
                logging.warning(f"Failed to load config from {self.config_file}: {e}")
                logging.info("Creating default configuration")
                self.config = self.create_default_config()
        else:
            logging.info("No config file found, creating default configuration")
            self.config = self.create_default_config()

        return self.config

    def save_config(self, config: Optional[SoulLinkConfig] = None) -> bool:
        """Save configuration to file."""
        if config is None:
            config = self.config

        if config is None:
            logging.error("No configuration to save")
            return False

        try:
            if self.config_file is None:
                self.config_file = self.get_config_file_path()

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

            logging.info(f"Saved configuration to {self.config_file}")
            return True

        except Exception as e:
            logging.error(f"Failed to save config to {self.config_file}: {e}")
            return False

    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with new values."""
        if self.config is None:
            self.load_config()

        try:
            # Apply updates to the appropriate sections
            config_dict = self.config.to_dict()

            for key, value in updates.items():
                if "." in key:
                    # Handle nested keys like "server.port"
                    section, field = key.split(".", 1)
                    if section in config_dict:
                        config_dict[section][field] = value
                else:
                    # Handle top-level keys
                    if key in config_dict:
                        if isinstance(value, dict):
                            config_dict[key].update(value)
                        else:
                            config_dict[key] = value

            self.config = SoulLinkConfig.from_dict(config_dict)
            return self.save_config()

        except Exception as e:
            logging.error(f"Failed to update configuration: {e}")
            return False

    def get_database_url(self) -> str:
        """Get the database URL."""
        if self.config is None:
            self.load_config()
        return self.config.database.url

    def get_web_directory(self) -> Optional[Path]:
        """Get the web directory path."""
        if self.config is None:
            self.load_config()
        web_dir = self.config.app.web_dir
        return Path(web_dir) if web_dir else None

    def get_data_directory(self) -> Optional[Path]:
        """Get the data directory path."""
        if self.config is None:
            self.load_config()
        data_dir = self.config.app.data_dir
        return Path(data_dir) if data_dir else None

    def get_lua_directory(self) -> Optional[Path]:
        """Get the Lua scripts directory path."""
        if self.config is None:
            self.load_config()
        lua_dir = self.config.app.lua_dir
        return Path(lua_dir) if lua_dir else None

    def is_portable_mode(self) -> bool:
        """Check if we're running in portable mode."""
        if self.config is None:
            self.load_config()
        return self.config.app.is_portable

    def is_development_mode(self) -> bool:
        """Check if we're running in development mode."""
        if self.config is None:
            self.load_config()
        return self.config.app.is_development

    def validate_config(self) -> List[str]:
        """Validate configuration and return list of warnings/errors."""
        if self.config is None:
            self.load_config()

        issues = []

        # Check critical directories exist
        if self.config.app.web_dir:
            web_path = Path(self.config.app.web_dir)
            if not web_path.exists():
                issues.append(f"Web directory not found: {web_path}")

        if self.config.app.data_dir:
            data_path = Path(self.config.app.data_dir)
            if not data_path.exists():
                issues.append(f"Data directory not found: {data_path}")

        # Check database file is writable
        db_url = self.config.database.url
        if db_url.startswith("sqlite:///"):
            db_path = Path(db_url.replace("sqlite:///", ""))
            db_dir = db_path.parent
            if not db_dir.exists():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create database directory: {e}")
            elif not os.access(db_dir, os.W_OK):
                issues.append(f"Database directory is not writable: {db_dir}")

        # Windows-specific checks
        if platform.system() == "Windows":
            # Check for common Windows path issues
            for path_str in [
                self.config.app.web_dir,
                self.config.app.data_dir,
                self.config.app.lua_dir,
            ]:
                if path_str and "\\" in path_str and "/" in path_str:
                    issues.append(f"Mixed path separators detected: {path_str}")

        return issues

    def validate_security_config(self) -> None:
        """Validate security-critical configuration at startup.

        Raises:
            SystemExit: If critical security issues are found
        """
        if self.config is None:
            self.load_config()

        # Validate JWT secret key
        _validate_jwt_secret_key(self.config.app.jwt_secret_key)

        # Additional security validations can be added here
        logging.info("Security configuration validation passed")


# Global config manager instance
config_manager = ConfigManager()


def get_rate_limit_config() -> "RateLimitConfig":
    """Create a RateLimitConfig from the current app configuration."""
    from .auth.rate_limiter import RateLimitConfig, RateLimitTier

    app_config = get_config().app

    return RateLimitConfig(
        auth_strict=RateLimitTier(
            max_requests=app_config.rate_limit_auth_requests,
            window_seconds=app_config.rate_limit_window_seconds,
            description="Authentication endpoints",
        ),
        api_moderate=RateLimitTier(
            max_requests=app_config.rate_limit_api_requests,
            window_seconds=app_config.rate_limit_window_seconds,
            description="API endpoints",
        ),
        websocket_lenient=RateLimitTier(
            max_requests=app_config.rate_limit_websocket_requests,
            window_seconds=app_config.rate_limit_window_seconds,
            description="WebSocket connections",
        ),
        failure_penalty_minutes=app_config.rate_limit_failure_penalty_minutes,
        max_failures_before_block=app_config.rate_limit_max_failures,
        enable_user_limits=app_config.rate_limit_enable_user_limits,
        enable_ip_bypass=app_config.rate_limit_enable_ip_bypass,
        admin_bypass_ips=set(
            app_config.rate_limit_admin_bypass_ips or ["127.0.0.1", "::1"]
        ),
    )


def get_config() -> SoulLinkConfig:
    """Get the current configuration."""
    return config_manager.load_config()


def get_database_url() -> str:
    """Get the database URL."""
    return config_manager.get_database_url()


def get_web_directory() -> Optional[Path]:
    """Get the web directory."""
    return config_manager.get_web_directory()


def get_data_directory() -> Optional[Path]:
    """Get the data directory."""
    return config_manager.get_data_directory()


def get_lua_directory() -> Optional[Path]:
    """Get the Lua directory."""
    return config_manager.get_lua_directory()


def is_portable_mode() -> bool:
    """Check if running in portable mode."""
    return config_manager.is_portable_mode()


def is_development_mode() -> bool:
    """Check if running in development mode."""
    return config_manager.is_development_mode()


def validate_startup_security() -> None:
    """Validate security configuration at application startup.

    This function should be called early in the application startup process
    to ensure critical security settings are properly configured.

    Raises:
        SystemExit: If critical security vulnerabilities are detected
    """
    try:
        config_manager.validate_security_config()
        logging.info("Startup security validation completed successfully")
    except SystemExit:
        # Re-raise system exit (security validation failure)
        raise
    except Exception as e:
        logging.critical(f"Unexpected error during security validation: {e}")
        sys.exit(1)
