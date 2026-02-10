"""Logging setup for the testbench."""
from __future__ import annotations

import logging
import sys
from typing import Any


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configure root logging with a deterministic format."""
    level_value = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if json_format:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=level_value, handlers=handlers)


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter (stdlib only)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        return _json_dumps(payload)


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, sort_keys=True)
