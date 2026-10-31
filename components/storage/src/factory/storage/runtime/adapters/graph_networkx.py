"""NetworkX graph storage adapter (in-memory)."""

from __future__ import annotations

import importlib.util
import time
import uuid
from typing import Any

from factory.storage.runtime.ports import GraphNode, GraphEdge, GraphQueryResult, StorageHealth

NETWORKX_AVAILABLE = importlib.util.find_spec("networkx") is not None


def _require_networkx() -> None:
    if not NETWORKX_AVAILABLE:
        raise ImportError("networkx required. Install with: pip install networkx")


class NetworkXGraphStore:
    """NetworkX implementation of GraphStore port (in-memory)."""

    def __init__(self) -> None:
        _require_networkx()
        import networkx as nx
        self._graph = nx.DiGraph()

    def add_node(self, labels: list[str], properties: dict[str, Any]) -> GraphNode:
        """Add a node to the graph."""
        node_id = properties.get("id") or str(uuid.uuid4())
        self._graph.add_node(node_id, labels=labels, **properties)
        return GraphNode(id=node_id, labels=labels, properties=properties)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        if node_id not in self._graph:
            return None
        data = dict(self._graph.nodes[node_id])
        labels = data.pop("labels", [])
        return GraphNode(id=node_id, labels=labels, properties=data)

    def update_node(self, node_id: str, properties: dict[str, Any]) -> GraphNode | None:
        """Update node properties."""
        if node_id not in self._graph:
            return None
        self._graph.nodes[node_id].update(properties)
        return self.get_node(node_id)

    def delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        if node_id not in self._graph:
            return False
        self._graph.remove_node(node_id)
        return True

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """Add an edge between nodes."""
        edge_id = str(uuid.uuid4())
        props = properties or {}
        self._graph.add_edge(
            source_id, target_id,
            id=edge_id, type=edge_type, **props,
        )
        return GraphEdge(
            id=edge_id, source_id=source_id, target_id=target_id,
            type=edge_type, properties=props,
        )

    def get_edges(self, node_id: str, direction: str = "both") -> list[GraphEdge]:
        """Get edges connected to a node."""
        edges = []
        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(node_id, data=True):
                edges.append(GraphEdge(
                    id=data.get("id", ""),
                    source_id=node_id,
                    target_id=target,
                    type=data.get("type", ""),
                    properties={k: v for k, v in data.items() if k not in ("id", "type")},
                ))
        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(node_id, data=True):
                edges.append(GraphEdge(
                    id=data.get("id", ""),
                    source_id=source,
                    target_id=node_id,
                    type=data.get("type", ""),
                    properties={k: v for k, v in data.items() if k not in ("id", "type")},
                ))
        return edges

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by ID."""
        for u, v, data in list(self._graph.edges(data=True)):
            if data.get("id") == edge_id:
                self._graph.remove_edge(u, v)
                return True
        return False

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> GraphQueryResult:
        """Execute a pseudo-Cypher query (limited support)."""
        # NetworkX doesn't support Cypher - return all nodes/edges for simple queries
        nodes = [self.get_node(n) for n in self._graph.nodes() if self.get_node(n)]
        edges = []
        for u, v, data in self._graph.edges(data=True):
            edges.append(GraphEdge(
                id=data.get("id", ""),
                source_id=u, target_id=v,
                type=data.get("type", ""),
                properties={k: v for k, v in data.items() if k not in ("id", "type")},
            ))
        return GraphQueryResult(nodes=nodes, edges=edges)

    def health_check(self) -> StorageHealth:
        """Check NetworkX health."""
        start = time.time()
        try:
            node_count = self._graph.number_of_nodes()
            edge_count = self._graph.number_of_edges()
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="networkx", latency_ms=latency,
                details={"nodes": node_count, "edges": edge_count},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="networkx", message=str(e))
