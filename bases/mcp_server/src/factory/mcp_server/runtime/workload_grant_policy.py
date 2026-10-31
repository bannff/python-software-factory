"""Gateway-owned authorization for exact workload capability grants."""
from __future__ import annotations

from typing import Any

_CONTROL_NAMES = frozenset({
    "call_brick_tool", "get_brick_prompts", "get_brick_resources",
    "get_brick_tools", "get_capabilities", "get_tool_catalog", "health_check",
    "list_bricks", "read_brick_resource", "render_brick_prompt",
})
_CONTROL_TERMS = frozenset({
    "authoring", "auth", "credential", "dispatcher", "health", "meta",
    "prompt", "resource", "schema", "token", "view",
})


class GatewayWorkloadGrantPolicy:
    """Approve only canonical public leaves in the live aggregator catalog."""

    def __init__(self, aggregator: Any,
                 allowed_tools: frozenset[str] | None = None) -> None:
        self._aggregator = aggregator
        self._allowed_tools = allowed_tools

    def authorize(self, grant: Any, *, tenant_id: str,
                  audience: str) -> Any | None:
        if getattr(grant, "tenant_id", None) != tenant_id:
            return None
        if getattr(grant, "audience", None) != audience:
            return None
        requested = getattr(grant, "allowed_tools", None)
        if not isinstance(requested, list) or not requested:
            return None
        if self._allowed_tools is not None and not set(requested) <= self._allowed_tools:
            return None
        return grant if all(self._admitted(name) for name in requested) else None

    def _admitted(self, name: Any) -> bool:
        if not isinstance(name, str) or not name:
            return False
        resolution = self._aggregator.resolve_tool_name(name, public_only=True)
        if not resolution.found or resolution.canonical_name != name:
            return False
        if _is_control(name, resolution.source_name or ""):
            return False
        catalog, source, error = self._aggregator.resolve_brick_tool(
            resolution.brick_name, resolution.source_name)
        if error or catalog is None or source is None:
            return False
        try:
            tool = catalog.tool_map().get(source)
        except Exception:
            return False
        category = getattr(getattr(tool, "fn", None), "_mcp_category", None)
        return category in {"deterministic", "operational"}


def _is_control(public_name: str, source_name: str) -> bool:
    lowered = public_name.lower()
    leaf = source_name.lower().replace(".", "_")
    if leaf in _CONTROL_NAMES or leaf.startswith("auth_"):
        return True
    parts = set(lowered.replace(".", "_").split("_"))
    return bool(parts & _CONTROL_TERMS)


__all__ = ["GatewayWorkloadGrantPolicy"]
