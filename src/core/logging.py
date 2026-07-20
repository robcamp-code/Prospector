"""Centralized logging configuration for Prospector."""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure logging for the application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
               Defaults to LOG_LEVEL env var or DEBUG.
    """
    log_level = level or os.environ.get("LOG_LEVEL", "DEBUG")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.DEBUG),
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    # Reduce third-party noise
    for lib in ["httpcore", "httpx", "sqlalchemy.engine", "openai", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
