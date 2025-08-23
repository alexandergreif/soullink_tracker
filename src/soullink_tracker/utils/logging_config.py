"""
Centralized logging configuration for SoulLink Tracker.
Provides component-specific loggers with separate log files.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..config import get_config


class ComponentLogger:
    """Manages component-specific logging with separate files."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False
    _log_dir: Optional[Path] = None
    
    # Component definitions with their log levels
    COMPONENTS = {
        'api': {'level': logging.INFO, 'file': 'api.log'},
        'database': {'level': logging.INFO, 'file': 'database.log'},
        'events': {'level': logging.INFO, 'file': 'events.log'},
        'auth': {'level': logging.INFO, 'file': 'auth.log'},
        'websocket': {'level': logging.INFO, 'file': 'websocket.log'},
        'middleware': {'level': logging.INFO, 'file': 'middleware.log'},
        'launcher': {'level': logging.INFO, 'file': 'launcher.log'},
        'watcher': {'level': logging.INFO, 'file': 'watcher.log'},
        'projection': {'level': logging.INFO, 'file': 'projection.log'},
        'main': {'level': logging.INFO, 'file': 'main.log'},
        'error': {'level': logging.ERROR, 'file': 'errors.log'},  # Centralized error log
    }
    
    @classmethod
    def initialize(cls, log_dir: Optional[str] = None, debug: bool = False) -> None:
        """
        Initialize the logging system with component-specific loggers.
        
        Args:
            log_dir: Directory for log files. Defaults to config.log_dir
            debug: Enable debug logging for all components
        """
        if cls._initialized:
            return
            
        config = get_config()
        
        # Set log directory
        if log_dir:
            cls._log_dir = Path(log_dir)
        else:
            cls._log_dir = Path(config.app.log_dir)
            
        # Create log directory if it doesn't exist
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session-specific subdirectory
        session_dir = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls._log_dir = cls._log_dir / session_dir
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Write session info
        session_info_file = cls._log_dir / "session_info.txt"
        with open(session_info_file, 'w') as f:
            f.write(f"Session started: {datetime.now().isoformat()}\n")
            f.write(f"Debug mode: {debug}\n")
            f.write(f"Config:\n")
            f.write(f"  Database: {config.database.url}\n")
            f.write(f"  Portable mode: {config.app.is_portable}\n")
            f.write(f"  Development mode: {config.app.is_development}\n")
            f.write(f"  Log directory: {cls._log_dir}\n")
        
        # Set up formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Set root logger level
        root_level = logging.DEBUG if debug else logging.INFO
        logging.getLogger().setLevel(root_level)
        
        # Create loggers for each component
        for component_name, component_config in cls.COMPONENTS.items():
            logger_name = f"soullink.{component_name}"
            logger = logging.getLogger(logger_name)
            
            # Clear existing handlers
            logger.handlers.clear()
            logger.propagate = False
            
            # Set level (DEBUG if debug mode, otherwise component default)
            level = logging.DEBUG if debug else component_config['level']
            logger.setLevel(level)
            
            # File handler with rotation
            log_file = cls._log_dir / component_config['file']
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
            
            # Console handler for errors and critical
            if component_name in ['error', 'main']:
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setLevel(logging.ERROR)
                console_handler.setFormatter(simple_formatter)
                logger.addHandler(console_handler)
            
            # Store logger reference
            cls._loggers[component_name] = logger
            
        # Create a unified log file for all components
        unified_logger = logging.getLogger('soullink.unified')
        unified_logger.setLevel(root_level)
        unified_logger.propagate = False
        
        unified_file = cls._log_dir / 'unified.log'
        unified_handler = logging.handlers.RotatingFileHandler(
            unified_file,
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=3,
            encoding='utf-8'
        )
        unified_handler.setLevel(root_level)
        unified_handler.setFormatter(detailed_formatter)
        unified_logger.addHandler(unified_handler)
        
        cls._loggers['unified'] = unified_logger
        
        # Mark as initialized before logging to avoid recursion
        cls._initialized = True
        
        # Log initialization
        main_logger = cls._loggers.get('main')
        if main_logger:
            main_logger.info("=" * 80)
            main_logger.info("SoulLink Tracker Logging System Initialized")
            main_logger.info(f"Session: {session_dir}")
            main_logger.info(f"Log directory: {cls._log_dir}")
            main_logger.info(f"Debug mode: {debug}")
            main_logger.info("=" * 80)
    
    @classmethod
    def get_logger(cls, component: str) -> logging.Logger:
        """
        Get a logger for a specific component.
        
        Args:
            component: Component name (api, database, events, auth, etc.)
            
        Returns:
            Logger instance for the component
        """
        if not cls._initialized:
            cls.initialize()
            
        # Map component to logger
        if component in cls._loggers:
            logger = cls._loggers[component]
        else:
            # Default to main logger for unknown components
            logger = cls._loggers.get('main', logging.getLogger(f'soullink.{component}'))
            
        # Also log to unified logger
        if 'unified' in cls._loggers and component != 'unified':
            return _DualLogger(logger, cls._loggers['unified'])
            
        return logger
    
    @classmethod
    def log_exception(cls, component: str, exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an exception with context to both component and error logs.
        
        Args:
            component: Component where the exception occurred
            exc: The exception to log
            context: Additional context information
        """
        component_logger = cls.get_logger(component)
        error_logger = cls.get_logger('error')
        
        # Build context string
        context_str = ""
        if context:
            context_str = " | Context: " + ", ".join(f"{k}={v}" for k, v in context.items())
        
        # Log to component logger
        component_logger.error(f"Exception in {component}: {type(exc).__name__}: {exc}{context_str}", exc_info=True)
        
        # Log to centralized error logger
        error_logger.error(f"[{component}] {type(exc).__name__}: {exc}{context_str}", exc_info=True)
    
    @classmethod
    def get_log_directory(cls) -> Optional[Path]:
        """Get the current log directory path."""
        return cls._log_dir
    
    @classmethod
    def rotate_logs(cls) -> None:
        """Manually trigger log rotation for all handlers."""
        for logger in cls._loggers.values():
            for handler in logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.doRollover()


class _DualLogger:
    """Logger that writes to two loggers simultaneously."""
    
    def __init__(self, primary: logging.Logger, secondary: logging.Logger):
        self.primary = primary
        self.secondary = secondary
        self.name = primary.name  # For string representation
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        self.primary.log(level, msg, *args, **kwargs)
        self.secondary.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        self.primary.exception(msg, *args, **kwargs)
        self.secondary.exception(msg, *args, **kwargs)
    
    def isEnabledFor(self, level: int) -> bool:
        """Check if logger is enabled for given level."""
        return self.primary.isEnabledFor(level)
    
    def __str__(self) -> str:
        """String representation of the logger."""
        return f"DualLogger({self.primary.name})"


# Convenience functions
def get_logger(component: str) -> logging.Logger:
    """Get a logger for a specific component."""
    return ComponentLogger.get_logger(component)


def initialize_logging(log_dir: Optional[str] = None, debug: bool = False) -> None:
    """Initialize the logging system."""
    ComponentLogger.initialize(log_dir=log_dir, debug=debug)


def log_exception(component: str, exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log an exception with context."""
    ComponentLogger.log_exception(component, exc, context)


def get_log_directory() -> Optional[Path]:
    """Get the current log directory path."""
    return ComponentLogger.get_log_directory()