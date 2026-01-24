"""Logging utilities for consistent logging across components."""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    name: Optional[str] = None,
) -> logging.Logger:
    """Set up logging with consistent formatting.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Optional custom format string
        name: Logger name (default: root logger)

    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(logging.Formatter(format_string))

    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a named logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
