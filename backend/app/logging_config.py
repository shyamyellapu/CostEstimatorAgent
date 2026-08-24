"""Application logging setup.

Configures three log destinations:
  stdout          — INFO+ (human-readable, coloured by level)
  logs/app.log    — INFO+ rotating, 10 MB × 5 backups
  logs/app_debug.log  — DEBUG+ rotating (only when debug=True), 20 MB × 3 backups
  logs/app_error.log  — ERROR+ rotating, 5 MB × 10 backups (never loses errors)
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from app.config import settings

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
_CONSOLE_FMT = logging.Formatter(
    "%(asctime)s %(levelname)-8s [%(name)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

_FILE_FMT = logging.Formatter(
    "%(asctime)s %(levelname)-8s [%(name)s] %(filename)s:%(funcName)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

_ERROR_FMT = logging.Formatter(
    "%(asctime)s %(levelname)-8s [%(name)s] %(filename)s:%(funcName)s:%(lineno)d\n"
    "  Process: %(process)d  Thread: %(thread)d\n"
    "  Message: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

class _LevelFilter(logging.Filter):
    """Accept only records at or above *min_level* and below *max_level*."""

    def __init__(self, min_level: int, max_level: int = logging.CRITICAL + 1):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        return self.min_level <= record.levelno < self.max_level


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Configure console + rotating-file logging for local and production runtimes."""
    level_name = (settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = []

    # --- 1. Stdout (console) ---
    # LOG_EVERYTHING_TO_CONSOLE=true drops the console handler down to DEBUG so
    # every record — including the ones that would otherwise only land in
    # app_debug.log — is also visible on stdout (e.g. via Azure Log stream).
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_CONSOLE_FMT)
    console_handler.setLevel(logging.DEBUG if settings.log_everything_to_console else level)
    handlers.append(console_handler)

    # --- 2. app.log — INFO and above ---
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    app_handler.setFormatter(_FILE_FMT)
    app_handler.setLevel(logging.INFO)
    handlers.append(app_handler)

    # --- 3. app_debug.log — DEBUG and above (only when debug mode on) ---
    if settings.debug:
        debug_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app_debug.log",
            maxBytes=settings.log_max_bytes * 2,
            backupCount=3,
            encoding="utf-8",
        )
        debug_handler.setFormatter(_FILE_FMT)
        debug_handler.setLevel(logging.DEBUG)
        handlers.append(debug_handler)

    # --- 4. app_error.log — ERROR and above (always on) ---
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app_error.log",
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=10,
        encoding="utf-8",
        delay=False,
    )
    error_handler.setFormatter(_ERROR_FMT)
    error_handler.setLevel(logging.ERROR)
    handlers.append(error_handler)

    # --- Root logger ---
    root = logging.getLogger()
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)
    # Use DEBUG as root level so debug handler can receive records when active;
    # individual handlers enforce their own min-level.
    root.setLevel(logging.DEBUG if (settings.debug or settings.log_everything_to_console) else level)

    # --- Suppress noisy third-party / infrastructure loggers ---
    # Skipped entirely when LOG_EVERYTHING_TO_CONSOLE=true — that flag means
    # "give me everything on stdout", so these stay at their own natural level
    # instead of being force-quieted to WARNING.
    if not settings.log_everything_to_console:
        _silence = {
            # SQLAlchemy engine: full SQL statements, BEGIN, ROLLBACK every few seconds
            "sqlalchemy.engine":                logging.WARNING,
            "sqlalchemy.engine.Engine":         logging.WARNING,
            "sqlalchemy.pool":                  logging.WARNING,
            "sqlalchemy.dialects":              logging.WARNING,
            # Uvicorn internal (access log handled separately, errors still show)
            "uvicorn.access":                   logging.WARNING,
            "uvicorn.error":                    logging.WARNING,
            # HTTP client libraries
            "httpx":                            logging.WARNING,
            "httpcore":                         logging.WARNING,
            "urllib3":                          logging.WARNING,
            "urllib3.connectionpool":           logging.WARNING,
            # Misc noisy libraries
            "googleapiclient.discovery_cache":  logging.WARNING,
            "multipart":                        logging.WARNING,
            "watchfiles":                       logging.WARNING,
            "asyncio":                          logging.WARNING,
            "PIL":                              logging.WARNING,
        }
        for name, lvl in _silence.items():
            logging.getLogger(name).setLevel(lvl)

    # Announce that logging is ready
    _init_logger = logging.getLogger("app.logging_config")
    _init_logger.info(
        "Logging initialised level=%s log_dir=%s debug_file=%s console_all=%s",
        level_name,
        log_dir.resolve(),
        settings.debug,
        settings.log_everything_to_console,
    )
