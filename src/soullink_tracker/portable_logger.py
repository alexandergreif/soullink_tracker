"""
Portable SoulLink Tracker Logging System

Provides comprehensive logging, diagnostics, and error reporting for the portable version.
Creates structured logs for easy debugging and support.
"""

import logging
import platform
import sys
import os
import traceback
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class PortableLogger:
    """Comprehensive logging system for portable SoulLink Tracker."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.cwd() / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # Create multiple log files for different purposes
        self.startup_log = self.log_dir / "startup.log"
        self.runtime_log = self.log_dir / "runtime.log"
        self.error_log = self.log_dir / "error.log"
        self.diagnostic_log = self.log_dir / "diagnostic.log"

        self.setup_logging()
        self.log_system_info()

    def setup_logging(self):
        """Setup comprehensive logging configuration."""
        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)d | %(message)s"
        )
        simple_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s"
        )

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)

        # Startup log handler (everything during startup)
        startup_handler = logging.FileHandler(
            self.startup_log, mode="w", encoding="utf-8"
        )
        startup_handler.setLevel(logging.DEBUG)
        startup_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(startup_handler)

        # Runtime log handler (INFO and above during runtime)
        runtime_handler = logging.FileHandler(
            self.runtime_log, mode="w", encoding="utf-8"
        )
        runtime_handler.setLevel(logging.INFO)
        runtime_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(runtime_handler)

        # Error log handler (ERROR and above only)
        error_handler = logging.FileHandler(self.error_log, mode="w", encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)

        # Store handlers for later management
        self.console_handler = console_handler
        self.startup_handler = startup_handler
        self.runtime_handler = runtime_handler
        self.error_handler = error_handler

        logging.info("=== SoulLink Tracker Portable Logging Started ===")

    def log_system_info(self):
        """Log comprehensive system information."""
        logger = logging.getLogger(__name__)

        logger.info("=== SYSTEM INFORMATION ===")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"System: {platform.system()} {platform.release()}")
        logger.info(f"Architecture: {platform.architecture()}")
        logger.info(f"Machine: {platform.machine()}")
        logger.info(f"Processor: {platform.processor()}")

        logger.info("=== PYTHON INFORMATION ===")
        logger.info(f"Python Version: {sys.version}")
        logger.info(f"Python Executable: {sys.executable}")
        logger.info(f"Python Path: {sys.path[:3]}... ({len(sys.path)} total)")

        logger.info("=== EXECUTION ENVIRONMENT ===")
        logger.info(f"Working Directory: {os.getcwd()}")
        logger.info(
            f"Script Location: {__file__ if '__file__' in globals() else 'Unknown'}"
        )
        logger.info(f"Frozen: {hasattr(sys, 'frozen')}")
        logger.info(f"PyInstaller: {hasattr(sys, '_MEIPASS')}")
        if hasattr(sys, "_MEIPASS"):
            logger.info(f"PyInstaller Temp Dir: {sys._MEIPASS}")

        logger.info("=== ENVIRONMENT VARIABLES ===")
        relevant_vars = ["PATH", "PYTHONPATH", "SOULLINK_DEBUG", "SOULLINK_PORTABLE"]
        for var in relevant_vars:
            value = os.environ.get(var, "Not Set")
            if var == "PATH":
                # Truncate PATH for readability
                value = f"{value[:100]}... (truncated)" if len(value) > 100 else value
            logger.info(f"{var}: {value}")

    def log_import_test(self, module_name: str) -> bool:
        """Test and log module import."""
        logger = logging.getLogger(__name__)
        try:
            __import__(module_name)
            logger.info(f"Import SUCCESS: {module_name}")
            return True
        except ImportError as e:
            logger.error(f"Import FAILED: {module_name} - {e}")
            return False
        except Exception as e:
            logger.error(f"Import ERROR: {module_name} - {type(e).__name__}: {e}")
            return False

    def log_critical_imports(self) -> Dict[str, bool]:
        """Test and log all critical imports."""
        logger = logging.getLogger(__name__)
        logger.info("=== TESTING CRITICAL IMPORTS ===")

        critical_modules = [
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "pydantic",
            "websockets",
            "cryptography",
            "passlib",
            "soullink_tracker",
            "soullink_tracker.main",
            "soullink_tracker.launcher",
            "soullink_tracker.config",
            "soullink_tracker.api.runs",
            "soullink_tracker.api.events",
            "soullink_tracker.db.models",
        ]

        results = {}
        for module in critical_modules:
            results[module] = self.log_import_test(module)

        failed_count = sum(1 for success in results.values() if not success)
        logger.info(
            f"Import test complete: {len(results) - failed_count}/{len(results)} successful"
        )

        if failed_count > 0:
            logger.error(f"CRITICAL: {failed_count} import failures detected!")

        return results

    def log_exception(self, exc: Exception, context: str = ""):
        """Log detailed exception information."""
        logger = logging.getLogger(__name__)

        logger.error(f"EXCEPTION in {context}: {type(exc).__name__}: {exc}")
        logger.error(f"Exception details: {repr(exc)}")

        # Log full traceback
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        for line in tb_lines:
            logger.error(f"TB: {line.rstrip()}")

    def log_resource_check(
        self, resource_path: Path, resource_type: str = "file"
    ) -> bool:
        """Log resource availability check."""
        logger = logging.getLogger(__name__)

        exists = resource_path.exists()
        if exists:
            if resource_path.is_file():
                size = resource_path.stat().st_size
                logger.info(
                    f"Resource OK: {resource_type} {resource_path} ({size} bytes)"
                )
            else:
                logger.info(f"Resource OK: {resource_type} {resource_path} (directory)")
        else:
            logger.error(f"Resource MISSING: {resource_type} {resource_path}")

        return exists

    def create_diagnostic_dump(self) -> Path:
        """Create comprehensive diagnostic dump for support."""
        dump_file = (
            self.log_dir
            / f"diagnostic_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        diagnostic_data = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "architecture": platform.architecture(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "python": {
                "version": sys.version,
                "executable": sys.executable,
                "frozen": hasattr(sys, "frozen"),
                "pyinstaller": hasattr(sys, "_MEIPASS"),
                "meipass": getattr(sys, "_MEIPASS", None),
                "path_count": len(sys.path),
                "path_sample": sys.path[:5],
            },
            "environment": {
                "cwd": os.getcwd(),
                "relevant_vars": {
                    var: os.environ.get(var)
                    for var in [
                        "PATH",
                        "PYTHONPATH",
                        "SOULLINK_DEBUG",
                        "SOULLINK_PORTABLE",
                    ]
                },
            },
            "imports": self.log_critical_imports(),
            "logs": {
                "startup_log": str(self.startup_log),
                "runtime_log": str(self.runtime_log),
                "error_log": str(self.error_log),
            },
        }

        try:
            with open(dump_file, "w", encoding="utf-8") as f:
                json.dump(diagnostic_data, f, indent=2, default=str)

            logging.info(f"Diagnostic dump created: {dump_file}")
            return dump_file

        except Exception as e:
            logging.error(f"Failed to create diagnostic dump: {e}")
            return None

    def switch_to_runtime_mode(self):
        """Switch from startup logging to runtime logging."""
        logger = logging.getLogger()

        # Remove startup handler, keep others
        if hasattr(self, "startup_handler"):
            logger.removeHandler(self.startup_handler)
            self.startup_handler.close()

        logging.info("Switched to runtime logging mode")

    def get_log_summary(self) -> Dict[str, Any]:
        """Get summary of log files for user."""
        summary = {"log_directory": str(self.log_dir), "files": {}}

        for log_file in [self.startup_log, self.runtime_log, self.error_log]:
            if log_file.exists():
                summary["files"][log_file.name] = {
                    "path": str(log_file),
                    "size": log_file.stat().st_size,
                    "modified": log_file.stat().st_mtime,
                }

        return summary


def setup_portable_logging(
    log_dir: Optional[Path] = None, debug: bool = False, role: str = "admin"
) -> PortableLogger:
    """Setup portable logging system."""
    # Enable debug mode if requested
    if debug:
        os.environ["SOULLINK_DEBUG"] = "1"

    # Use role-specific log directory if not provided
    if log_dir is None and role == "user":
        log_dir = Path.cwd() / "logs_user"
    elif log_dir is None:
        log_dir = Path.cwd() / "logs"

    return PortableLogger(log_dir)


def log_startup_error(error: Exception, context: str = "startup"):
    """Emergency logging for startup errors before logger is setup."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_msg = (
        f"{timestamp} STARTUP ERROR in {context}: {type(error).__name__}: {error}\n"
    )

    # Write to both console and emergency log file
    print(error_msg, file=sys.stderr)

    try:
        with open("emergency_error.log", "a", encoding="utf-8") as f:
            f.write(error_msg)
            f.write("Traceback:\n")
            traceback.print_exc(file=f)
            f.write("\n" + "=" * 50 + "\n")
    except Exception:
        pass  # If we can't log, don't make things worse
