"""Neo4j adapter for knowledge graph brick."""
from __future__ import annotations
import time
from typing import Any
from ..entity_contract import normalize_entity_properties
from ..models import TaxonomyEdgeSpec
from ..ports import Entity, Relationship, GraphPath, GraphHealth, KnowledgeGraph, QueryResult
from .neo4j_provenance import Neo4jProvenanceUnsupportedMixin
from . import neo4j_runs
from ..neighbor_limits import DEFAULT_NEIGHBOR_LIMIT, validate_neighbor_limit


class Neo4jGraph(Neo4jProvenanceUnsupportedMixin):
    """Neo4j-based knowledge graph adapter."""
    def __init__(
        self, uri: str = "bolt://localhost:7687", user: str = "neo4j",
        password: str = "password", database: str = "neo4j", **kwargs: Any,
    ) -> None:
        self._uri, self._user, self._password, self._database = uri, user, password, database
        self._driver: Any = None

    def _get_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            except ImportError:
                raise ImportError("neo4j required: pip install neo4j")
        return self._driver

    def add_entity(self, entity: Entity) -> Entity:
        driver = self._get_driver()
        labels = ":".join([entity.type] + entity.labels) if entity.labels else entity.type
        props = {**normalize_entity_properties(entity), "id": entity.id}  # cig73: reserved keys -> prop_*
        with driver.session(database=self._database) as session:
            session.run(f"MERGE (n:{labels} {{id: $id}}) SET n += $props", id=entity.id, props=props)
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            result = session.run("MATCH (n {id: $id}) RETURN n, labels(n) as labels", id=entity_id)
            record = result.single()
            if not record:
                return None
            node, labels = record["n"], record["labels"]
            props = dict(node)
            props.pop("id", None)
            return Entity(id=entity_id, type=labels[0] if labels else "unknown",
                          labels=labels[1:] if len(labels) > 1 else [], properties=props)

    def update_entity(self, entity: Entity) -> Entity:
        return self.add_entity(entity)

    def delete_entity(self, entity_id: str) -> bool:
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            result = session.run("MATCH (n {id: $id}) DETACH DELETE n RETURN count(n) as c", id=entity_id)
            return result.single()["c"] > 0

    def add_relationship(self, relationship: Relationship) -> Relationship:
        driver = self._get_driver()
        props = {**relationship.properties, "id": relationship.id}
        with driver.session(database=self._database) as session:
            session.run(
                f"MATCH (a {{id: $src}}), (b {{id: $tgt}}) "
                f"MERGE (a)-[r:{relationship.type} {{id: $rid}}]->(b) SET r += $props",
                src=relationship.source_id, tgt=relationship.target_id, rid=relationship.id, props=props,
            )
        return relationship

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (a)-[r {id: $id}]->(b) RETURN r, type(r) as type, a.id as src, b.id as tgt",
                id=relationship_id,
            )
            record = result.single()
            if not record:
                return None
            props = dict(record["r"])
            props.pop("id", None)
            return Relationship(id=relationship_id, type=record["type"],
                                source_id=record["src"], target_id=record["tgt"], properties=props)

    def delete_relationship(self, relationship_id: str) -> bool:
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            result = session.run("MATCH ()-[r {id: $id}]->() DELETE r RETURN count(r) as c", id=relationship_id)
            return result.single()["c"] > 0

    def get_neighbors(self, entity_id: str, relationship_type: str | None = None, direction: str = "both", limit: int = DEFAULT_NEIGHBOR_LIMIT) -> list[Entity]:
        validate_neighbor_limit(limit)
        driver = self._get_driver()
        rel_filter = f":{relationship_type}" if relationship_type else ""
        if direction == "out":
            query = f"MATCH (a {{id: $id}})-[{rel_filter}]->(b) RETURN DISTINCT b.id as id ORDER BY id LIMIT $limit"
        elif direction == "in":
            query = f"MATCH (a {{id: $id}})<-[{rel_filter}]-(b) RETURN DISTINCT b.id as id ORDER BY id LIMIT $limit"
        else:
            query = f"MATCH (a {{id: $id}})-[{rel_filter}]-(b) RETURN DISTINCT b.id as id ORDER BY id LIMIT $limit"
        with driver.session(database=self._database) as session:
            result = session.run(query, id=entity_id, limit=limit)
            neighbors = []
            for row in result:
                entity = self.get_entity(row["id"])
                if entity:
                    neighbors.append(entity)
                if len(neighbors) >= limit:
                    break
            return neighbors

    def get_neighborhood(self, request):
        from .neo4j_neighborhood import get_neighborhood
        return get_neighborhood(self, request)

    def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> GraphPath | None:
        driver = self._get_driver()
        with driver.session(database=self._database) as session:
            result = session.run(
                f"MATCH p=shortestPath((a {{id: $src}})-[*..{max_depth}]-(b {{id: $tgt}})) RETURN p",
                src=source_id, tgt=target_id,
            )
            record = result.single()
            if not record:
                return None
            path = record["p"]
            entities = [self.get_entity(n["id"]) for n in path.nodes if self.get_entity(n.get("id"))]
            relationships = [
                Relationship(id=rel.get("id", ""), type=rel.type,
                             source_id=rel.start_node["id"], target_id=rel.end_node["id"])
                for rel in path.relationships
            ]
            return GraphPath(entities=entities, relationships=relationships, length=len(relationships))

    def find_entities(self, entity_type: str | None = None, properties: dict[str, Any] | None = None, limit: int = 100) -> list[Entity]:
        driver = self._get_driver()
        label = f":{entity_type}" if entity_type else ""
        where_clauses, params = [], {"limit": limit}
        if properties:
            for i, (k, v) in enumerate(properties.items()):
                where_clauses.append(f"n.{k} = $prop{i}")
                params[f"prop{i}"] = v
        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"MATCH (n{label}) {where} RETURN n.id as id LIMIT $limit"
        with driver.session(database=self._database) as session:
            result = session.run(query, **params)
            return [self.get_entity(r["id"]) for r in result if self.get_entity(r["id"])]

    def health_check(self) -> GraphHealth:
        start = time.perf_counter()
        try:
            driver = self._get_driver()
            with driver.session(database=self._database) as session:
                nodes = session.run("MATCH (n) RETURN count(n) as nodes").single()["nodes"]
                edges = session.run("MATCH ()-[r]->() RETURN count(r) as edges").single()["edges"]
            latency = (time.perf_counter() - start) * 1000
            return GraphHealth(healthy=True, backend="neo4j", node_count=nodes, edge_count=edges, latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return GraphHealth(healthy=False, backend="neo4j", latency_ms=latency, message=str(e))

    # --- Run-scoped typed queries (bd python-factory-j1lb / c39g) ---
    # Implementations live in neo4j_runs.py to keep this file <200 LOC.

    def get_findings_for_run(
        self, run_id: str, app: str = "", limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        return neo4j_runs.get_findings_for_run(
            self, run_id, app, limit, taxonomy_edges)

    def count_entities_by_run(
        self, run_id: str, labels: list[str],
    ) -> dict[str, int]:
        return neo4j_runs.count_entities_by_run(self, run_id, labels)

    def get_recent_findings(
        self, severity: str = "", app: str = "", run_id: str = "",
        limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        return neo4j_runs.get_recent_findings(
            self, severity, app, run_id, limit, taxonomy_edges)

    def get_target_app(self, target_app: str, run_id: str = "") -> Entity | None:
        return neo4j_runs.get_target_app(self, target_app, run_id)

    def get_tool_invocations_for_run(self, run_id: str, limit: int = 50) -> QueryResult:
        return neo4j_runs.get_tool_invocations_for_run(self, run_id, limit)

    def set_finding_state(self, finding_id: str, state: str) -> bool:
        return neo4j_runs.set_finding_state(self, finding_id, state)
    def list_recent_tool_invocations(self, limit: int = 100) -> QueryResult:
        from factory.mcp_utils.interface import POLL_NOISE
        return neo4j_runs.list_recent_tool_invocations(self, limit, list(POLL_NOISE))
assert issubclass(Neo4jGraph, KnowledgeGraph)  # see ports.py docstring
