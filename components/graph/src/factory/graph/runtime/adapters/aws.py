"""AWS Neptune adapter for graph brick.

Implements KnowledgeGraph protocol using Amazon Neptune
with openCypher query support. Traversal/search in aws_queries.py.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from factory.graph.runtime.ports import (
    Entity, GraphHealth, GraphPath, Relationship,
)
from factory.graph.runtime.adapters.aws_queries import NeptuneQueryMixin


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for Neptune adapter"
        raise ImportError(msg)


class NeptuneGraphAdapter(NeptuneQueryMixin):
    """Amazon Neptune adapter for KnowledgeGraph port."""

    def __init__(
        self, endpoint: str = "localhost", port: int = 8182,
        region: str = "us-east-1", use_iam: bool = True, **kwargs: Any,
    ) -> None:
        _require_boto3()
        self._endpoint = endpoint
        self._port = port
        self._region = region
        self._base_url = f"https://{endpoint}:{port}"

    @staticmethod
    def _validate_identifier(value: str) -> str:
        """Validate Cypher label/type — alphanumeric + underscore only."""
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
            raise ValueError(f"Invalid Cypher identifier: {value!r}")
        return value

    def _query(self, cypher: str, params: dict | None = None) -> Any:
        """Execute openCypher query against Neptune HTTP endpoint."""
        import urllib.request
        payload = json.dumps({"query": cypher, "parameters": params or {}})
        req = urllib.request.Request(
            f"{self._base_url}/openCypher",
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _rows(self, cypher: str, params: dict | None = None) -> list[dict]:
        return self._query(cypher, params).get("results", [])

    # --- Entity CRUD ---

    def add_entity(self, entity: Entity) -> Entity:
        eid = entity.id or str(uuid.uuid4())
        safe_labels = [self._validate_identifier(l) for l in (entity.labels or [entity.type])]
        labels = ":".join(safe_labels)
        props = {**entity.properties, "id": eid, "type": entity.type}
        self._query(f"CREATE (n:{labels} $props) RETURN n", {"props": props})
        return Entity(id=eid, type=entity.type, properties=entity.properties, labels=entity.labels)

    def get_entity(self, entity_id: str) -> Entity | None:
        rows = self._rows("MATCH (n {id: $id}) RETURN n", {"id": entity_id})
        if not rows:
            return None
        n = rows[0].get("n", {})
        return Entity(
            id=entity_id, type=n.get("type", "unknown"),
            properties={k: v for k, v in n.items() if k not in ("id", "type")},
        )

    def update_entity(self, entity: Entity) -> Entity:
        self._query("MATCH (n {id: $id}) SET n += $props RETURN n",
                     {"id": entity.id, "props": entity.properties})
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        self._query("MATCH (n {id: $id}) DETACH DELETE n", {"id": entity_id})
        return True

    # --- Relationship CRUD ---

    def add_relationship(self, rel: Relationship) -> Relationship:
        rid = rel.id or str(uuid.uuid4())
        safe_type = self._validate_identifier(rel.type)
        self._query(
            f"MATCH (a {{id: $src}}), (b {{id: $tgt}}) "
            f"CREATE (a)-[r:{safe_type} $props]->(b) RETURN r",
            {"src": rel.source_id, "tgt": rel.target_id,
             "props": {**rel.properties, "id": rid}},
        )
        return Relationship(
            id=rid, type=rel.type, source_id=rel.source_id,
            target_id=rel.target_id, properties=rel.properties,
        )

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        rows = self._rows("MATCH ()-[r {id: $id}]->() RETURN r", {"id": relationship_id})
        if not rows:
            return None
        return Relationship(
            id=relationship_id, type="unknown", source_id="", target_id="",
            properties=rows[0].get("r", {}),
        )

    def delete_relationship(self, relationship_id: str) -> bool:
        self._query("MATCH ()-[r {id: $id}]->() DELETE r", {"id": relationship_id})
        return True
