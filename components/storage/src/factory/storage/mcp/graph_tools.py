"""Typed graph storage MCP tools."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.base import EdgeData, JsonObject, NodeData
from .contracts.graph import GraphAddEdgeInput, GraphAddNodeInput, GraphDeleteEdgeInput, GraphDeleteEdgeOutput, GraphDeleteNodeInput, GraphDeleteNodeOutput, GraphEdgeOutput, GraphGetEdgesInput, GraphGetEdgesOutput, GraphGetNodeInput, GraphNodeOutput, GraphQueryInput, GraphQueryOutput, GraphUpdateNodeInput

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def _node(node: object) -> NodeData:
    return NodeData(id=node.id, labels=node.labels, properties=node.properties)


def _edge(edge: object) -> EdgeData:
    return EdgeData(id=edge.id, source_id=edge.source_id, target_id=edge.target_id, type=edge.type, properties=edge.properties)


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register graph storage tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=GraphAddNodeInput, output_model=NodeData)
    def graph_add_node(labels: list[str], properties: JsonObject | None = None) -> ToolResult[NodeData]:
        """Add a node to the graph with labels and optional properties."""
        return _node(get_runtime().get_graph_store().add_node(labels, properties or {}))

    @mcp.tool()
    @operational(input_model=GraphGetNodeInput, output_model=GraphNodeOutput)
    def graph_get_node(node_id: str) -> ToolResult[GraphNodeOutput]:
        """Get a node by ID."""
        node = get_runtime().get_graph_store().get_node(node_id)
        return GraphNodeOutput(found=node is not None, id="" if node is None else node.id, labels=[] if node is None else node.labels, properties={} if node is None else node.properties, node_id=node_id, error=None if node is not None else "not_found")

    @mcp.tool()
    @operational(input_model=GraphUpdateNodeInput, output_model=GraphNodeOutput)
    def graph_update_node(node_id: str, properties: JsonObject) -> ToolResult[GraphNodeOutput]:
        """Update node properties."""
        node = get_runtime().get_graph_store().update_node(node_id, properties)
        return GraphNodeOutput(found=node is not None, id="" if node is None else node.id, labels=[] if node is None else node.labels, properties={} if node is None else node.properties, node_id=node_id, error=None if node is not None else "not_found")

    @mcp.tool()
    @operational(input_model=GraphDeleteNodeInput, output_model=GraphDeleteNodeOutput)
    def graph_delete_node(node_id: str) -> ToolResult[GraphDeleteNodeOutput]:
        """Delete a node from the graph."""
        return GraphDeleteNodeOutput(deleted=get_runtime().get_graph_store().delete_node(node_id), node_id=node_id)

    @mcp.tool()
    @operational(input_model=GraphAddEdgeInput, output_model=GraphEdgeOutput)
    def graph_add_edge(source_id: str, target_id: str, edge_type: str, properties: JsonObject | None = None) -> ToolResult[GraphEdgeOutput]:
        """Add an edge between two nodes."""
        return _edge(get_runtime().get_graph_store().add_edge(source_id, target_id, edge_type, properties))

    @mcp.tool()
    @operational(input_model=GraphGetEdgesInput, output_model=GraphGetEdgesOutput)
    def graph_get_edges(node_id: str, direction: str = "both") -> ToolResult[GraphGetEdgesOutput]:
        """Get edges connected to a node. Direction: 'in', 'out', or 'both'."""
        edges = get_runtime().get_graph_store().get_edges(node_id, direction)
        return GraphGetEdgesOutput(edges=[_edge(item) for item in edges], count=len(edges))

    @mcp.tool()
    @operational(input_model=GraphDeleteEdgeInput, output_model=GraphDeleteEdgeOutput)
    def graph_delete_edge(edge_id: str) -> ToolResult[GraphDeleteEdgeOutput]:
        """Delete an edge from the graph."""
        return GraphDeleteEdgeOutput(deleted=get_runtime().get_graph_store().delete_edge(edge_id), edge_id=edge_id)

    @mcp.tool()
    @operational(input_model=GraphQueryInput, output_model=GraphQueryOutput)
    def graph_query(cypher: str, params: JsonObject | None = None) -> ToolResult[GraphQueryOutput]:
        """Execute a Cypher query against the graph store."""
        result = get_runtime().get_graph_store().query(cypher, params)
        return GraphQueryOutput(nodes=[_node(item) for item in result.nodes], edges=[_edge(item) for item in result.edges], raw=result.raw)
