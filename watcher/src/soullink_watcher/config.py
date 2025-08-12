"""Configuration management for the SoulLink Production Watcher."""

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class WatcherConfig:
    """Configuration for the production watcher."""
    
    base_url: str
    run_id: str
    player_id: str
    token: str
    spool_dir: Path
    dev: bool = False
    from_file: Optional[Path] = None
    poll_interval_secs: float = 1.0
    backoff_base_secs: float = 1.0
    backoff_max_secs: float = 300.0
    backoff_jitter_ratio: float = 0.2
    http_timeout_secs: float = 10.0


def default_spool_dir(dev: bool) -> Path:
    """Get the default spool directory based on platform and dev mode."""
    if dev:
        # Development mode: use repo-local spool directory
        return Path("spool")
    
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: C:\ProgramData\SoulLinkWatcher\spool
        program_data = os.getenv("PROGRAMDATA", "C:\\ProgramData")
        return Path(program_data) / "SoulLinkWatcher" / "spool"
    else:
        # Linux/macOS: ~/.local/state/soullink-watcher/spool
        # Fallback to ~/.local/share/soullink-watcher/spool if state doesn't exist
        home = Path.home()
        local_state = home / ".local" / "state"
        
        if local_state.exists():
            return local_state / "soullink-watcher" / "spool"
        else:
            return home / ".local" / "share" / "soullink-watcher" / "spool"


def read_from_env() -> WatcherConfig:
    """Read configuration from environment variables."""
    api_url = os.getenv("SOULLINK_API_URL", "http://127.0.0.1:8000")
    run_id = os.getenv("SOULLINK_RUN_ID", "default-run")
    player_id = os.getenv("SOULLINK_PLAYER_ID", "player-1")
    token = os.getenv("SOULLINK_SECURE_TOKEN", "")
    
    # Get spool directory from environment or default
    spool_dir_str = os.getenv("SOULLINK_WATCHER_SPOOL_DIR")
    if spool_dir_str:
        spool_dir = Path(spool_dir_str)
    else:
        dev_mode = os.getenv("SOULLINK_DEV", "false").lower() == "true"
        spool_dir = default_spool_dir(dev_mode)
    
    dev = os.getenv("SOULLINK_DEV", "false").lower() == "true"
    
    # Optional file input
    from_file_str = os.getenv("SOULLINK_FROM_FILE")
    from_file = Path(from_file_str) if from_file_str else None
    
    return WatcherConfig(
        base_url=api_url,
        run_id=run_id,
        player_id=player_id,
        token=token,
        spool_dir=spool_dir,
        dev=dev,
        from_file=from_file
    )


def get_config() -> WatcherConfig:
    """Get watcher configuration with precedence: environment -> defaults."""
    return read_from_env()


def ensure_dirs(cfg: WatcherConfig) -> None:
    """Create spool directory structure with appropriate permissions."""
    # Create base spool directory
    cfg.spool_dir.mkdir(parents=True, exist_ok=True)
    
    # Set restrictive permissions on POSIX systems
    if platform.system().lower() != "windows":
        cfg.spool_dir.chmod(0o700)
    
    # Create per-run/player subdirectories
    player_spool_dir = cfg.spool_dir / cfg.run_id / cfg.player_id
    player_spool_dir.mkdir(parents=True, exist_ok=True)
    
    if platform.system().lower() != "windows":
        player_spool_dir.chmod(0o700)
    
    # Create dead letter directory
    dead_dir = player_spool_dir / "dead"
    dead_dir.mkdir(exist_ok=True)
    
    if platform.system().lower() != "windows":
        dead_dir.chmod(0o700)
    
    return player_spool_dir