"""Graph storage port - Neo4j-style graph database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .common import StorageHealth


@dataclass
class GraphNode:
    """A node in the graph."""
    id: str
    labels: list[str]
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the graph."""
    id: str
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphQueryResult:
    """Result from a graph query."""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    raw: list[dict[str, Any]] = field(default_factory=list)


class GraphStore(Protocol):
    """Port: Graph database (Neo4j, NetworkX, etc.)"""

    def add_node(self, labels: list[str], properties: dict[str, Any]) -> GraphNode:
        """Add a node to the graph."""
        ...

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        ...

    def update_node(self, node_id: str, properties: dict[str, Any]) -> GraphNode | None:
        """Update node properties."""
        ...

    def delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """Add an edge between nodes."""
        ...

    def get_edges(self, node_id: str, direction: str = "both") -> list[GraphEdge]:
        """Get edges connected to a node. Direction: 'in', 'out', or 'both'."""
        ...

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        ...

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> GraphQueryResult:
        """Execute a Cypher query."""
        ...

    def health_check(self) -> StorageHealth:
        """Check graph store health."""
        ...
