# app/logging_config.py
from __future__ import annotations
import os, sys, logging, logging.config
from pathlib import Path

def setup_logging() -> None:
    """
    Configure console + rotating file logging using dictConfig.
    Tunables via env:
      LOG_LEVEL=INFO|DEBUG|...
      LOG_FILE=logs/app.log
      LOG_MAX_BYTES=5242880 (5MB)
      LOG_BACKUPS=3
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = Path(os.getenv("LOG_FILE", "logs/app.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "5242880"))
    backups = int(os.getenv("LOG_BACKUPS", "3"))

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "rich": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "level": level,
                "formatter": "rich",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_file),
                "maxBytes": max_bytes,
                "backupCount": backups,
                "encoding": "utf-8",
                "level": "DEBUG",
                "formatter": "rich",
            },
        },
        "loggers": {
            "uvicorn.error": {"handlers": ["console", "file"], "level": level, "propagate": False},
            "uvicorn.access": {"handlers": ["console", "file"], "level": level, "propagate": False},
            "search": {"handlers": ["console", "file"], "level": level, "propagate": False},
            "fetch": {"handlers": ["console", "file"], "level": level, "propagate": False},
            "llm": {"handlers": ["console", "file"], "level": level, "propagate": False},
            "orchestrator": {"handlers": ["console", "file"], "level": level, "propagate": False},
        },
        "root": {"handlers": ["console", "file"], "level": level},
    }
    logging.config.dictConfig(config)
