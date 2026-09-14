"""Centralised logging configuration for SmartRoute AI Backend."""

import logging
import sys
from typing import Final

from app.core.config import get_settings

_LOG_FORMAT_DEV: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_FORMAT_JSON: Final[str] = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
)


def setup_logging() -> None:
    """Configure the root logger based on application settings.

    Call once during application startup (inside the lifespan handler).
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = _LOG_FORMAT_DEV if settings.is_development else _LOG_FORMAT_JSON

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on reload
    if not root.handlers:
        root.addHandler(handler)

    # Silence overly chatty libraries
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.  All application code should use this helper."""
    return logging.getLogger(f"smartroute.{name}")
