"""Config core - high-level convenience functions."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import get_runtime


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from the default config."""
    return get_runtime().get_config().get(key, default)


def get_config_int(key: str, default: int = 0) -> int:
    """Get a configuration value as an integer."""
    return get_runtime().get_config().get_typed(key, int, default)


def get_config_bool(key: str, default: bool = False) -> bool:
    """Get a configuration value as a boolean."""
    return get_runtime().get_config().get_typed(key, bool, default)


def set_config(key: str, value: Any) -> bool:
    """Set a configuration value in the default config."""
    return get_runtime().get_config().set(key, value)


def get_environment() -> str:
    """Get the current environment."""
    return get_runtime().environment
