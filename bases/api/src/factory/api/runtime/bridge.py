"""MCP Gateway Bridge — native catalog-backed REST and in-process access.

``/api/tools/{tool_name}`` is a transport projection only: canonical naming,
aliases, validation, and suggestions are owned by the MCP aggregator. The
bridge retains dedicated health/persona reads and the in-process helpers used
by AG-UI and view actions.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from factory.mcp_utils.interface import get_tool_map, make_serializable

logger = logging.getLogger(__name__)
# Lazy-cached aggregator reference
_aggregator_server = None
_aggregator = None


def _get_mcp_server():
    """Import the MCP aggregator as in-process library (lazy singleton)."""
    global _aggregator_server
    if _aggregator_server is None:
        from factory.mcp_server.interface import get_server
        _aggregator_server = get_server()
    return _aggregator_server


def _get_aggregator():
    """Get the MCPAggregator instance (resolves all brick tools)."""
    global _aggregator
    if _aggregator is None:
        _get_mcp_server()
        from factory.mcp_server.interface import get_aggregator
        _aggregator = get_aggregator()
        # Register tool invoker so bricks can call MCP tools without
        # importing the aggregator directly (via mcp_utils registry).
        if _aggregator is not None:
            from factory.mcp_utils.interface import set_service
            set_service("tool_invoker", _aggregator.invoke_tool)
            # ActionRef needs a tool-existence + schema probe (bd:3jcls.3).
            set_service("brick_tools", _aggregator.get_brick_tools)
    return _aggregator


def _get_tools() -> dict[str, Any]:
    """Get tool map from the aggregated MCP server."""
    return get_tool_map(_get_mcp_server())


def _timeline_capabilities() -> dict[str, Any]:
    """Describe timeline support: live SSE plus optional graph history."""
    graph_backend = (
        os.environ.get("FACTORY_GRAPH_ADAPTER")
        or os.environ.get("GRAPH_BACKEND")
        or "networkx"
    ).lower()
    graph_sink_enabled = os.environ.get(
        "TELEMETRY_GRAPH_SINK", "false",
    ).lower() in ("1", "true", "yes")
    history_available = graph_sink_enabled
    if history_available:
        history_reason = None
    else:
        history_reason = "graph_sink_disabled"

    return {
        "live": {
            "available": True,
            "transport": "sse",
        },
        "history": {
            "available": history_available,
            "backend": graph_backend,
            "reason": history_reason,
        },
    }


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool by name via the aggregator.

    Uses aggregator.invoke_tool() which resolves all brick tools
    (not just the flat meta-tool map from progressive discovery).
    """
    import asyncio

    agg = _get_aggregator()
    if agg is None:
        return None
    try:
        result = agg.invoke_tool(tool_name, **arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return make_serializable(result)
    except Exception as exc:
        logger.warning("_call_tool(%s) failed: %s", tool_name, exc)
        return None


async def _extract_envelope(request: Any) -> dict | None:
    """Return a complete principal envelope from the canonical verifier."""
    from .ag_ui_identity import extract_identity

    return await extract_identity(request, _call_tool)


def register_bridge_routes(app) -> None:
    """Register generic catalog-backed tool routes and dedicated REST reads.

    Tool execution delegates canonical name resolution to the MCP aggregator;
    this transport owns no alias list or brick-specific routing.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def list_personas(request: Request) -> JSONResponse:
        """List chat personas for the FE '/' palette (bd:d4roe.3).

        Thin read passthrough to the agent brick's ``get_agent_registry``
        MCP tool via the aggregator. The agent registry is the single
        source of truth post-d4roe.1; this route does NOT re-read YAML /
        AGENTS_TYPED or own persona data (meta-architect verdict
        ``a19ef414`` Q3). Read-only GET.
        """
        result = await _call_tool("agent_get_agent_registry", {})
        data = result.get("data") if isinstance(result, dict) and result.get("ok") else result
        if isinstance(data, dict):
            personas = data.get("agents", [])
        else:
            personas = data if isinstance(data, list) else []
        return JSONResponse({"personas": personas, "count": len(personas)})

    async def gateway_health(request: Request) -> JSONResponse:
        """Aggregated health check across all registered bricks.

        Kept alive as a minimal REST survivor — ``docker-compose.yml`` and
        ``scripts/companion-x-ui.sh`` health-check against this exact path.
        """
        timeline = _timeline_capabilities()
        # Side-chat planner state (issue #41): the wiring never fails boot, so
        # a degraded side panel must be visible here, not just in the log line.
        from .side_chat_wiring import side_chat_status
        side_chat = side_chat_status()
        agg = _get_aggregator()
        if agg:
            all_tools = agg.get_all_tool_names()
            health = agg.get_aggregated_health()
            # #68: the top-level status must be computed from the brick
            # aggregate, not asserted. A brick that failed to register shows
            # up here as degraded/unhealthy bricks — readiness consumers
            # (launcher, docker-compose) watch this field. Fail closed: an
            # unexpected/missing aggregate status is not proof of health.
            status = health.get("status") if isinstance(health, dict) and health.get("status") in {"healthy", "degraded"} else "degraded"
            caps = agg.get_aggregated_capabilities()
            # Trigger view registration on first health check
            from .views import ensure_views_registered
            ensure_views_registered(agg)
            return JSONResponse({
                "gateway": "http",
                "status": status,
                "process_id": os.getpid(),
                "launch_id": os.environ.get("COMPANION_X_LAUNCH_ID", ""),
                "total_tools": len(all_tools),
                "mcp_health": make_serializable(health),
                "capabilities": make_serializable(caps),
                "timeline": timeline,
                "side_chat": side_chat,
            })
        # Fallback to flat tool map
        tools = _get_tools()
        health_fn = tools.get("health_check")
        health = health_fn() if health_fn else {"status": "unknown"}
        caps_fn = tools.get("get_capabilities")
        caps = caps_fn() if caps_fn else {}
        # #68: flat fallback mirrors the aggregate rule — trust the health
        # map's own status when it names one, else unknown is not healthy.
        status = health.get("status", "unknown") if isinstance(health, dict) else "unknown"
        return JSONResponse({
            "gateway": "http",
            "status": status,
            "process_id": os.getpid(),
            "launch_id": os.environ.get("COMPANION_X_LAUNCH_ID", ""),
            "total_tools": len(tools),
            "mcp_health": health,
            "capabilities": caps,
            "timeline": timeline,
            "side_chat": side_chat,
        })

    app.routes.extend([
        Route("/api/personas", list_personas, methods=["GET"]),
        Route("/api/health", gateway_health, methods=["GET"]),
    ])
