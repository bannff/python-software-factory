"""MCP Prompt registration for Graph brick.

Prompts provide guided workflows for common tasks:
- Creating knowledge graphs
- Querying graph data
- Importing data into graphs
- Debugging graph issues
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import CREATE_GRAPH_TEMPLATE, QUERY_GRAPH_TEMPLATE
from .templates_import import IMPORT_DATA_TEMPLATE, DEBUG_GRAPH_TEMPLATE

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register all Graph prompts with the MCP server."""

    @mcp.prompt()
    def create_graph(
        name: str,
        description: str = "",
        backend: str = "networkx",
    ) -> str:
        """Generate guidance for creating a knowledge graph."""
        return CREATE_GRAPH_TEMPLATE.format(
            name=name,
            description=description or "A new knowledge graph for semantic relationships.",
            backend=backend,
        )

    @mcp.prompt()
    def query_graph(
        query_type: str = "neighbors",
        entity_id: str = "",
    ) -> str:
        """Generate guidance for querying the graph."""
        return QUERY_GRAPH_TEMPLATE.format(
            query_type=query_type,
            entity_id=entity_id or "your-entity-id",
        )

    @mcp.prompt()
    def import_data(
        source_format: str = "json",
        entity_type: str = "",
    ) -> str:
        """Generate guidance for importing data into the graph."""
        return IMPORT_DATA_TEMPLATE.format(
            source_format=source_format,
            entity_type=entity_type or "YourType",
        )

    @mcp.prompt()
    def debug_graph(
        issue: str = "",
        backend: str = "networkx",
    ) -> str:
        """Generate guidance for debugging graph issues."""
        return DEBUG_GRAPH_TEMPLATE.format(
            issue=issue or "Graph not behaving as expected",
            backend=backend,
        )
