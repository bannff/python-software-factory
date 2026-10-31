"""Shared MCP utilities with a framework-neutral native-v2 runtime seam.

Stable cross-brick contracts are exported through ``interface``. Internal
implementation modules keep narrow imports to avoid eager composition cycles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["deterministic", "operational", "authoring", "op_kind"]
_LEGACY_EXPORTS = frozenset(__all__)

if TYPE_CHECKING:
    from .interface import authoring, deterministic, op_kind, operational


def __getattr__(name: str) -> Any:
    """Resolve legacy decorator conveniences without eager transport imports."""
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import interface

    value = getattr(interface, name)
    globals()[name] = value
    return value
