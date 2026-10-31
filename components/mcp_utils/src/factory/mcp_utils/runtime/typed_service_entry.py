"""Service-entry helpers for the native MCP-v2 boundary."""
from __future__ import annotations

from typing import Any, Callable

_ENTRY = "_service_entry_authorization"
_MISSING = object()


def install_service_entry_dependency(
    wrapper: Callable[..., Any], source: Callable[..., Any],
) -> None:
    """Retained no-op: native dispatch authorizes at the service boundary."""


def pop_service_entry(kwargs: dict[str, Any]) -> object:
    return kwargs.pop(_ENTRY, _MISSING)


__all__ = ["install_service_entry_dependency", "pop_service_entry"]
