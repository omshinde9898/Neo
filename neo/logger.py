"""Logging configuration for Neo."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from platformdirs import user_log_dir


def get_log_dir() -> Path:
    """Get the log directory for Neo."""
    # Try .neo/logs in project root first, then fall back to user log dir
    cwd = Path.cwd()
    for _ in range(5):
        neo_dir = cwd / ".neo"
        if neo_dir.exists():
            log_dir = neo_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            return log_dir
        if (cwd / ".git").exists():
            # In a git repo but no .neo, create it
            log_dir = neo_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        if cwd.parent == cwd:
            break
        cwd = cwd.parent

    # Fall back to user log directory
    log_dir = Path(user_log_dir("neo", "neo-ai"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    level: int = logging.DEBUG,
    log_to_file: bool = True,
    log_to_console: bool = False,
) -> logging.Logger:
    """Set up logging for Neo.

    Args:
        level: Logging level (default: DEBUG)
        log_to_file: Whether to log to file (default: True)
        log_to_console: Whether to log to console (default: False)

    Returns:
        The Neo logger instance
    """
    logger = logging.getLogger("neo")
    logger.setLevel(level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_to_file:
        log_dir = get_log_dir()
        log_file = log_dir / "neo.log"

        # Rotate existing logs
        _rotate_logs(log_dir)

        # File handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_to_console:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def _rotate_logs(log_dir: Path, max_files: int = 5) -> None:
    """Rotate log files, keeping only the most recent ones."""
    log_file = log_dir / "neo.log"
    if not log_file.exists():
        return

    # Rotate existing logs
    for i in range(max_files - 1, 0, -1):
        old_file = log_dir / f"neo.log.{i}"
        new_file = log_dir / f"neo.log.{i + 1}"
        if old_file.exists():
            if new_file.exists():
                new_file.unlink()
            old_file.rename(new_file)

    # Rotate current log
    if log_file.exists():
        current_backup = log_dir / "neo.log.1"
        if current_backup.exists():
            current_backup.unlink()
        log_file.rename(current_backup)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name, prefixed with 'neo.'."""
    if not name.startswith("neo."):
        name = f"neo.{name}"
    return logging.getLogger(name)


# Global logger instance
logger = setup_logging()


def log_exception(exc: Exception, context: dict[str, Any] | None = None) -> None:
    """Log an exception with optional context."""
    logger.exception("Exception occurred: %s", exc)
    if context:
        for key, value in context.items():
            logger.debug("Context %s: %s", key, value)
