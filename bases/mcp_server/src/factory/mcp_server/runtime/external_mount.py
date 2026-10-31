"""Mount synthetic catalogs (external MCP servers) as gateway pseudo-bricks.

Same admission, scoping, approval, and telemetry path as module bricks; only
the importlib load is skipped because there is no module to import.
"""
from __future__ import annotations

from typing import Any

from .aggregator import BrickRegistration


def register_external(aggregator: Any, brick_name: str, catalog: Any) -> bool:
    if not callable(getattr(catalog, "tool_map", None)):
        raise TypeError("external catalog must expose tool_map()")
    from .lazy_loader import _count_tools
    registration = BrickRegistration(
        brick_name, f"external.{brick_name}", _count_tools(catalog, brick_name), True,
    )
    lazy = aggregator._lazy
    if lazy is not None:
        lazy.invalidate(brick_name)
        lazy._cache[brick_name] = catalog
        if brick_name not in lazy._available:
            lazy._available.append(brick_name)
        lazy._registrations[brick_name] = registration
    else:
        aggregator._flat_bricks[brick_name] = catalog
    aggregator._registered[brick_name] = registration
    return True


def unregister_external(aggregator: Any, brick_name: str) -> bool:
    present = brick_name in aggregator._registered
    lazy = aggregator._lazy
    if lazy is not None:
        lazy.invalidate(brick_name)
        lazy._registrations.pop(brick_name, None)
        if brick_name in lazy._available:
            lazy._available.remove(brick_name)
    aggregator._flat_bricks.pop(brick_name, None)
    aggregator._registered.pop(brick_name, None)
    return present


__all__ = ["register_external", "unregister_external"]
