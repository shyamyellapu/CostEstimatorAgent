"""Application logging setup."""
from __future__ import annotations

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Configure consistent stdout logging for local and production runtimes."""
    level_name = (settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for noisy_logger in ("googleapiclient.discovery_cache", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
