"""Deterministic MCP tools for the portable graph module."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from ._deterministic_meta import capabilities_for
from .deterministic_core import register as register_core
from .deterministic_neighborhood import register as register_neighborhood
from .deterministic_runs import register as register_runs
from .evidence import register as register_evidence
from .helper_models import CapabilitiesData, ConfigSchemaData, HealthData, HealthGraphData, NoArgsInput

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register deterministic portable Graph tools under canonical names."""

    @typed_tool(mcp)
    @deterministic(input_model=NoArgsInput, output_model=CapabilitiesData)
    def graph_get_capabilities() -> ToolResult[CapabilitiesData]:
        """Return machine-readable capabilities for portable graph APIs."""
        raw = capabilities_for(get_runtime())
        return CapabilitiesData(**raw)

    @typed_tool(mcp)
    @deterministic(input_model=NoArgsInput, output_model=HealthData)
    def graph_health_check() -> ToolResult[HealthData]:
        """Fast readiness probe for active graph backends."""
        health = get_runtime().health_check()
        graphs = {key: HealthGraphData(healthy=value.healthy, nodes=value.node_count,
                                       edges=value.edge_count) for key, value in health.items()}
        return HealthData(healthy=all(item.healthy for item in health.values()), graphs=graphs,
                          message=None if health else "No graphs initialized")

    @typed_tool(mcp)
    @deterministic(input_model=NoArgsInput, output_model=ConfigSchemaData)
    def graph_describe_config_schema() -> ToolResult[ConfigSchemaData]:
        """Describe portable graph configuration."""
        return ConfigSchemaData(type="object", required=["backend"], properties={
            "backend": {"type": "string", "description": "Graph backend to use",
                        "enum": ["persistent_networkx", "networkx", "neo4j"]},
            "uri": {"type": "string", "description": "Neo4j connection URI"},
            "user": {"type": "string", "description": "Neo4j username"},
            "password": {"type": "string", "description": "Neo4j password"},
        })

    register_core(mcp, get_runtime)
    register_neighborhood(mcp, get_runtime)
    register_evidence(mcp, get_runtime)
    register_runs(mcp, get_runtime)
