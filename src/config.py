"""Load and validate config from settings.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_settings() -> dict[str, Any]:
    """Load main settings.yaml config."""
    settings_path = CONFIG_DIR / "settings.yaml"
    if not settings_path.exists():
        raise FileNotFoundError(
            f"Config not found at {settings_path}. "
            "Copy settings.example.yaml to settings.yaml and fill in your keys."
        )
    with open(settings_path) as f:
        return yaml.safe_load(f)


def load_vertical(name: str) -> dict[str, Any]:
    """Load vertical-specific config overrides."""
    vertical_path = CONFIG_DIR / "verticals" / f"{name}.yaml"
    if not vertical_path.exists():
        return {}
    with open(vertical_path) as f:
        return yaml.safe_load(f) or {}


def get_api_key(settings: dict[str, Any], key_name: str) -> str:
    """Get an API key from settings, raise if missing."""
    key = settings.get("apis", {}).get(key_name, "")
    if not key:
        raise ValueError(
            f"API key '{key_name}' not set in config/settings.yaml"
        )
    return key
