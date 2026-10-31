"""Select exact brick tools for legacy and native MCP server composition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factory.mcp_utils.interface import NativeToolRegistration

from .public_admission import project_public_tools


@dataclass(frozen=True, slots=True)
class SelectedTool:
    """One selected tool with its public name and native-v2 registration."""

    brick: str
    source_name: str
    public_name: str
    tool: Any

    def native_registration(self) -> NativeToolRegistration:
        """Adapt an existing typed brick handler without revalidating it."""
        handler = getattr(self.tool, "fn", None)
        if not callable(handler):
            raise TypeError(f"{self.source_name} has no callable typed handler")
        description = str(getattr(self.tool, "description", "") or "")
        return NativeToolRegistration(
            self.public_name, description, handler,
            brick_name=self.brick, source_name=self.source_name,
        )


def resolve_selected_tools(
    aggregator: Any,
    allowlist: set[str] | None,
    *,
    rename_dot_to_underscore: bool,
) -> tuple[SelectedTool, ...]:
    """Resolve exact requested tools from lazy brick maps in stable order.

    ``None`` retains the all-tools view. An empty set remains a strict empty
    scope. Both source and normalised public names are accepted in an
    allowlist so existing dot-name callers remain compatible.
    """
    lazy = aggregator._lazy
    if lazy is None or allowlist == set():
        return ()
    selected: list[tuple[str, dict[str, Any]]] = []
    for brick in _resolve_bricks(lazy.available_bricks, allowlist):
        server = lazy.ensure_loaded(brick)
        if server is not None:
            selected.append((brick, lazy.get_cached_tool_map(brick, server)))
    projection = project_public_tools(
        selected, allowlist=allowlist,
        normalize_dots=rename_dot_to_underscore,
    )
    if projection.invalid_tools:
        reasons = ",".join(sorted({item["reason"] for item in projection.invalid_tools}))
        raise ValueError(f"invalid public tool declarations: {reasons}")
    return tuple(
        SelectedTool(
            item.brick, item.source_name, item.public_name, item.tool,
        )
        for item in projection.admitted
    )


def native_registrations(selected: tuple[SelectedTool, ...]) -> tuple[NativeToolRegistration, ...]:
    """Return native registrations from the same selected-tool decision."""
    return tuple(item.native_registration() for item in selected)


def _resolve_bricks(available: list[str], allowlist: set[str] | None) -> list[str]:
    if allowlist is None:
        return list(available)
    needed = {
        brick for tool_name in allowlist
        for brick in available
        if tool_name.startswith(f"{brick}_") or tool_name.startswith(f"{brick}.")
    }
    return sorted(needed)


__all__ = ["SelectedTool", "native_registrations", "resolve_selected_tools"]
