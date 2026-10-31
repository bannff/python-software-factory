"""Zep adapter for agent memory.

Zep provides long-term memory for AI assistants with temporal awareness,
entity extraction, and semantic search. Supports both Zep Cloud and Zep OSS.

Ideal for companion/conversational agents that need cross-session memory
with automatic fact extraction and relationship tracking.
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


class ZepMemoryStore:
    """Zep implementation of MemoryStore protocol.

    Uses zep-python SDK for long-term agent memory with:
    - Temporal awareness (auto-timestamped facts)
    - Entity extraction and relationship graphs
    - Semantic search over memory
    - Session-scoped and user-scoped memory
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        from zep_cloud.client import Zep

        self._client = Zep(api_key=api_key, base_url=base_url)
        self._local_index: dict[str, Memory] = {}

    def store(
        self,
        user_id: str,
        content: str,
        memory_type: str = "short_term",
        category: str = "custom",
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        expires_at = _utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None

        # Add as a message to Zep session (Zep extracts facts automatically)
        from zep_cloud.types import Message

        self._client.memory.add(
            session_id=user_id,
            messages=[Message(
                role_type="user",
                role="system",
                content=content,
                metadata={
                    "memory_id": memory_id,
                    "memory_type": memory_type,
                    "category": category,
                    **(metadata or {}),
                },
            )],
        )

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
        return memory

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        result = self._client.memory.search_sessions(
            text=query.query,
            user_id=query.user_id,
            search_scope="facts",
            limit=query.limit,
        )

        memories = []
        for item in result.results or []:
            score = item.score if hasattr(item, "score") else 0.5
            if score < query.min_relevance:
                continue
            content = item.fact.content if hasattr(item, "fact") else str(item)
            mem = Memory(
                id=str(uuid.uuid4()),
                user_id=query.user_id,
                content=content,
                memory_type="long_term",
                category=MemoryCategory.FACT,
                relevance_score=min(score, 1.0),
            )
            memories.append(mem)
        return memories[:query.limit]

    def get(self, memory_id: str) -> Memory | None:
        return self._local_index.get(memory_id)

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        session_memory = self._client.memory.get(session_id=user_id)
        memories = []
        for fact in session_memory.facts or []:
            mem = Memory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                content=fact.content if hasattr(fact, "content") else str(fact),
                memory_type="long_term",
                category=MemoryCategory.FACT,
            )
            memories.append(mem)
            if len(memories) >= limit:
                break
        return memories

    def delete(self, memory_id: str) -> bool:
        return self._local_index.pop(memory_id, None) is not None

    def delete_user_memories(self, user_id: str) -> int:
        try:
            self._client.memory.delete(session_id=user_id)
        except Exception:
            pass
        removed = [k for k, v in self._local_index.items() if v.user_id == user_id]
        for k in removed:
            del self._local_index[k]
        return len(removed)

    def consolidate(self, user_id: str) -> int:
        # Zep handles consolidation automatically via its fact extraction pipeline
        return 0

    def stats(self, user_id: str | None = None) -> MemoryStats:
        count = 0
        if user_id:
            try:
                session_memory = self._client.memory.get(session_id=user_id)
                count = len(session_memory.facts or [])
            except Exception:
                pass
        return MemoryStats(total_memories=count, by_type={"long_term": count})

    def health_check(self) -> MemoryHealth:
        start = time.perf_counter()
        try:
            # Lightweight probe — list sessions with limit 1
            self._client.memory.list_sessions(limit=1)
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=True, backend="zep", latency_ms=latency,
                message="Zep connected",
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=False, backend="zep", latency_ms=latency,
                message=f"Zep error: {e}",
            )
