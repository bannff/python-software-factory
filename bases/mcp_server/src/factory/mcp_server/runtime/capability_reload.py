"""One 'Reload capabilities' fan-out: bricks, Agent registries, external servers.

No process restart: invalidates every loaded brick catalog (next call re-imports
it), reloads the Agent's persona/skill/graph/tool registries through its own
``reload_config`` tool, and re-discovers owner-registered external MCP servers
through the connections brick. Each part reports independently so one failure
never hides the others.
"""
from __future__ import annotations

import inspect
from typing import Any


async def reload_capabilities(aggregator: Any) -> dict[str, Any]:
    outcome: dict[str, Any] = {"bricks": {}, "agent": None, "connections": None}
    lazy = getattr(aggregator, "_lazy", None)
    for name in list(getattr(aggregator, "_registered", {})):
        namespace = aggregator._registered[name].namespace
        if namespace.startswith("external."):
            continue  # remounted below through the connections brick
        if lazy is not None:
            lazy.invalidate(name)
            outcome["bricks"][name] = "invalidated"
        else:
            outcome["bricks"][name] = "reloaded" if aggregator.reload_brick(name).get("success") else "failed"
    outcome["agent"] = await _call(aggregator, "agent", "reload_config", {})
    outcome["connections"] = await _call(aggregator, "connections", "connections_reload", {})
    return outcome


async def _call(aggregator: Any, brick: str, tool: str, arguments: dict[str, Any]) -> str:
    try:
        raw = aggregator.call_brick_tool(brick, tool, arguments)
        result = await raw if inspect.isawaitable(raw) else raw
    except Exception as exc:  # noqa: BLE001 - reported, never raised across parts
        return f"error:{type(exc).__name__}"
    structured = result.get("result", {}).get("structured_content") if isinstance(result, dict) else None
    if isinstance(structured, dict) and structured.get("ok") is True:
        return "reloaded"
    error = structured.get("error") if isinstance(structured, dict) else None
    return f"error:{error or 'unavailable'}"


__all__ = ["reload_capabilities"]
