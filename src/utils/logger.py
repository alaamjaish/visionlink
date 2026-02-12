"""
VisionLink Logging Framework

CRITICAL: Logs are the ONLY way to debug on this headless device.
Everything gets logged - button presses, API calls, errors, state changes, file ops.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Will be initialized by setup_logging()
_initialized = False


def setup_logging(log_dir: str = None, level: str = "DEBUG"):
    """Initialize the logging system. Call once at startup."""
    global _initialized
    if _initialized:
        return

    if log_dir is None:
        from config import LOGS_DIR
        log_dir = LOGS_DIR
    else:
        log_dir = Path(log_dir)

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "visionlink.log"

    # Format: timestamp - module - level - message
    formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Rotating file handler (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Console handler (for dev, when running manually)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _initialized = True

    logger = logging.getLogger("setup")
    logger.info("=" * 60)
    logger.info("VisionLink logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Log level: {level}")
    logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use module name as the name."""
    return logging.getLogger(f"vl.{name}")
