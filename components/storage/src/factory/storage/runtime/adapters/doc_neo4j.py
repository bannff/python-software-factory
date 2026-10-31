"""Neo4j document storage adapter.

Stores documents as :Document nodes with collection-based labeling.
Metadata is flattened into node properties with a `meta_` prefix.
Implements the DocumentStore Protocol from runtime/ports/document.py.

Requires: neo4j package (optional dependency)
"""

from __future__ import annotations

import importlib.util
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.storage.runtime.adapters.doc_neo4j_atomic import Neo4jCreateOrMatchMixin
from factory.storage.runtime.ports import Document, StorageHealth

NEO4J_AVAILABLE = importlib.util.find_spec("neo4j") is not None


def _require_neo4j() -> None:
    if not NEO4J_AVAILABLE:
        raise ImportError("neo4j required. Install with: pip install neo4j")


class Neo4jDocumentStore(Neo4jCreateOrMatchMixin):
    """Neo4j implementation of DocumentStore port.

    Documents are stored as :Document nodes with properties:
      - id, collection, created_at, updated_at
      - data fields flattened with `d_` prefix
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] | None = None,
        database: str = "neo4j",
    ) -> None:
        _require_neo4j()
        import os
        from neo4j import GraphDatabase
        uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        auth = auth or (
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "password"),
        )
        self._driver = GraphDatabase.driver(uri, auth=auth)
        self._database = database
        self._uri = uri
        self._ensure_index()

    def _ensure_index(self) -> None:
        """Create uniqueness constraint on Document.id."""
        with self._driver.session(database=self._database) as s:
            try:
                s.run(
                    "CREATE CONSTRAINT doc_id IF NOT EXISTS "
                    "FOR (d:Document) REQUIRE d.id IS UNIQUE"
                )
            except Exception:
                pass  # constraint may already exist

    # -- write ops --

    def insert(
        self, collection: str, data: dict[str, Any], doc_id: str | None = None,
    ) -> Document:
        """Insert a document as a :Document node."""
        doc_id = doc_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        props = self._flatten(data, doc_id, collection, now, now)
        with self._driver.session(database=self._database) as s:
            s.run("CREATE (d:Document $props)", props=props)
        return Document(
            id=doc_id, collection=collection, data=data,
            created_at=now, updated_at=now,
        )

    def update(
        self, collection: str, doc_id: str, data: dict[str, Any],
    ) -> Document | None:
        """Update a document's data fields."""
        now = datetime.now(timezone.utc)
        flat = {f"d_{k}": v for k, v in data.items() if isinstance(v, (str, int, float, bool))}
        flat["updated_at"] = now.isoformat()
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (d:Document {id: $id, collection: $col}) "
                "SET d += $props RETURN d",
                id=doc_id, col=collection, props=flat,
            ).single()
        if not rec:
            return None
        return self._node_to_doc(dict(rec["d"]))

    def delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document node."""
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (d:Document {id: $id, collection: $col}) "
                "WITH d, count(d) AS c DETACH DELETE d RETURN c",
                id=doc_id, col=collection,
            ).single()
        return rec is not None and rec["c"] > 0

    # -- read ops --

    def get(self, collection: str, doc_id: str) -> Document | None:
        """Get a document by ID."""
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (d:Document {id: $id, collection: $col}) RETURN d",
                id=doc_id, col=collection,
            ).single()
        if not rec:
            return None
        return self._node_to_doc(dict(rec["d"]))

    def find(
        self, collection: str, query: dict[str, Any],
        limit: int = 100, skip: int = 0,
    ) -> list[Document]:
        """Find documents matching property filters."""
        where = ["d.collection = $col"]
        params: dict[str, Any] = {"col": collection, "lim": limit, "sk": skip}
        for i, (k, v) in enumerate(query.items()):
            pname = f"p{i}"
            where.append(f"d.d_{k} = ${pname}")
            params[pname] = v
        cypher = (
            f"MATCH (d:Document) WHERE {' AND '.join(where)} "
            f"RETURN d SKIP $sk LIMIT $lim"
        )
        with self._driver.session(database=self._database) as s:
            return [self._node_to_doc(dict(r["d"])) for r in s.run(cypher, **params)]

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        """Count documents in a collection."""
        if query:
            return len(self.find(collection, query, limit=100_000))
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (d:Document {collection: $col}) RETURN count(d) AS c",
                col=collection,
            ).single()
        return rec["c"] if rec else 0

    def health_check(self) -> StorageHealth:
        """Check Neo4j connectivity."""
        start = time.time()
        try:
            with self._driver.session(database=self._database) as s:
                s.run("RETURN 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="neo4j-doc", latency_ms=latency,
                details={"uri": self._uri, "database": self._database},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="neo4j-doc", message=str(e))

    # -- helpers --

    @staticmethod
    def _flatten(
        data: dict[str, Any], doc_id: str, collection: str,
        created: datetime, updated: datetime,
    ) -> dict[str, Any]:
        props: dict[str, Any] = {
            "id": doc_id, "collection": collection,
            "created_at": created.isoformat(), "updated_at": updated.isoformat(),
        }
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)):
                props[f"d_{k}"] = v
        return props

    @staticmethod
    def _node_to_doc(node: dict[str, Any]) -> Document:
        data = {k[2:]: v for k, v in node.items() if k.startswith("d_")}
        ca = node.get("created_at")
        ua = node.get("updated_at")
        return Document(
            id=node.get("id", ""),
            collection=node.get("collection", ""),
            data=data,
            created_at=datetime.fromisoformat(ca) if ca else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(ua) if ua else datetime.now(timezone.utc),
        )
