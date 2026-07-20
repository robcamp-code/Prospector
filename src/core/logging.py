"""Centralized logging configuration for Prospector."""

import logging
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

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
        # stderr is never block-buffered, so logs appear live even when
        # stdout is piped or captured (stdout stays clean for the REPL)
        handlers=[logging.StreamHandler(sys.stderr)],
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


_timing_logger = logging.getLogger("timing")


@contextmanager
def timed(step: str) -> Iterator[None]:
    """Log start/end/duration of a step for local-dev observability.

    Safe to wrap around `await` expressions (enter/exit are synchronous).
    """
    _timing_logger.info(f"▶ {step}")
    start = time.perf_counter()
    try:
        yield
        _timing_logger.info(f"✓ {step} ({time.perf_counter() - start:.1f}s)")
    except Exception:
        _timing_logger.info(f"✗ {step} FAILED ({time.perf_counter() - start:.1f}s)")
        raise
