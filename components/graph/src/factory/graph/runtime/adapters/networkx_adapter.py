"""NetworkX adapter for knowledge graph brick."""
from __future__ import annotations
import time
from typing import Any
from ..ports import Entity, Relationship, GraphPath, GraphHealth, KnowledgeGraph
from .networkx_attrs import node_attrs
from .networkx_edges import first_edge_data, iter_edges, remove_edge_id
from .networkx_provenance import NetworkXProvenanceMixin
from .networkx_run_queries import NetworkXRunQueriesMixin
from ..neighbor_limits import DEFAULT_NEIGHBOR_LIMIT, validate_neighbor_limit


class NetworkXGraph(NetworkXProvenanceMixin, NetworkXRunQueriesMixin):
    """NetworkX-based knowledge graph adapter."""
    def __init__(self, **kwargs: Any) -> None:
        self._graph: Any = None

    def _get_graph(self) -> Any:
        if self._graph is None:
            try:
                import networkx as nx
                self._graph = nx.MultiDiGraph()
            except ImportError:
                raise ImportError("networkx required: pip install networkx")
        return self._graph

    def add_entity(self, entity: Entity) -> Entity:
        graph = self._get_graph()
        graph.add_node(entity.id, **node_attrs(entity))
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        graph = self._get_graph()
        if entity_id not in graph.nodes:
            return None
        data = dict(graph.nodes[entity_id])
        return Entity(id=entity_id, type=data.pop("type", "unknown"),
                      labels=data.pop("labels", []), properties=data)

    def update_entity(self, entity: Entity) -> Entity:
        graph = self._get_graph()
        if entity.id not in graph.nodes:
            return self.add_entity(entity)
        graph.nodes[entity.id].update(node_attrs(entity))
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        graph = self._get_graph()
        if entity_id not in graph.nodes:
            return False
        graph.remove_node(entity_id)
        return True

    def add_relationship(self, relationship: Relationship) -> Relationship:
        graph = self._get_graph()
        # Relationship IDs are stable MultiDiGraph edge keys.
        remove_edge_id(graph, relationship.id)
        graph.add_edge(
            relationship.source_id, relationship.target_id, key=relationship.id,
            id=relationship.id, type=relationship.type, **relationship.properties,
        )
        return relationship

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        graph = self._get_graph()
        for u, v, _key, data in iter_edges(graph):
            if data.get("id") == relationship_id:
                props = {k: v for k, v in data.items() if k not in ("id", "type")}
                return Relationship(id=relationship_id, type=data.get("type", "unknown"),
                                    source_id=u, target_id=v, properties=props)
        return None

    def delete_relationship(self, relationship_id: str) -> bool:
        return remove_edge_id(self._get_graph(), relationship_id)

    def get_neighbors(self, entity_id: str, relationship_type: str | None = None, direction: str = "both", limit: int = DEFAULT_NEIGHBOR_LIMIT) -> list[Entity]:
        validate_neighbor_limit(limit)
        graph = self._get_graph()
        neighbors = set()
        if direction in ("out", "both"):
            for _, target, data in graph.out_edges(entity_id, data=True):
                if relationship_type is None or data.get("type") == relationship_type:
                    neighbors.add(target)
        if direction in ("in", "both"):
            for source, _, data in graph.in_edges(entity_id, data=True):
                if relationship_type is None or data.get("type") == relationship_type:
                    neighbors.add(source)
        return [self.get_entity(n) for n in sorted(neighbors, key=str)[:limit] if self.get_entity(n)]

    def get_neighborhood(self, request):
        from .networkx_neighborhood import get_neighborhood
        return get_neighborhood(self, request)

    def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> GraphPath | None:
        import networkx as nx
        graph = self._get_graph()
        try:
            path_nodes = nx.shortest_path(graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        if len(path_nodes) - 1 > max_depth:
            return None
        entities = [self.get_entity(n) for n in path_nodes if self.get_entity(n)]
        relationships = []
        for i in range(len(path_nodes) - 1):
            edge_data = first_edge_data(graph, path_nodes[i], path_nodes[i + 1])
            if edge_data:
                props = {k: v for k, v in edge_data.items() if k not in ("id", "type")}
                relationships.append(Relationship(
                    id=edge_data.get("id", ""), type=edge_data.get("type", ""),
                    source_id=path_nodes[i], target_id=path_nodes[i + 1], properties=props,
                ))
        return GraphPath(entities=entities, relationships=relationships, length=len(path_nodes) - 1)

    def find_entities(self, entity_type: str | None = None, properties: dict[str, Any] | None = None, limit: int = 100) -> list[Entity]:
        graph = self._get_graph()
        results = []
        for node_id in graph.nodes:
            entity = self.get_entity(node_id)
            if entity is None:
                continue
            if entity_type and entity.type != entity_type:
                continue
            if properties and not all(entity.properties.get(k) == v for k, v in properties.items()):
                continue
            results.append(entity)
            if len(results) >= limit:
                break
        return results

    def health_check(self) -> GraphHealth:
        start = time.perf_counter()
        try:
            graph = self._get_graph()
            latency = (time.perf_counter() - start) * 1000
            return GraphHealth(healthy=True, backend="networkx", node_count=graph.number_of_nodes(),
                               edge_count=graph.number_of_edges(), latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return GraphHealth(healthy=False, backend="networkx", latency_ms=latency, message=str(e))

    # --- Run-scoped typed queries (bd python-factory-j1lb) ---
    # Delegating methods live in the NetworkXRunQueriesMixin base class.

    def set_finding_state(self, finding_id: str, state: str) -> bool:
        """Set one finding state atomically without read-modify-write."""
        graph = self._get_graph()
        if finding_id not in graph.nodes:
            return False
        graph.nodes[finding_id]["state"] = state
        return True

    def export_snapshot(self) -> bytes:
        """The whole graph as one portable, checksummed JSON file (row 48
        — owner direction 2026-09-16: simple export/import, no
        staged-restore ceremony). See ``networkx_snapshot_io.py``."""
        from . import networkx_snapshot_io
        return networkx_snapshot_io.export_snapshot(self._get_graph())

    def import_snapshot(self, data: bytes) -> None:
        """Replace the in-memory graph with a previously exported file.
        Raises ``SnapshotIntegrityError`` on a corrupt/foreign file —
        never silently imports a bad graph. See ``networkx_snapshot_io.py``."""
        from . import networkx_snapshot_io
        self._graph = networkx_snapshot_io.import_snapshot(data)
assert isinstance(NetworkXGraph(), KnowledgeGraph)  # protocol conformance
