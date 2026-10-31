"""Core MCP Server — unified entry point aggregating all brick servers."""
from __future__ import annotations

import logging
import os
from typing import Any

from .runtime.aggregator import MCPAggregator
from .runtime.brick_selection import (
    DEFAULT_EXCLUDE, parse_brick_list, resolve_brick_names as _resolve_brick_names,
)

logger = logging.getLogger(__name__)


def get_config() -> dict[str, Any]:
    """Load configuration from environment variables."""
    discovery_mode = os.environ.get("MCP_DISCOVERY_MODE", "progressive")
    if discovery_mode not in {"progressive", "flat"}:
        raise ValueError("MCP_DISCOVERY_MODE must be 'progressive' or 'flat'")
    return {
        "server_name": os.environ.get("MCP_SERVER_NAME", "factory-app"),
        "include_bricks": os.environ.get("MCP_INCLUDE_BRICKS", ""),
        "exclude_bricks": os.environ.get("MCP_EXCLUDE_BRICKS", ""),
        "discovery_mode": discovery_mode,
    }


def _initialize_telemetry(
    aggregator: MCPAggregator, *, required: bool,
) -> None:
    """Install and verify Telemetry before any Agent/Graph brick is loaded."""
    try:
        from factory.mcp_utils.interface import set_caller_hint
        set_caller_hint("system:telemetry-init")
        try:
            aggregator.get_brick_tools("telemetry")
            from factory.telemetry.interface import health_check
            health = health_check()
        finally:
            set_caller_hint(None)
        if not health.get("ok"):
            raise RuntimeError(f"Telemetry is unhealthy: {health}")
        logger.info("Telemetry provider/exporter healthy: %s", health)
    except Exception as exc:
        if required:
            raise RuntimeError("Companion-X requires healthy Telemetry") from exc
        logger.warning("Telemetry brick not available — spans disabled: %s", exc)


def _warmup_ui_bricks(
    aggregator: MCPAggregator, ui_bricks: list[str], available: list[str],
) -> None:
    """Eagerly load UI-critical bricks to avoid cold-start timeouts in Companion-X."""
    from factory.mcp_utils.interface import set_caller_hint

    available_set = set(available)
    loaded, failed = 0, 0
    token = set_caller_hint("system:warmup")
    try:
        for name in ui_bricks:
            if name not in available_set:
                continue
            try:
                aggregator.get_brick_tools(name)
                loaded += 1
            except Exception as exc:
                logger.warning("UI-critical brick '%s' failed to warm: %s", name, exc)
                failed += 1
    finally:
        set_caller_hint(None)
    logger.info("UI brick warmup: %d loaded, %d failed", loaded, failed)


_server: Any | None = None
_aggregator: MCPAggregator | None = None


def create_configured_native_server(
    allowlist: set[str] | None = None,
) -> Any:
    """Create the configured native-v2 process surface and generated plan."""
    config = get_config()
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(_resolve_brick_names(config))
    from factory.mcp_utils.interface import set_service
    from .runtime.workload_grant_policy import GatewayWorkloadGrantPolicy
    set_service("workload_grant_policy", GatewayWorkloadGrantPolicy(aggregator))
    from .runtime.native_invoker import NativeEnvelopeInvoker
    invoker = NativeEnvelopeInvoker(aggregator)
    set_service("tool_invoker", aggregator.invoke_tool)
    set_service("tool_invoker_envelope", invoker)
    set_service("tool_invoker_for_caller", invoker.for_caller)
    set_service("brick_tools", aggregator.get_brick_tools)
    from .runtime import graph_sink
    graph_sink.set_aggregator(aggregator)
    set_service("tool_invocation_sink", graph_sink.materialize)
    telemetry_required = (
        config["server_name"] == "companion-x"
        or os.environ.get("TELEMETRY_REQUIRED", "").lower() in {"1", "true", "yes"}
    )
    if config["discovery_mode"] == "flat":
        _initialize_telemetry(aggregator, required=telemetry_required)
    from .runtime.native_v2_bootstrap import build_configured_native_server
    from .runtime.access_control import build_access_components
    access_controller, token_verifier = build_access_components()
    set_service("mcp_access_controller", access_controller)
    set_service("mcp_token_verifier", token_verifier)
    server, _plan = build_configured_native_server(
        aggregator, server_name=config["server_name"],
        discovery_mode=config["discovery_mode"], allowlist=allowlist,
        access_controller=access_controller,
    )
    aggregator.mcp = server
    global _server, _aggregator
    _server, _aggregator = server, aggregator
    return server


def create_native_server(plan: Any, allowlist: set[str] | None = None) -> Any:
    """Create the one native MCP-v2 server from neutral brick catalogs."""
    config = get_config()
    brick_names = _resolve_brick_names(config)
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(brick_names)

    global _server, _aggregator
    _aggregator = aggregator

    from .runtime.native_v2_view import build_native_v2_view
    _server = build_native_v2_view(aggregator, plan, allowlist)
    return _server


def create_server() -> Any:
    """Create the sole configured native MCP-v2 server."""
    return create_configured_native_server()


def get_server() -> Any:
    """Get or create the global server instance."""
    global _server
    if _server is None:
        _server = create_server()
    return _server


def get_aggregator() -> MCPAggregator | None:
    """Get the global aggregator instance (available after get_server())."""
    return _aggregator


def create_app():
    """Create a unified Starlette app with MCP + REST + SSE + AG-UI routes."""
    server = get_server()
    from .runtime.native_v2_http import build_streamable_http_app
    from .runtime.access_control import auth_settings
    from factory.mcp_utils.interface import get_service
    local = os.environ.get("MCP_LOCAL_AUTH", "").lower() in {"1", "true", "yes"}
    host = "127.0.0.1" if local else os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    app = build_streamable_http_app(
        server, path="/mcp", auth=auth_settings(),
        token_verifier=get_service("mcp_token_verifier"), host=host,
    )

    from .runtime.http_routes import register_http_routes
    from .runtime.sse_routes import register_sse_routes
    from .runtime.ag_ui_routes import register_ag_ui_routes

    register_http_routes(app)
    register_sse_routes(app)
    register_ag_ui_routes(app)

    return app


def main() -> None:
    """Run the aggregated native MCP-v2 server over stdio."""
    import asyncio
    from mcp.server.stdio import stdio_server

    async def serve() -> None:
        server = get_server()
        async with stdio_server() as streams:
            await server.run(*streams, server.create_initialization_options())

    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(serve())
    finally:
        from .runtime.pools import shutdown_pools
        shutdown_pools()


if __name__ == "__main__":
    main()
