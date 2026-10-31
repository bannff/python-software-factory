"""Neo4j graph storage adapter."""

from __future__ import annotations

import importlib.util
import time
import uuid
from typing import Any

from factory.storage.runtime.ports import GraphNode, GraphEdge, GraphQueryResult, StorageHealth

NEO4J_AVAILABLE = importlib.util.find_spec("neo4j") is not None


def _require_neo4j() -> None:
    if not NEO4J_AVAILABLE:
        raise ImportError("neo4j required. Install with: pip install neo4j")


class Neo4jGraphStore:
    """Neo4j implementation of GraphStore port."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] | None = None,
        database: str = "neo4j",
    ) -> None:
        _require_neo4j()
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(uri, auth=auth)
        self._database = database
        self._uri = uri

    def add_node(self, labels: list[str], properties: dict[str, Any]) -> GraphNode:
        """Add a node to Neo4j."""
        node_id = properties.get("id") or str(uuid.uuid4())
        props = {**properties, "id": node_id}
        label_str = ":".join(labels) if labels else "Node"

        with self._driver.session(database=self._database) as session:
            session.run(
                f"CREATE (n:{label_str} $props)",
                props=props,
            )
        return GraphNode(id=node_id, labels=labels, properties=properties)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (n {id: $id}) RETURN n, labels(n) as labels",
                id=node_id,
            )
            record = result.single()
            if not record:
                return None
            node = record["n"]
            return GraphNode(
                id=node_id,
                labels=record["labels"],
                properties=dict(node),
            )

    def update_node(self, node_id: str, properties: dict[str, Any]) -> GraphNode | None:
        """Update node properties."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (n {id: $id}) SET n += $props RETURN n, labels(n) as labels",
                id=node_id, props=properties,
            )
            record = result.single()
            if not record:
                return None
            return GraphNode(
                id=node_id,
                labels=record["labels"],
                properties=dict(record["n"]),
            )

    def delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (n {id: $id}) DETACH DELETE n RETURN count(n) as deleted",
                id=node_id,
            )
            record = result.single()
            return record["deleted"] > 0 if record else False

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """Add an edge between nodes."""
        edge_id = str(uuid.uuid4())
        props = {**(properties or {}), "id": edge_id}

        with self._driver.session(database=self._database) as session:
            session.run(
                f"""
                MATCH (a {{id: $source}}), (b {{id: $target}})
                CREATE (a)-[r:{edge_type} $props]->(b)
                """,
                source=source_id, target=target_id, props=props,
            )
        return GraphEdge(
            id=edge_id, source_id=source_id, target_id=target_id,
            type=edge_type, properties=properties or {},
        )

    def get_edges(self, node_id: str, direction: str = "both") -> list[GraphEdge]:
        """Get edges connected to a node."""
        edges = []
        with self._driver.session(database=self._database) as session:
            if direction in ("out", "both"):
                result = session.run(
                    "MATCH (n {id: $id})-[r]->(m) RETURN r, type(r) as t, m.id as target",
                    id=node_id,
                )
                for record in result:
                    edges.append(self._record_to_edge(node_id, record, "out"))

            if direction in ("in", "both"):
                result = session.run(
                    "MATCH (n {id: $id})<-[r]-(m) RETURN r, type(r) as t, m.id as source",
                    id=node_id,
                )
                for record in result:
                    edges.append(self._record_to_edge(node_id, record, "in"))
        return edges

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by ID."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH ()-[r {id: $id}]->() DELETE r RETURN count(r) as deleted",
                id=edge_id,
            )
            record = result.single()
            return record["deleted"] > 0 if record else False

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> GraphQueryResult:
        """Execute a Cypher query."""
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, params or {})
            raw = [dict(record) for record in result]
        return GraphQueryResult(raw=raw)

    def health_check(self) -> StorageHealth:
        """Check Neo4j health."""
        start = time.time()
        try:
            with self._driver.session(database=self._database) as session:
                session.run("RETURN 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="neo4j", latency_ms=latency,
                details={"uri": self._uri, "database": self._database},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="neo4j", message=str(e))

    def close(self) -> None:
        """Close the driver."""
        self._driver.close()

    def _record_to_edge(self, node_id: str, record: Any, direction: str) -> GraphEdge:
        """Convert a Neo4j record to GraphEdge."""
        rel = record["r"]
        props = dict(rel)
        edge_id = props.pop("id", "")
        if direction == "out":
            return GraphEdge(
                id=edge_id, source_id=node_id, target_id=record["target"],
                type=record["t"], properties=props,
            )
        return GraphEdge(
            id=edge_id, source_id=record["source"], target_id=node_id,
            type=record["t"], properties=props,
        )
