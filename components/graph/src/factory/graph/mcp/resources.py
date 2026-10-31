"""Native MCP resources for the portable Graph brick."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

from .docs import GRAPH_DOCS
from .docs_security_taxonomy import SECURITY_TAXONOMY
from .docs_taxonomy import GRAPH_TAXONOMY

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register portable Graph schemas, documentation, and live resources."""
    @mcp.resource("graph://schemas/node")
    def node_schema() -> str:
        return json.dumps({"type": "object", "properties": {"id": {"type": "string"},
                          "type": {"type": "string"}, "properties": {"type": "object"},
                          "labels": {"type": "array", "items": {"type": "string"}}},
                           "required": ["id", "type"]}, indent=2)

    @mcp.resource("graph://schemas/edge")
    def edge_schema() -> str:
        return json.dumps({"type": "object", "properties": {"id": {"type": "string"},
                          "type": {"type": "string"}, "source_id": {"type": "string"},
                          "target_id": {"type": "string"}, "properties": {"type": "object"}},
                           "required": ["id", "type", "source_id", "target_id"]}, indent=2)

    @mcp.resource("graph://schemas/taxonomy")
    def taxonomy() -> str:
        return json.dumps(GRAPH_TAXONOMY, indent=2)

    @mcp.resource("graph://schemas/security-taxonomy")
    def security_taxonomy() -> str:
        return json.dumps(SECURITY_TAXONOMY, indent=2)

    @mcp.resource("graph://schemas/taxonomy/{domain}")
    def domain_taxonomy(domain: str) -> str:
        from ..runtime.taxonomy_registry import get_extensions, resolve_domain_taxonomy
        result = resolve_domain_taxonomy(domain)
        return json.dumps(result if result is not None else {"error": f"Domain '{domain}' not registered",
                          "available_domains": ["security", *get_extensions().keys()]}, indent=2)

    @mcp.resource("graph://docs/overview")
    def docs_overview() -> str:
        return GRAPH_DOCS["overview"]["content"]

    @mcp.resource("graph://docs/adapters")
    def docs_adapters() -> str:
        return GRAPH_DOCS["adapters"]["content"]

    @mcp.resource("graph://stats")
    def stats() -> str:
        health = get_runtime().health_check()
        return json.dumps({"graphs": {name: {"healthy": item.healthy, "node_count": item.node_count,
                           "edge_count": item.edge_count, "latency_ms": item.latency_ms}
                           for name, item in health.items()}, "total_graphs": len(health)}, indent=2)

    @mcp.resource("graph://backends")
    def backends() -> str:
        return json.dumps({"backends": [{"name": "networkx", "persistent": False},
                          {"name": "persistent_networkx", "persistent": True},
                          {"name": "neo4j", "persistent": True}],
                          "available": get_runtime().available_backends(),
                          "provenance": get_runtime().provenance_backends()}, indent=2)

    @mcp.resource("graph://factory")
    def factory_ref() -> str:
        return json.dumps({"message": "Use foreman tools for workspace operations",
                          "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"]}, indent=2)
