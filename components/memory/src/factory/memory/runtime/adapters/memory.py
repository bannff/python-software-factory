"""In-memory adapter for memory storage (volatile, for testing)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from rapidfuzz.fuzz import ratio as _fuzz_ratio
from typing import Any

from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class InMemoryStore:
    """In-memory implementation of MemoryStore protocol."""

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}
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
        """Store a new memory."""
        memory_id = str(uuid.uuid4())
        expires_at = None
        if ttl_seconds:
            expires_at = _utcnow() + timedelta(seconds=ttl_seconds)

        memory = Memory(
            id=memory_id,
            user_id=user_id,
            content=content,
            memory_type=memory_type,  # type: ignore
            category=MemoryCategory(category),
            metadata=metadata or {},
            expires_at=expires_at,
        )
        self._memories[memory_id] = memory
        if user_id not in self._user_index:
            self._user_index[user_id] = set()
        self._user_index[user_id].add(memory_id)
        return memory

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        """Retrieve memories with simple text similarity scoring."""
        self._cleanup_expired()
        user_memories = self._get_user_memories(query.user_id)

        # Filter by type and category
        filtered = [m for m in user_memories if self._matches_filters(m, query)]

        # Score by text similarity
        scored = [(m, self._similarity(query.query, m.content)) for m in filtered]
        scored = [(m, s) for m, s in scored if s >= query.min_relevance]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Update relevance scores and return
        result = []
        for memory, score in scored[: query.limit]:
            memory.relevance_score = score
            result.append(memory)
        return result

    def get(self, memory_id: str) -> Memory | None:
        """Get a specific memory by ID."""
        self._cleanup_expired()
        return self._memories.get(memory_id)

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        """List all memories for a user."""
        self._cleanup_expired()
        memories = self._get_user_memories(user_id)
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        memory = self._memories.pop(memory_id, None)
        if memory:
            self._user_index.get(memory.user_id, set()).discard(memory_id)
            return True
        return False

    def update(self, memory_id: str, content: str) -> Memory | None:
        """Correct a memory's content in place (row 43 single correction).

        Not on the ``MemoryStore`` Protocol (matches the existing
        ``recall_path`` degradation precedent) — the runtime facade
        duck-types via ``getattr(store, "update", None)``.
        """
        memory = self._memories.get(memory_id)
        if memory is None:
            return None
        memory.content = content
        memory.updated_at = _utcnow()
        return memory

    def delete_user_memories(self, user_id: str) -> int:
        """Delete all memories for a user."""
        memory_ids = self._user_index.pop(user_id, set())
        for mid in memory_ids:
            self._memories.pop(mid, None)
        return len(memory_ids)

    def consolidate(self, user_id: str) -> int:
        """Move short-term memories to long-term."""
        count = 0
        for memory in self._get_user_memories(user_id):
            if memory.memory_type == "short_term":
                memory.memory_type = "long_term"
                memory.updated_at = _utcnow()
                count += 1
        return count

    def stats(self, user_id: str | None = None) -> MemoryStats:
        """Get memory statistics."""
        self._cleanup_expired()
        memories = list(self._memories.values())
        if user_id:
            memories = [m for m in memories if m.user_id == user_id]

        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for m in memories:
            by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
            by_category[m.category.value] = by_category.get(m.category.value, 0) + 1

        dates = [m.created_at for m in memories]
        return MemoryStats(
            total_memories=len(memories),
            by_type=by_type,
            by_category=by_category,
            oldest_memory=min(dates) if dates else None,
            newest_memory=max(dates) if dates else None,
        )

    def health_check(self) -> MemoryHealth:
        """Check backend health."""
        start = time.perf_counter()
        count = len(self._memories)
        latency = (time.perf_counter() - start) * 1000
        return MemoryHealth(
            healthy=True,
            backend="memory",
            latency_ms=latency,
            message=f"In-memory store with {count} memories",
        )

    def _get_user_memories(self, user_id: str) -> list[Memory]:
        """Get all memories for a user."""
        memory_ids = self._user_index.get(user_id, set())
        return [self._memories[mid] for mid in memory_ids if mid in self._memories]

    def _matches_filters(self, memory: Memory, query: MemoryQuery) -> bool:
        """Check if memory matches query filters."""
        if query.memory_type and memory.memory_type != query.memory_type:
            return False
        if query.category and memory.category != query.category:
            return False
        return True

    def _similarity(self, a: str, b: str) -> float:
        """Text similarity using rapidfuzz (C-accelerated fuzzy matching)."""
        return _fuzz_ratio(a.lower(), b.lower()) / 100.0

    def _cleanup_expired(self) -> None:
        """Remove expired memories."""
        now = _utcnow()
        expired = [
            mid
            for mid, m in self._memories.items()
            if m.expires_at and m.expires_at < now
        ]
        for mid in expired:
            self.delete(mid)
