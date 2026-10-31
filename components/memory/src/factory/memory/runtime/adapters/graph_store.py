"""Graph-backed memory storage (M7.7 Unified graph memory, Slice 1).

Delegates persistence to the ``graph`` brick's ``GraphRuntime`` — the SAME
shared persistent-networkx store the ``kb`` brick's parallel graph adapter
also writes into (consult `8382bf2f`: "one target is the shared graph brick
store, not a shared Protocol"). Shape mirrors ``neo4j.py`` — an adapter that
wraps an external graph runtime rather than owning storage.

A memory becomes a ``memory`` node; ``HAS_MEMORY`` from a ``user`` node
mirrors ``neo4j.py``'s ownership edge, and ``FOLLOWED_BY`` preserves the
same temporal chain. Embedding similarity (when the local embedder reports
``is_semantic``) adds ``similar_to`` edges above a fixed threshold, which is
what unblocks feature-map rows 46/50/51 (Explore memory / Embeddings /
Memory graph visualizer) — none of which are built in this slice, this only
lands the substrate they depend on.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from factory.graph.interface import Entity, GraphRuntime, Relationship
from factory.memory.core import MemoryCategory
from factory.memory.runtime.adapters import graph_similarity, graph_supersession
from factory.memory.runtime.adapters.graph_entity_convert import entity_to_memory
from factory.memory.runtime.embedding_local import LlamaCppEmbedder
from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GraphMemoryStore:
    """``MemoryStore`` adapter over the shared graph brick's KnowledgeGraph."""

    def __init__(self, runtime: GraphRuntime | None = None,
                 embedder: LlamaCppEmbedder | None = None,
                 backend: str = "persistent_networkx") -> None:
        self._graph = (runtime or GraphRuntime()).get_graph(backend)
        self._embedder = embedder or LlamaCppEmbedder()

    @property
    def embedder(self) -> LlamaCppEmbedder:
        """Read-only introspection for the Embeddings status tool (row 50)."""
        return self._embedder

    def store(self, user_id: str, content: str, memory_type: str = "short_term",
              category: str = "custom", metadata: dict[str, Any] | None = None,
              ttl_seconds: int | None = None) -> Memory:
        memory_id = str(uuid.uuid4())
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        props: dict[str, Any] = {
            "user_id": user_id, "content": content, "memory_type": memory_type,
            "category": category, "created_at": now.isoformat(), "relevance_score": 1.0,
        }
        if expires_at:
            props["expires_at"] = expires_at.isoformat()
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    props[f"meta_{k}"] = v
        self._graph.add_entity(Entity(id=memory_id, type="memory", properties=props))
        self._link_owner_and_chain(user_id, memory_id)
        self._link_similar(memory_id, content, user_id)
        return Memory(
            id=memory_id, user_id=user_id, content=content, memory_type=memory_type,
            category=MemoryCategory(category), metadata=metadata or {},
            created_at=now, expires_at=expires_at,
        )

    def _link_owner_and_chain(self, user_id: str, memory_id: str) -> None:
        owner_id = f"user:{user_id}"
        if self._graph.get_entity(owner_id) is None:
            self._graph.add_entity(Entity(id=owner_id, type="user", properties={"user_id": user_id}))
        self._graph.add_relationship(Relationship(
            id=str(uuid.uuid4()), type="HAS_MEMORY", source_id=owner_id, target_id=memory_id,
        ))
        previous = self._graph.find_entities(entity_type="memory", properties={"user_id": user_id}, limit=200)
        chain = sorted(
            (e for e in previous if e.id != memory_id),
            key=lambda e: e.properties.get("created_at", ""), reverse=True,
        )
        if chain:
            self._graph.add_relationship(Relationship(
                id=str(uuid.uuid4()), type="FOLLOWED_BY", source_id=chain[0].id, target_id=memory_id,
            ))

    def _link_similar(self, memory_id: str, content: str, user_id: str) -> None:
        """See ``graph_similarity.py`` — embed once, persist the vector,
        compare against peers' stored vectors instead of re-embedding."""
        graph_similarity.link_similar(self._graph, self._embedder, memory_id, content, user_id)

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        candidates = self._graph.find_entities(
            entity_type="memory", properties={"user_id": query.user_id}, limit=500,
        )
        matched = [
            e for e in candidates
            if query.query.lower() in e.properties.get("content", "").lower()
            and e.properties.get("_status") != "superseded"
        ]
        matched.sort(key=lambda e: e.properties.get("created_at", ""), reverse=True)
        return [entity_to_memory(e) for e in matched[:query.limit]]

    def supersede(self, old_id: str, new_id: str) -> bool:
        """Mark ``old_id`` replaced by ``new_id`` (owner ruling 2026-09-16
        06:32, see ``graph_supersession.py``). The curator calls this —
        never a user-facing restore action."""
        return graph_supersession.supersede(self._graph, old_id, new_id)

    def history(self, memory_id: str) -> list[Memory]:
        """Every version of a memory, newest first — see
        ``graph_supersession.py``. No restore action; informational only."""
        return graph_supersession.history(self._graph, memory_id, entity_to_memory)

    def recall_path(self, memory_id: str) -> dict[str, Any]:
        """The real graph neighborhood around one memory — row 45's recall
        inspection (owner direction 2026-09-16): the owner-facing "why did
        this surface" view, built on the SAME edges ``store()`` already
        writes (no fabricated trace). See ``graph_similarity.recall_path``."""
        return graph_similarity.recall_path(self._graph, memory_id, entity_to_memory)

    def get(self, memory_id: str) -> Memory | None:
        entity = self._graph.get_entity(memory_id)
        return entity_to_memory(entity) if entity else None

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        """Excludes superseded nodes (compx-auditor `8f718ea5` P1: this is
        the surface the Memory tab's default list will actually read, and
        the ruling requires superseded versions to drop out of DEFAULT
        retrieval everywhere, not just ``retrieve()``)."""
        entities = self._graph.find_entities(entity_type="memory", properties={"user_id": user_id}, limit=limit)
        entities = [e for e in entities if e.properties.get("_status") != "superseded"]
        entities.sort(key=lambda e: e.properties.get("created_at", ""), reverse=True)
        return [entity_to_memory(e) for e in entities[:limit]]

    def delete(self, memory_id: str) -> bool:
        return self._graph.delete_entity(memory_id)

    def update(self, memory_id: str, content: str) -> Memory | None:
        """Correct content in place (row 43). Not on the ``MemoryStore``
        Protocol (matches ``recall_path``'s degradation precedent); mirrors
        ``consolidate()``'s mutate-then-``update_entity`` shape."""
        entity = self._graph.get_entity(memory_id)
        if entity is None:
            return None
        entity.properties["content"] = content
        entity.properties["updated_at"] = _utcnow().isoformat()
        self._graph.update_entity(entity)
        return entity_to_memory(entity)

    def delete_user_memories(self, user_id: str) -> int:
        entities = self._graph.find_entities(entity_type="memory", properties={"user_id": user_id}, limit=10_000)
        return sum(1 for e in entities if self._graph.delete_entity(e.id))

    def consolidate(self, user_id: str) -> int:
        entities = self._graph.find_entities(entity_type="memory", properties={"user_id": user_id}, limit=10_000)
        count = 0
        for entity in entities:
            if entity.properties.get("memory_type") == "short_term":
                entity.properties["memory_type"] = "long_term"
                entity.properties["updated_at"] = _utcnow().isoformat()
                self._graph.update_entity(entity)
                count += 1
        return count

    def stats(self, user_id: str | None = None) -> MemoryStats:
        """Excludes superseded nodes by default (compx-auditor `8f718ea5`
        flagged this as a genuine judgment call, not obvious either way —
        decided in favor of "total_memories" reading as live memories, same
        as list_all/retrieve, rather than a raw graph-node count that would
        include dead versions. Revisit if the owner wants a raw count."""
        entities = self._graph.find_entities(
            entity_type="memory", properties={"user_id": user_id} if user_id else None, limit=10_000,
        )
        entities = [e for e in entities if e.properties.get("_status") != "superseded"]
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for entity in entities:
            t = entity.properties.get("memory_type", "short_term")
            c = entity.properties.get("category", "custom")
            by_type[t] = by_type.get(t, 0) + 1
            by_category[c] = by_category.get(c, 0) + 1
        return MemoryStats(total_memories=len(entities), by_type=by_type, by_category=by_category)

    def health_check(self) -> MemoryHealth:
        health = self._graph.health_check()
        return MemoryHealth(
            healthy=health.healthy, backend="graph", latency_ms=health.latency_ms,
            message=health.message or "graph brick persistent_networkx",
        )


__all__ = ["GraphMemoryStore"]
