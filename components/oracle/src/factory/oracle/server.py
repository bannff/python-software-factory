"""MCP server for the oracle brick.

Public MCP surface — no domain logic. Delegates tool registration to the
``mcp/`` subpackage and exposes the standard brick contract functions.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import OracleRuntime, get_runtime
from .mcp import deterministic, operational, authoring
from .mcp import register_resources, register_prompts


def _register_tools(registry: Any, runtime: OracleRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current)


def create_tool_catalog(runtime: OracleRuntime | None = None) -> Any:
    """Create the transport-neutral typed Oracle catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-oracle")
    _register_tools(catalog, runtime)

    def _get_runtime() -> OracleRuntime:
        return runtime

    register_resources(catalog, _get_runtime)
    register_prompts(catalog, _get_runtime)
    return catalog


def create_mcp_server(runtime: OracleRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for the oracle brick."""
    return {
        "name": "oracle",
        "version": "1.0.0",
        "features": [
            "finding_verification",
            "verifier_registry_overlay",
            "generic_fallback",
            "domain_agnostic_dispatch",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for the oracle brick."""
    return {"healthy": True, "verifiers": len(get_runtime().registry.domains())}


def describe_config_schema() -> dict[str, Any]:
    """Describe oracle configuration schema (no config today)."""
    return {"type": "object", "additionalProperties": False, "properties": {}}


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
