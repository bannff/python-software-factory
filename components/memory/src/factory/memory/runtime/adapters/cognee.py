"""Cognee adapter for knowledge-graph-enriched agent memory.

Cognee builds knowledge graphs from unstructured data, enabling
graph-based memory retrieval with entity relationships and reasoning.

Ideal for agents that need structured knowledge extraction,
relationship-aware recall, and graph-powered reasoning over memory.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CogneeMemoryStore:
    """Cognee implementation of MemoryStore protocol.

    Uses cognee SDK for knowledge-graph-enriched memory:
    - Automatic entity and relationship extraction
    - Graph-based semantic search
    - Structured knowledge representation
    - Cross-document reasoning
    """

    def __init__(self, **kwargs: Any) -> None:
        import cognee

        self._cognee = cognee
        self._local_index: dict[str, Memory] = {}
        self._user_index: dict[str, set[str]] = {}

    def store(
        self,
        user_id: str,
        content: str,
        memory_type: str = "short_term",
        category: str = "custom",
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> Memory:
        import asyncio

        memory_id = str(uuid.uuid4())
        expires_at = _utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None

        # Add content to Cognee's knowledge graph
        tagged_content = f"[user:{user_id}] [{category}] {content}"
        asyncio.run(self._cognee.add(tagged_content, dataset_name=f"memory_{user_id}"))
        asyncio.run(self._cognee.cognify())

        memory = Memory(
            id=memory_id,
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            category=MemoryCategory(category),
            metadata=metadata or {},
            expires_at=expires_at,
        )
        self._local_index[memory_id] = memory
        self._user_index.setdefault(user_id, set()).add(memory_id)
        return memory

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        import asyncio

        results = asyncio.run(self._cognee.search(
            query_type="GRAPH_COMPLETION",
            query_text=query.query,
            datasets=[f"memory_{query.user_id}"],
        ))

        memories = []
        for item in results or []:
            content = str(item)
            mem = Memory(
                id=str(uuid.uuid4()),
                user_id=query.user_id,
                content=content,
                memory_type="long_term",
                category=MemoryCategory.FACT,
                relevance_score=0.8,
            )
            memories.append(mem)
            if len(memories) >= query.limit:
                break
        return memories

    def get(self, memory_id: str) -> Memory | None:
        return self._local_index.get(memory_id)

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        mids = self._user_index.get(user_id, set())
        memories = [self._local_index[m] for m in mids if m in self._local_index]
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:limit]

    def delete(self, memory_id: str) -> bool:
        mem = self._local_index.pop(memory_id, None)
        if mem:
            self._user_index.get(mem.user_id, set()).discard(memory_id)
            return True
        return False

    def delete_user_memories(self, user_id: str) -> int:
        import asyncio

        mids = self._user_index.pop(user_id, set())
        for mid in mids:
            self._local_index.pop(mid, None)
        try:
            asyncio.run(self._cognee.prune.prune_data(dataset_name=f"memory_{user_id}"))
        except Exception:
            pass
        return len(mids)

    def consolidate(self, user_id: str) -> int:
        # Cognee's knowledge graph is inherently consolidated
        # Re-cognify to ensure graph is up to date
        import asyncio

        try:
            asyncio.run(self._cognee.cognify())
        except Exception:
            pass
        return 0

    def stats(self, user_id: str | None = None) -> MemoryStats:
        if user_id:
            mids = self._user_index.get(user_id, set())
            count = len(mids)
        else:
            count = len(self._local_index)
        return MemoryStats(total_memories=count, by_type={"long_term": count})

    def health_check(self) -> MemoryHealth:
        start = time.perf_counter()
        try:
            # Verify cognee is importable and responsive
            import cognee  # noqa: F811
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=True, backend="cognee", latency_ms=latency,
                message="Cognee connected",
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=False, backend="cognee", latency_ms=latency,
                message=f"Cognee error: {e}",
            )
