"""Neo4j adapter for agent memory with graph-native storage.

Stores memories as nodes with temporal edges (FOLLOWED_BY)
and user ownership (HAS_MEMORY). Pure graph storage — no embeddings.

For embedding-enhanced retrieval, use Neo4jEmbeddingMemoryStore
from neo4j_embedding.py which wraps this store.

Requires Neo4j 5.11+. GDS structural embeddings are managed
externally via the graph brick's MCP tools.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats
from factory.memory.runtime.adapters._neo4j_filters import build_filter_clauses

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None  # type: ignore[assignment, misc]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_memory(node: Any, score: float | None = None) -> Memory:
    """Convert a Neo4j node to a Memory model."""
    props = dict(node)
    meta = {k[5:]: v for k, v in props.items() if k.startswith("meta_")}
    # Carry evolution properties into metadata if present
    if props.get("keywords"):
        meta["keywords"] = props["keywords"]
    if props.get("context"):
        meta["context"] = props["context"]
    if props.get("tags"):
        meta["tags"] = props["tags"]
    if props.get("evolution_status"):
        meta["evolution_status"] = props["evolution_status"]
    relevance = score if score is not None else props.get("relevance_score", 1.0)
    return Memory(
        id=props["id"], user_id=props["user_id"], content=props["content"],
        memory_type=props.get("memory_type", "short_term"),
        category=MemoryCategory(props.get("category", "custom")),
        metadata=meta, relevance_score=min(relevance, 1.0),
        created_at=datetime.fromisoformat(props["created_at"]) if "created_at" in props else _utcnow(),
        updated_at=datetime.fromisoformat(props["updated_at"]) if props.get("updated_at") else None,
        expires_at=datetime.fromisoformat(props["expires_at"]) if props.get("expires_at") else None,
    )


class Neo4jMemoryStore:
    """Neo4j implementation of MemoryStore protocol."""

    def __init__(self, uri: str | None = None, user: str | None = None,
                 password: str | None = None, database: str = "neo4j") -> None:
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j required: pip install neo4j")
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self._database = database
        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        self._ensure_constraints()

    @property
    def driver(self) -> Any:
        return self._driver

    @property
    def database(self) -> str:
        return self._database

    def _ensure_constraints(self) -> None:
        queries = [
            "CREATE CONSTRAINT mem_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
            "CREATE INDEX mem_user IF NOT EXISTS FOR (m:Memory) ON (m.user_id)",
        ]
        with self._driver.session(database=self._database) as s:
            for q in queries:
                try:
                    s.run(q)
                except Exception:
                    pass

    def store(self, user_id: str, content: str, memory_type: str = "short_term",
              category: str = "custom", metadata: dict[str, Any] | None = None,
              ttl_seconds: int | None = None) -> Memory:
        memory_id = str(uuid.uuid4())
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        props: dict[str, Any] = {
            "id": memory_id, "user_id": user_id, "content": content,
            "memory_type": memory_type, "category": category,
            "created_at": now.isoformat(), "relevance_score": 1.0,
        }
        if expires_at:
            props["expires_at"] = expires_at.isoformat()
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    props[f"meta_{k}"] = v
        query = (
            "MERGE (u:User {id: $uid}) "
            "CREATE (m:Memory {id: $mid}) SET m += $props "
            "CREATE (u)-[:HAS_MEMORY]->(m) "
            "WITH u, m "
            "OPTIONAL MATCH (u)-[:HAS_MEMORY]->(prev:Memory) "
            "WHERE prev.id <> m.id "
            "WITH m, prev ORDER BY prev.created_at DESC LIMIT 1 "
            "FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END | "
            "  CREATE (prev)-[:FOLLOWED_BY]->(m))"
        )
        with self._driver.session(database=self._database) as s:
            s.run(query, uid=user_id, mid=memory_id, props=props)
        return Memory(
            id=memory_id, user_id=user_id, content=content,
            memory_type=memory_type, category=MemoryCategory(category),
            metadata=metadata or {}, expires_at=expires_at, created_at=now,
        )

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        # Tags + metadata push-down (bd:python-factory-26e2a + b2d2o).
        # Conditional via _neo4j_filters.build_filter_clauses: tags=None /
        # metadata=None|{} → no fragment; tags=[] → leave to runtime
        # post-filter (returns []); non-empty → ANY-match on m.tags
        # + per-key m.meta_<k> = $meta_<k>. Cypher-injection guard
        # (safe_property_key) is applied inside the helper.
        params: dict[str, Any] = {"uid": query.user_id, "q": query.query, "lim": query.limit}
        filter_clauses = build_filter_clauses(query, params)
        cypher = (
            "MATCH (m:Memory {user_id: $uid}) WHERE m.content CONTAINS $q"
            f"{filter_clauses} RETURN m ORDER BY m.created_at DESC LIMIT $lim"
        )
        with self._driver.session(database=self._database) as s:
            records = list(s.run(cypher, **params))
        return [to_memory(r["m"]) for r in records]

    def get(self, memory_id: str) -> Memory | None:
        with self._driver.session(database=self._database) as s:
            rec = s.run("MATCH (m:Memory {id: $id}) RETURN m", id=memory_id).single()
        return to_memory(rec["m"]) if rec else None

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        cypher = "MATCH (m:Memory {user_id: $uid}) RETURN m ORDER BY m.created_at DESC LIMIT $lim"
        with self._driver.session(database=self._database) as s:
            return [to_memory(r["m"]) for r in s.run(cypher, uid=user_id, lim=limit)]
    def delete(self, memory_id: str) -> bool:
        with self._driver.session(database=self._database) as s:
            rec = s.run("MATCH (m:Memory {id: $id}) DETACH DELETE m RETURN count(m) AS c", id=memory_id).single()
        return rec is not None and rec["c"] > 0

    def delete_user_memories(self, user_id: str) -> int:
        with self._driver.session(database=self._database) as s:
            rec = s.run("MATCH (m:Memory {user_id: $uid}) DETACH DELETE m RETURN count(m) AS c", uid=user_id).single()
        return rec["c"] if rec else 0

    def consolidate(self, user_id: str) -> int:
        cypher = (
            "MATCH (m:Memory {user_id: $uid, memory_type: 'short_term'}) "
            "SET m.memory_type = 'long_term', m.updated_at = $now RETURN count(m) AS c"
        )
        with self._driver.session(database=self._database) as s:
            rec = s.run(cypher, uid=user_id, now=_utcnow().isoformat()).single()
        return rec["c"] if rec else 0

    def stats(self, user_id: str | None = None) -> MemoryStats:
        where = "WHERE m.user_id = $uid" if user_id else ""
        cypher = f"MATCH (m:Memory) {where} RETURN m.memory_type AS t, m.category AS c, count(m) AS n"
        params: dict[str, Any] = {"uid": user_id} if user_id else {}
        by_type: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        total = 0
        with self._driver.session(database=self._database) as s:
            for r in s.run(cypher, **params):
                by_type[r["t"]] = by_type.get(r["t"], 0) + r["n"]
                by_cat[r["c"]] = by_cat.get(r["c"], 0) + r["n"]
                total += r["n"]
        return MemoryStats(total_memories=total, by_type=by_type, by_category=by_cat)

    def health_check(self) -> MemoryHealth:
        start = time.perf_counter()
        try:
            with self._driver.session(database=self._database) as s:
                s.run("RETURN 1").single()
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(healthy=True, backend="neo4j", latency_ms=latency, message="Neo4j connected")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(healthy=False, backend="neo4j", latency_ms=latency, message=str(e))
