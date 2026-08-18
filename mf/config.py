"""Runtime configuration for Memory-Facade.

Values are resolved from environment with in-process defaults so tests can
inject them without touching the environment. Never holds secrets.
"""

from __future__ import annotations

import os

DEFAULTS = {
    "HINDSIGHT_API_URL": "https://memory.msmsoft.net",
    "HINDSIGHT_API_KEY": "",  # empty on trusted network
    "HINDSIGHT_TIMEOUT": "30",
}


def get(name: str, default: str | None = None) -> str:
    return os.environ.get(name, default if default is not None else DEFAULTS.get(name, ""))


def hindsight_api_url() -> str:
    return get("HINDSIGHT_API_URL").rstrip("/")


def hindsight_api_key() -> str:
    return get("HINDSIGHT_API_KEY")


def hindsight_timeout() -> float:
    try:
        return float(get("HINDSIGHT_TIMEOUT"))
    except ValueError:
        return 30.0
