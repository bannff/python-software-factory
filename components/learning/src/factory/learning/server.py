"""MCP server for the learning brick.

Public MCP surface — no domain logic. The two live tools preserve flat
wire kwargs/defaults, validate through strict local DTOs, and serialize as
versioned ToolResult envelopes; the stable native string resources describe
the reward-signal schema and runtime contract. Cross-brick adapters accept
only typed or serialized v1 success envelopes unless an explicit legacy
shape validator opts in; failures, wrong versions, and unbounded evidence
abstain. Learning inputs intentionally omit ``idempotency_key``, so these
request tools do not provide request-level replay.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import LearningRuntime, get_runtime
from .mcp import deterministic, operational, register_resources


def _register_tools(registry: Any, runtime: LearningRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)


def create_tool_catalog(runtime: LearningRuntime | None = None) -> Any:
    """Create the transport-neutral typed Learning catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-learning")
    _register_tools(catalog, runtime)
    register_resources(catalog, lambda: runtime)
    return catalog


def create_mcp_server(runtime: LearningRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for the learning brick."""
    return {
        "name": "learning",
        "version": "1.0.0",
        "features": [
            "reward_source_registry_overlay",
            "domain_agnostic_reward",
            "gt_findings_reward_source",
            "generic_fallback",
            "fastmcp_typed_contracts",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for the learning brick."""
    return {"healthy": True, "reward_sources": len(get_runtime().registry.source_ids())}


def describe_config_schema() -> dict[str, Any]:
    """Describe learning configuration schema (no config today)."""
    return {"type": "object", "additionalProperties": False, "properties": {}}


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
