"""Polylith Interface for mcp_server base.

This module exposes the public API for the MCP server aggregator.
"""
from __future__ import annotations

from typing import Any

from .core import (
    create_server, create_native_server, create_configured_native_server,
    main, get_server, get_aggregator, create_app,
)
from .runtime import BrickDiscovery, BrickInfo, MCPAggregator

# Alias for backward compatibility
create_mcp_server = create_server


def set_workflow_run_id(run_id: str | None) -> None:
    """Public facade for graph_sink.set_workflow_run_id.

    Lazy resolution so test patches against
    factory.mcp_server.runtime.graph_sink.set_workflow_run_id still apply.
    Re-binding at import time would defeat those patches and let production
    code mutate real module state during tests.
    """
    from .runtime.graph_sink import set_workflow_run_id as _impl
    _impl(run_id)


def get_workflow_run_id() -> str | None:
    """Public facade for graph_sink.get_workflow_run_id.

    Same lazy-resolution pattern as set_workflow_run_id so tests can patch
    the runtime module's accessor without breaking production callers that
    import via the interface.
    """
    from .runtime.graph_sink import get_workflow_run_id as _impl
    return _impl()


def get_native_v2_selected_registrations(
    allowlist: set[str] | None = None,
    *,
    rename_dot_to_underscore: bool = True,
) -> tuple[Any, ...]:
    """Return exact typed registrations for the future native-v2 composer.

    This is deliberately a planning seam: the active MCP v1/FastMCP surface
    still owns resources, prompts, and transport. It lets the native composer
    receive the same selected handlers at the dependency cutover without a
    second registry or direct brick imports.
    """
    from .runtime.selected_tools import native_registrations, resolve_selected_tools

    get_server()
    aggregator = get_aggregator()
    if aggregator is None:
        raise RuntimeError("MCP aggregator is not initialized")
    selected = resolve_selected_tools(
        aggregator, allowlist, rename_dot_to_underscore=rename_dot_to_underscore,
    )
    return native_registrations(selected)


def get_native_v2_view(
    plan: Any,
    allowlist: set[str] | None = None,
    *,
    rename_dot_to_underscore: bool = True,
) -> Any:
    """Compose selected gateway handlers as a public native MCP-v2 server.

    This v2-only factory intentionally has no FastMCP fallback.  The active
    transport remains unchanged until the published dependency closure can
    resolve MCP v2; then this is the gateway activation seam.
    """
    from .runtime.native_v2_view import build_native_v2_view

    get_server()
    aggregator = get_aggregator()
    if aggregator is None:
        raise RuntimeError("MCP aggregator is not initialized")
    return build_native_v2_view(
        aggregator,
        plan,
        allowlist,
        rename_dot_to_underscore=rename_dot_to_underscore,
    )


def get_brick_tool_map(brick: str) -> dict[str, Any] | None:
    """Return one loaded brick's neutral name-to-tool map."""
    get_server()
    aggregator = get_aggregator()
    if aggregator is None or aggregator._lazy is None:
        return None
    catalog = aggregator._lazy.ensure_loaded(brick)
    return None if catalog is None else catalog.tool_map()


def get_op_kind_lookup() -> dict[str, str]:
    """Return the ``tool_name -> op_kind`` lookup (bd:python-factory-rk4hc).

    Built by introspecting each loaded brick tool's ``_mcp_op_kind`` trait
    (set via ``factory.mcp_utils.interface.op_kind``) plus a name-keyed seed
    for non-MCP ``strands_tools`` (``shell`` / ``python_repl`` → ``shell``).
    The chat adapter reads this to populate ``ToolCallDeltaEvent.op_kind``,
    which the ui mapper stamps as camelCase ``opKind`` for the IDE terminal
    mirror. Keyed by both brick-native and dot→underscore-normalised names.
    """
    from .runtime.op_kind_lookup import build_op_kind_lookup as _impl
    return _impl()


def get_tool_catalog(categories: list[str] | None = None) -> dict[str, Any]:
    """Return the whole-registry tool catalog (bd:3jcls.4)."""
    from .runtime.tool_catalog import build_tool_catalog as _impl
    return _impl(get_aggregator(), categories)


def build_streamable_http_app(server: Any, path: str = "/") -> Any:
    """Expose the authenticated native Streamable HTTP app."""
    import os
    from factory.mcp_utils.interface import get_service
    from .runtime.access_control import auth_settings
    from .runtime.native_v2_http import build_streamable_http_app as _impl

    local = os.environ.get("MCP_LOCAL_AUTH", "").lower() in {"1", "true", "yes"}
    host = "127.0.0.1" if local else os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    return _impl(
        server, path=path, auth=auth_settings(),
        token_verifier=get_service("mcp_token_verifier"), host=host,
    )


def resolve_public_mcp_names(requested: list[str]) -> frozenset[str]:
    """Canonicalize public MCP declarations or fail closed on any miss."""
    get_server()
    aggregator = get_aggregator()
    if aggregator is None:
        raise RuntimeError("MCP aggregator is not initialized")
    from .runtime.scoped_surface import resolve_public_names
    return resolve_public_names(aggregator, requested)


def create_exact_flat_native_scope(
    tool_names: set[str] | None = None, *, parent_scope: Any | None = None,
    policy_id: str = "companion-x-agent",
) -> tuple[Any, Any]:
    """Build one exact admitted native server plus canonical trusted scope.

    ``None`` means all admitted names at a root and the parent's exact names
    for delegation. An explicit empty set always remains empty.
    """
    get_server()
    aggregator = get_aggregator()
    if aggregator is None:
        raise RuntimeError("MCP aggregator is not initialized")
    from .runtime.scoped_surface import create_exact_flat_surface
    return create_exact_flat_surface(
        aggregator, tool_names, policy_id=policy_id, parent_scope=parent_scope,
    )


__all__ = [
    "create_server",
    "create_mcp_server",
    "create_app",
    "get_server",
    "get_aggregator",
    "main",
    "BrickDiscovery",
    "BrickInfo",
    "MCPAggregator",
    "set_workflow_run_id",
    "get_workflow_run_id",
    "get_native_v2_selected_registrations",
    "get_native_v2_view",
    "get_brick_tool_map",
    "get_op_kind_lookup",
    "get_tool_catalog",
    "build_streamable_http_app",
    "resolve_public_mcp_names",
    "create_exact_flat_native_scope",
]
