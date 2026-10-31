"""Tool-existence probe for :mod:`~.actions` validation (bd:3jcls.3).

``ActionRef`` validation wants to know whether ``(brick, tool)`` actually
resolves, so a typo fails at view-ingestion time instead of at the user's
click. The ui brick cannot import the aggregator (tenet 4), so the API base
registers ``agg.get_brick_tools`` as the ``brick_tools`` service alongside the
existing ``tool_invoker`` (``bases/api/.../bridge.py``); this module reads it
back out of the registry.

Alias handling mirrors ``resolve_tool_name``
(``bases/mcp_server/runtime/tool_dispatch.py:14``) plus one extra form the
aggregator's ``_parse_tool_name`` accepts and 18 live brick views rely on:
the brick-prefixed string (``cache_cache_get``) whose local map key is
``cache_get``. All four forms are probed so legacy declarations resolve
without any brick edit.
"""

from __future__ import annotations

from typing import Any

#: Result of a successful probe: the brick-local tool key and its schema.
ProbeResult = "tuple[str, dict[str, Any]]"


def candidate_names(brick: str, tool: str) -> list[str]:
    """Every accepted spelling of ``tool`` as a brick-local map key."""
    names = [tool, f"{brick}_{tool}", f"{brick}.{tool}"]
    for sep in ("_", "."):
        prefix = f"{brick}{sep}"
        if tool.startswith(prefix):
            names.append(tool[len(prefix):])
    return names


def qualified_name(brick: str, local: str) -> str:
    """Build the name ``aggregator.invoke_tool`` will parse back to ``brick``."""
    if local.startswith((f"{brick}_", f"{brick}.")):
        return local
    return f"{brick}_{local}"


def build_tool_resolver():
    """Return a ``(brick, tool) -> (local_name, input_schema) | None`` probe.

    Returns ``None`` when the ``brick_tools`` service is unregistered (gateway
    not initialized, or a unit test with no aggregator). Callers treat that as
    "skip existence validation" rather than "refuse every action" — a missing
    probe must not turn every view into an error page.
    """
    from factory.mcp_utils.interface import get_service

    brick_tools = get_service("brick_tools")
    if brick_tools is None:
        return None

    def _resolve(brick: str, tool: str) -> tuple[str, dict[str, Any]] | None:
        try:
            listing = brick_tools(brick)
        except Exception:  # noqa: BLE001 — a probe must never raise
            return None
        tools = listing.get("tools") if isinstance(listing, dict) else None
        if not isinstance(tools, list):
            return None
        by_name = {
            entry["name"]: entry.get("input_schema") or {}
            for entry in tools
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        }
        for candidate in candidate_names(brick, tool):
            if candidate in by_name:
                return candidate, by_name[candidate]
        return None

    return _resolve
