"""Shared logging utilities for the enclave application.

Provides a central get_logger(name) factory that ensures console + file handlers
are configured once and that log level and file path can be controlled via
environment variables LOG_LEVEL and LOG_FILE.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional


_configured = False

def _ensure_configured() -> None:
    global _configured
    if _configured:
        return

    LOG_LEVEL = os.getenv('APP_LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('APP_LOG_FILE', '')

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # File handler: only register if APP_LOG_FILE is explicitly set
    try:
        if LOG_FILE:
            log_path = Path(LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        else:
            # file logging disabled when APP_LOG_FILE is empty
            pass
    except Exception:
        root.exception('Failed to create file log handler; continuing with console only')

    # show the initial log level
    root.info(f'Logging initialized with level {LOG_LEVEL}, file={LOG_FILE or "(console only)"}')
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger for the given name.

    The first call will configure the root logger according to environment
    variables (LOG_LEVEL, LOG_FILE). Subsequent calls return regular
    loggers that inherit the same handlers/level.
    """
    _ensure_configured()
    return logging.getLogger(name)
