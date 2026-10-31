"""Register typed tools on the framework-neutral catalog."""

from __future__ import annotations

from typing import Any, Callable


def typed_tool(
    registry: Any, *, name: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a category-decorated handler on a neutral catalog."""
    return registry.tool(name=name)


__all__ = ["typed_tool"]
