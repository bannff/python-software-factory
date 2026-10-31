"""Neptune traversal, search, and health — extends NeptuneGraphAdapter.

Kept separate from aws.py to stay under 200 LOC per file.
Import NeptuneGraphAdapter from aws.py; this module monkey-patches
nothing — it's mixed in via multiple inheritance or direct use.
"""

from __future__ import annotations

import re
from typing import Any

from factory.graph.runtime.ports import (
    Entity, GraphHealth, GraphPath, QueryResult,
)
from factory.graph.runtime.neighbor_limits import DEFAULT_NEIGHBOR_LIMIT, validate_neighbor_limit
from factory.graph.runtime.topology_errors import GraphTopologyUnsupportedError


class NeptuneQueryMixin:
    """Traversal, search, and health methods for Neptune adapter.

    Expects self._query() and self._rows() from NeptuneGraphAdapter.
    """

    def get_run_topology(self, run_id: str, limit: int = 200) -> QueryResult:
        raise GraphTopologyUnsupportedError("neptune")

    def get_neighbors(
        self, entity_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = DEFAULT_NEIGHBOR_LIMIT,
    ) -> list[Entity]:
        validate_neighbor_limit(limit)
        rel = ""
        if relationship_type:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", relationship_type):
                raise ValueError(f"Invalid relationship type: {relationship_type!r}")
            rel = f":{relationship_type}"
        match direction:
            case "out":
                pat = f"(a {{id: $id}})-[{rel}]->(b)"
            case "in":
                pat = f"(a {{id: $id}})<-[{rel}]-(b)"
            case _:
                pat = f"(a {{id: $id}})-[{rel}]-(b)"
        rows = self._rows(
            f"MATCH {pat} RETURN b LIMIT $limit",
            {"id": entity_id, "limit": limit},
        )  # type: ignore[attr-defined]
        return [
            Entity(id=r["b"].get("id", ""), type=r["b"].get("type", ""),
                   properties=r["b"])
            for r in rows[:limit]
        ]

    def find_path(
        self, source_id: str, target_id: str, max_depth: int = 5,
    ) -> GraphPath | None:
        max_depth = max(1, min(int(max_depth), 20))
        result = self._query(  # type: ignore[attr-defined]
            f"MATCH p=shortestPath((a {{id: $src}})-[*..{max_depth}]-(b {{id: $tgt}})) RETURN p",
            {"src": source_id, "tgt": target_id},
        )
        if not result.get("results"):
            return None
        return GraphPath(entities=[], relationships=[], length=0)

    def find_entities(
        self, entity_type: str | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        clauses, params = [], {"limit": limit}
        if entity_type:
            clauses.append("n.type = $type")
            params["type"] = entity_type
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._rows(  # type: ignore[attr-defined]
            f"MATCH (n){where} RETURN n LIMIT $limit", params,
        )
        return [
            Entity(id=r["n"].get("id", ""), type=r["n"].get("type", ""),
                   properties=r["n"])
            for r in rows
        ]

    def health_check(self) -> GraphHealth:
        try:
            rows = self._rows("MATCH (n) RETURN count(n) AS cnt")  # type: ignore[attr-defined]
            cnt = rows[0].get("cnt", 0) if rows else 0
            return GraphHealth(healthy=True, backend="neptune", node_count=cnt)
        except Exception as e:
            return GraphHealth(healthy=False, backend="neptune", message=str(e))

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "neptune",
            "construct": "DatabaseCluster",
            "props": {
                "engine": "neptune",
                "serverless_scaling": {"min_capacity": 1.0, "max_capacity": 8.0},
            },
        }
