"""FastMCP server interface exposing security tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .runtime.runtime import SecurityRuntime
from .mcp import deterministic, operational, authoring, register_resources, register_prompts
from .mcp.views import register as register_views


def _default_runtime() -> SecurityRuntime:
    import os
    adapter_name = os.environ.get("FACTORY_SECURITY_ADAPTER", "mock")
    if adapter_name == "bandit":
        from .runtime.adapters.bandit_adapter import BanditAnalyzerAdapter
        analyzer = BanditAnalyzerAdapter()
    else:
        from .runtime.adapters.mock import MockAnalyzerAdapter
        analyzer = MockAnalyzerAdapter()
    llm = None
    try:
        from factory.llm_gateway.interface import get_runtime as get_llm_runtime
        llm = get_llm_runtime().get_provider()
    except Exception:
        pass
    persistence = None
    from factory.mcp_utils.config_helpers import get_infra
    if get_infra("security.persistence", "memory") == "graph":
        try:
            from .runtime.adapters.graph_persistence import GraphFindingPersistence
            persistence = GraphFindingPersistence()
        except Exception:
            pass
    return SecurityRuntime(analyzer, llm=llm, persistence=persistence)


def _register_tools(
    registry: Any, runtime: SecurityRuntime, config_dir: Path | None,
    pentest_runtime: Any | None = None,
) -> Any:
    enabled = authoring_enabled()
    manager = AuthoringManager(config_dir or Path.cwd()) if enabled else None
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime, manager)
    from .runtime.pentest import PentestRuntime
    from .mcp import pentest_tools
    pentest_runtime = pentest_runtime or PentestRuntime()
    pentest_tools.register(registry, pentest_runtime)
    register_views(registry)
    _auto_seed_taxonomies()
    _register_oracle_verifier()
    return pentest_runtime


def create_tool_catalog(
    runtime: SecurityRuntime | None = None, config_dir: Path | None = None,
) -> Any:
    """Create the transport-neutral Security tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or _default_runtime()
    catalog = ToolCatalog("security-module")
    pentest_runtime = _register_tools(catalog, active_runtime, config_dir)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    from .mcp import pentest_resources
    pentest_resources.register(catalog, pentest_runtime)
    return catalog


def create_mcp_server(
    runtime: SecurityRuntime | None = None, config_dir: Path | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, config_dir)


def _register_oracle_verifier() -> None:
    """Best-effort registration of the security verifier into the oracle."""
    try:
        from factory.security.runtime.adapters.oracle_verifier import (
            register_security_verifier,
        )
        register_security_verifier()
    except Exception:
        pass  # Oracle brick may not be available


def _auto_seed_taxonomies() -> None:
    """Best-effort taxonomy seeding on startup."""
    try:
        from factory.security.runtime.cwe_taxonomy import seed_cwe_taxonomy
        seed_cwe_taxonomy()
    except Exception:
        pass  # Graph may not be available yet
    try:
        from factory.security.runtime.ocsf_taxonomy import seed_ocsf_taxonomy
        seed_ocsf_taxonomy()
    except Exception:
        pass  # Graph may not be available yet


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for security brick."""
    return {
        "name": "security",
        "version": "0.1.0",
        "adapters": ["threat_modeling", "code_analysis", "pen_testing", "recon", "mock"],
        "features": [
            "threat_modeling",
            "code_analysis",
            "penetration_testing",
            "reconnaissance",
            "vulnerability_scanning",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for security brick."""
    import os
    adapter = os.environ.get("FACTORY_SECURITY_ADAPTER", "mock")
    return {"healthy": True, "adapter": adapter}


def describe_config_schema() -> dict[str, Any]:
    """Describe security configuration schema."""
    return {
        "type": "object",
        "properties": {
            "max_findings": {"type": "integer", "default": 100},
            "include_info": {"type": "boolean", "default": False},
            "timeout_seconds": {"type": "integer", "default": 300},
        },
    }
