"""The v1 session brick exposes no authoring operations."""
from __future__ import annotations

from typing import Any, Callable


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    del mcp, get_runtime


__all__ = ["register"]
