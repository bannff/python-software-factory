"""Native MCP v2 server — exposes game operations through the neutral catalog."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import get_runtime, GamesRuntime
from .mcp import deterministic, operational, authoring, resources, prompts
from .mcp.views import register as register_views


def _register_tools(registry: Any, runtime: GamesRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current)
    register_views(registry, runtime)


def create_tool_catalog(runtime: GamesRuntime | None = None) -> Any:
    """Create the transport-neutral Games tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-games")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: GamesRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for games brick."""
    return {
        "name": "games",
        "version": "1.1.0",
        "game_types": [
            "connect_four", "ctf_challenge",
            "sql_injection", "xss_hunter", "command_injection", "ssti",
            "idor_detective", "path_traversal", "finding_triage",
        ],
        "backends": ["memory", "graph"],
        "features": [
            "game_sessions", "turn_based_play", "connect_four",
            "ctf_challenge", "rl_environment", "legal_move_validation",
            "convergence_detection", "post_game_pipeline", "security_rubrics",
            "security_games", "injection_games", "access_control_games",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for games brick."""
    return {"healthy": True, "backend": "memory"}


def describe_config_schema() -> dict[str, Any]:
    """Describe games configuration schema."""
    return {
        "type": "object",
        "properties": {
            "default_game_type": {
                "type": "string",
                "enum": [
                    "connect_four", "ctf_challenge",
                    "sql_injection", "xss_hunter", "command_injection", "ssti",
                    "idor_detective", "path_traversal", "finding_triage",
                ],
            },
            "store_backend": {"type": "string", "enum": ["memory", "graph"]},
        },
    }
