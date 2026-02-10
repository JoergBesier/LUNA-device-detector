"""Configuration loading utilities."""
from __future__ import annotations

import json
import pathlib
import tomllib
from typing import Any


class ConfigError(RuntimeError):
    """Raised when configuration loading fails."""


def load_config(path: str | pathlib.Path) -> dict[str, Any]:
    """Load a configuration file (TOML or JSON).

    This stays dependency-free to keep offline-first setups lightweight.
    """
    path_obj = pathlib.Path(path)
    if not path_obj.exists():
        raise ConfigError(f"Config path does not exist: {path_obj}")

    suffix = path_obj.suffix.lower()
    if suffix == ".toml":
        with path_obj.open("rb") as handle:
            return tomllib.load(handle)
    if suffix == ".json":
        with path_obj.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    raise ConfigError(f"Unsupported config format: {path_obj.suffix}")
