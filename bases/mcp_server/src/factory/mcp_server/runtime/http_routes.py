"""HTTP routes — minimal REST survivor for the unified MCP server.

bd:python-factory-736 (mechanical consolidation track) retired this file's
REST tool-invocation routes (``GET /api/tools``, ``POST /api/tools/{name}``,
``GET /api/tools/resolve/{partial}``) — the near-duplicate of the api base's
``bridge.py`` the issue called out. Real MCP clients (the Next dashboard's
``StreamableHTTPClientTransport``) now speak ``tools/call``/``tools/list``
directly against ``/mcp``, which this composition root already mounts
(``create_app`` in ``core.py``).

Only ``GET /api/health`` remains — kept alive as a minimal, non-MCP
health-check surface. Nothing in this repo currently health-checks THIS
composition root's ``/api/health`` directly (the docker-compose.yml /
companion-x-ui.sh checks target the ``api`` base's own ``bridge.py`` route,
which is unaffected), but removing the only non-MCP liveness probe entirely
would leave any external caller of this base with no HTTP fallback at all —
matching the api base's decision to keep a minimal health surface rather
than repoint it at MCP.

Pure transport — no brick-specific logic. Delegates to the aggregator.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from factory.mcp_utils.interface import get_tool_map, make_serializable

logger = logging.getLogger(__name__)


def _timeline_capabilities() -> dict[str, Any]:
    """Describe timeline support for the frontend."""
    graph_backend = (
        os.environ.get("FACTORY_GRAPH_ADAPTER")
        or os.environ.get("GRAPH_BACKEND")
        or "networkx"
    ).lower()
    graph_sink_enabled = os.environ.get(
        "TELEMETRY_GRAPH_SINK", "false",
    ).lower() in ("1", "true", "yes")
    history_available = graph_sink_enabled
    history_reason = None if history_available else "graph_sink_disabled"

    return {
        "live": {"available": True, "transport": "sse"},
        "history": {
            "available": history_available,
            "backend": graph_backend,
            "reason": history_reason,
        },
    }


def register_http_routes(app) -> None:
    """Register the surviving ``/api/health`` route on a Starlette app instance."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from ..core import get_aggregator, get_server

    async def gateway_health(request: Request) -> JSONResponse:
        """Aggregated health check across all registered bricks."""
        timeline = _timeline_capabilities()
        agg = get_aggregator()
        if agg:
            all_tools = agg.get_all_tool_names()
            health = agg.get_aggregated_health()
            caps = agg.get_aggregated_capabilities()
            from .views import ensure_views_registered
            ensure_views_registered(agg)
            return JSONResponse({
                "gateway": "unified",
                "status": "healthy",
                "total_tools": len(all_tools),
                "mcp_health": make_serializable(health),
                "capabilities": make_serializable(caps),
                "timeline": timeline,
            })
        tools = get_tool_map(get_server())
        return JSONResponse({
            "gateway": "unified",
            "status": "healthy",
            "total_tools": len(tools),
            "mcp_health": {"status": "unknown"},
            "capabilities": {},
            "timeline": timeline,
        })

    app.routes.extend([
        Route("/api/health", gateway_health, methods=["GET"]),
    ])
