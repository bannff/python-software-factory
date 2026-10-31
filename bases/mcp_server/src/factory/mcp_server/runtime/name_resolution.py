"""Canonical public tool naming and request resolution for MCP v2."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any

_ALIASES = {"ml": "machine_learning"}


@dataclass(frozen=True, slots=True)
class ToolNameResolution:
    """Resolution of one caller-visible tool name against the native catalog."""

    requested_name: str
    brick_name: str | None = None
    source_name: str | None = None
    canonical_name: str | None = None
    suggestions: tuple[str, ...] = ()
    error: str | None = None

    @property
    def found(self) -> bool:
        return self.canonical_name is not None


def canonical_tool_name(
    brick_name: str, source_name: str, *, normalize_dots: bool = True,
) -> str:
    """Return the single caller-visible name used by native MCP discovery."""
    name = (
        source_name
        if source_name.startswith((f"{brick_name}_", f"{brick_name}."))
        else f"{brick_name}_{source_name}"
    )
    return name.replace(".", "_") if normalize_dots else name


def resolve_tool_request(
    aggregator: Any, requested_name: str, *, public_only: bool = False,
) -> ToolNameResolution:
    """Resolve a request through the catalog and canonical public name map."""
    brick_name, local_name = parse_tool_name(aggregator, requested_name)
    if brick_name is None or local_name is None:
        return _missing(aggregator, requested_name)
    _catalog, source_name, error = aggregator.resolve_brick_tool(brick_name, local_name)
    if error or source_name is None:
        return _missing(aggregator, requested_name, error)
    canonical_name = canonical_tool_name(brick_name, source_name)
    if public_only and canonical_name not in aggregator.get_all_tool_names():
        return _missing(aggregator, requested_name)
    return ToolNameResolution(
        requested_name=requested_name,
        brick_name=brick_name,
        source_name=source_name,
        canonical_name=canonical_name,
    )


def parse_tool_name(aggregator: Any, tool_name: str) -> tuple[str | None, str | None]:
    """Identify the owning brick and brick-local spelling for a public name."""
    available = sorted(
        (aggregator._lazy.available_bricks if aggregator._lazy
         else aggregator._registered.keys()), key=len, reverse=True,
    )
    for brick in available:
        if tool_name.startswith(f"{brick}_") or tool_name.startswith(f"{brick}."):
            return brick, tool_name[len(brick) + 1:]
    for alias, brick in _ALIASES.items():
        if tool_name.startswith(f"{alias}_"):
            return brick, tool_name
    brick = _reverse_lookup(aggregator, tool_name) if aggregator._lazy else None
    return (brick, tool_name) if brick else (None, None)


def _missing(
    aggregator: Any, requested_name: str, error: str | None = None,
) -> ToolNameResolution:
    names = aggregator.get_all_tool_names()
    suggestions = tuple(get_close_matches(requested_name, names, n=3, cutoff=0.45))
    message = error or f"Tool '{requested_name}' was not found in the native MCP catalog"
    return ToolNameResolution(requested_name, suggestions=suggestions, error=message)


def _reverse_lookup(aggregator: Any, tool_name: str) -> str | None:
    if not hasattr(aggregator, "_t2b"):
        aggregator._t2b = {}
    if tool_name in aggregator._t2b:
        return aggregator._t2b[tool_name]
    from .lazy_loader import _get_tool_map
    from .service_policy import public_tool_map
    for brick in aggregator._lazy.available_bricks:
        catalog = aggregator._lazy.ensure_loaded(brick)
        if not catalog:
            continue
        for name in public_tool_map(_get_tool_map(catalog)):
            aggregator._t2b[name] = brick
            aggregator._t2b[canonical_tool_name(brick, name)] = brick
        if tool_name in aggregator._t2b:
            return aggregator._t2b[tool_name]
    return None


__all__ = [
    "ToolNameResolution", "canonical_tool_name", "parse_tool_name",
    "resolve_tool_request",
]
