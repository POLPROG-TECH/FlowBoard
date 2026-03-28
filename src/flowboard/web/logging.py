"""Centralized logging configuration."""

import json
import logging
import os
import sys


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extras = ""
        for key in ("request_path", "config_path", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                extras += f" {key}={val}"
        base = super().format(record)
        return f"{base}{extras}" if extras else base


class JSONFormatter(logging.Formatter):
    """Blocker #23: machine-readable JSON log format for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_path", "config_path", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def _make_formatter() -> logging.Formatter:
    """Return JSON formatter if FLOWBOARD_LOG_FORMAT=json, else structured text."""
    if os.environ.get("FLOWBOARD_LOG_FORMAT", "").lower() == "json":
        return JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    return StructuredFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"flowboard.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_make_formatter())
        logger.addHandler(handler)
    return logger


def configure_root_logger(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger("flowboard")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_make_formatter())
        root.addHandler(handler)
