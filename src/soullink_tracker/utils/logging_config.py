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
                      Can also be a module path like 'soullink_tracker.api.websockets'
            
        Returns:
            Logger instance for the component
        """
        if not cls._initialized:
            cls.initialize()
            
        # Handle module paths - extract component from __name__ format
        original_component = component
        if 'soullink_tracker.' in component:
            # Extract component from module path
            parts = component.split('.')
            if len(parts) >= 3:
                # More comprehensive mapping
                if parts[2] == 'websockets':
                    component = 'websocket'
                elif parts[2] in ['admin', 'events', 'queries'] or parts[1] == 'api':
                    component = 'api'
                elif parts[1] == 'auth':
                    component = 'auth'
                elif parts[1] in ['db', 'store'] or any(x in parts for x in ['database', 'models', 'projections']):
                    component = 'database'
                elif parts[1] == 'events':
                    component = 'events'
                elif parts[1] == 'core' and 'rules' in parts:
                    component = 'events'  # Rules engine is part of event processing
                elif parts[-1] in ['launcher', 'user_launcher', 'portable_logger']:
                    component = 'launcher'
                else:
                    # Default to second level (soullink_tracker.X.Y -> X)
                    component = parts[1] if len(parts) > 1 else 'main'
            elif len(parts) >= 2:
                # soullink_tracker.main -> main
                component = parts[1]
            
        # Map component to logger
        if component in cls._loggers:
            logger = cls._loggers[component]
        else:
            # Create a new component logger on-demand
            cls._create_component_logger(component)
            logger = cls._loggers.get(component, cls._loggers.get('main'))
            
        # Ensure this logger writes to unified.log by copying its handler
        if 'unified' in cls._loggers and component != 'unified':
            unified_logger = cls._loggers['unified']
            # Find the unified handler
            unified_handler = None
            for handler in unified_logger.handlers:
                if hasattr(handler, 'baseFilename') and 'unified.log' in handler.baseFilename:
                    unified_handler = handler
                    break
            
            # Add unified handler to this component logger if not already present
            if unified_handler:
                handler_exists = False
                for existing_handler in logger.handlers:
                    if (hasattr(existing_handler, 'baseFilename') and
                        hasattr(unified_handler, 'baseFilename') and
                        existing_handler.baseFilename == unified_handler.baseFilename):
                        handler_exists = True
                        break
                
                if not handler_exists:
                    logger.addHandler(unified_handler)
            
        return logger
    
    @classmethod
    def _create_component_logger(cls, component: str) -> None:
        """Create a component logger on-demand."""
        if not cls._initialized or component in cls._loggers:
            return
            
        logger_name = f"soullink.{component}"
        logger = logging.getLogger(logger_name)
        
        # Clear existing handlers
        logger.handlers.clear()
        logger.propagate = False
        
        # Set level (DEBUG if debug mode, otherwise INFO)
        config = get_config()
        level = logging.DEBUG if config.server.debug else logging.INFO
        logger.setLevel(level)
        
        # Create component-specific file handler
        log_file = cls._log_dir / f'{component}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Add unified handler for cross-component visibility
        if 'unified' in cls._loggers:
            unified_logger = cls._loggers['unified']
            # Find the unified handler
            unified_handler = None
            for handler in unified_logger.handlers:
                if hasattr(handler, 'baseFilename') and 'unified.log' in handler.baseFilename:
                    unified_handler = handler
                    break
            
            if unified_handler:
                logger.addHandler(unified_handler)
        
        # Store logger reference
        cls._loggers[component] = logger
    
    @classmethod
    def log_exception(cls, component: str, exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an exception with context to both component and error logs.
        
        Args:
            component: Component where the exception occurred
            exc: The exception to log
            context: Additional context information
        """
        # Get the actual logger instances directly from _loggers to avoid handler duplication
        component_logger = cls._loggers.get(component)
        if not component_logger and component not in cls._loggers:
            cls._create_component_logger(component)
            component_logger = cls._loggers.get(component)
        
        error_logger = cls._loggers.get('error')
        
        if not component_logger or not error_logger:
            # Fallback to main logger if component/error loggers not found
            fallback_logger = cls._loggers.get('main')
            if fallback_logger:
                fallback_logger.error(f"Failed to get proper loggers for component: {component}")
            return
        
        # Build context string
        context_str = ""
        if context:
            context_str = " | Context: " + ", ".join(f"{k}={v}" for k, v in context.items())
        
        # Log to component logger (this will also go to unified due to shared handler)
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


# _DualLogger class removed - now using shared handlers approach for unified logging


# Convenience functions
def get_logger(component: str) -> logging.Logger:
    """Get a logger for a specific component."""
    return ComponentLogger.get_logger(component)


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a module using its __name__.
    This automatically maps module paths to appropriate components.
    
    Example:
        logger = get_module_logger(__name__)  # Works from any module
    """
    return ComponentLogger.get_logger(module_name)


def initialize_logging(log_dir: Optional[str] = None, debug: bool = False) -> None:
    """Initialize the logging system."""
    ComponentLogger.initialize(log_dir=log_dir, debug=debug)


def log_exception(component: str, exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log an exception with context."""
    ComponentLogger.log_exception(component, exc, context)


def get_log_directory() -> Optional[Path]:
    """Get the current log directory path."""
    return ComponentLogger.get_log_directory()