"""Memory runtime - orchestrates memory operations."""

from __future__ import annotations

from typing import Any

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.bulk_delete_support import bulk_match
from factory.memory.runtime.learning_emit import emit_learning_applied
from factory.memory.runtime.memory_filters import matches_metadata, matches_tags
from factory.memory.runtime.models import (
    Memory,
    MemoryHealth,
    MemoryQuery,
    MemoryStats,
    Settings,
)
from factory.memory.runtime.ports import MemoryStore


class MemoryRuntime:
    """Main runtime for memory operations."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._store = store or InMemoryStore()

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        return self._settings

    @property
    def adapter(self) -> MemoryStore:
        """The active storage adapter — read-only introspection (e.g. the
        Embeddings status tool needs to know if the graph adapter with a
        real embedder is active). Never used to bypass the runtime's own
        methods for a mutation. Named ``adapter`` (not ``store``) because
        ``store()`` is already this class's mutation verb."""
        return self._store

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
        ttl = ttl_seconds or self._settings.default_ttl_seconds
        return self._store.store(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            category=category,
            metadata=metadata,
            ttl_seconds=ttl,
        )

    def retrieve(
        self,
        user_id: str,
        query: str,
        memory_type: str | None = None,
        category: str | None = None,
        min_relevance: float = 0.3,
        limit: int = 5,
        tags: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[Memory]:
        """Retrieve memories matching a query.

        ``tags`` (bd:python-factory-lin6p) filters to memories whose
        ``metadata.tags`` overlap with the supplied list (ANY-match).
        ``None`` (default) preserves today's behaviour. ``[]`` matches
        nothing — distinct from ``None``. Post-filter at the runtime
        layer so the ``MemoryStore`` Protocol stays clean; tier 2/3
        adapters that don't push down inherit the filter for free.

        ``metadata`` (bd:python-factory-b2d2o) per-key AND filter on
        ``memory.metadata``. ``None`` and ``{}`` BOTH = no filter
        (asymmetric vs ``tags=[]``). Composes AND with ``tags`` filter
        when both set. Apply order: tags -> metadata.
        """
        q = MemoryQuery(
            user_id=user_id,
            query=query,
            memory_type=memory_type,  # type: ignore
            category=category,  # type: ignore
            min_relevance=min_relevance,
            limit=limit,
            tags=tags,
            metadata=metadata,
        )
        memories = self._store.retrieve(q)
        if tags is not None:
            memories = [m for m in memories if matches_tags(m, tags)]
        if metadata:
            # Truthy check intentionally treats both None and {} as "no
            # filter" per b2d2o asymmetric default (verdict f279063c Q4).
            memories = [m for m in memories if matches_metadata(m, metadata)]
        emit_learning_applied(memories, query, user_id)
        return memories

    def get(self, memory_id: str) -> Memory | None:
        """Get a specific memory by ID."""
        return self._store.get(memory_id)

    def list_all(self, user_id: str, limit: int = 100, metadata: dict[str, str] | None = None) -> list[Memory]:
        """List all memories for a user.

        ``metadata`` (owner ruling 2026-09-16 06:32 — rows 44/45 scope
        filter): same per-key AND filter as ``retrieve()``'s, post-applied
        here for the same reason (``MemoryStore`` Protocol stays clean;
        every adapter inherits it for free). ``None``/``{}`` = no filter.
        This is the read path the Memory tab's default (no-query) browse
        view actually uses — the scope filter needs it here too, not just
        on ``retrieve()``, or it would silently do nothing until the user
        typed a search term.
        """
        memories = self._store.list_all(user_id, limit)
        if metadata:
            memories = [m for m in memories if matches_metadata(m, metadata)]
        return memories

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        return self._store.delete(memory_id)

    def bulk_match(
        self, user_id: str, query: str | None = None,
        memory_type: str | None = None, metadata: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[Memory]:
        """Row 43 bulk correction's match set — see ``bulk_delete_support.py``."""
        return bulk_match(self, user_id, query, memory_type, metadata, limit)

    def bulk_delete(
        self, user_id: str, query: str | None = None,
        memory_type: str | None = None, metadata: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[str]:
        """Delete every memory ``bulk_match`` finds; returns deleted ids."""
        matched = self.bulk_match(user_id, query, memory_type=memory_type, metadata=metadata, limit=limit)
        return [m.id for m in matched if self._store.delete(m.id)]

    def update(self, memory_id: str, content: str) -> Memory | None:
        """Correct a memory's content in place (row 43 single correction).

        ``None`` when the memory does not exist OR the active adapter has
        no update primitive (same graceful-degradation shape as
        ``recall_path``) — the caller distinguishes the two the same way
        the FE already distinguishes "not supported" from "not found":
        by also checking ``get(memory_id)`` first if it needs to.
        """
        method = getattr(self._store, "update", None)
        return method(memory_id, content) if callable(method) else None

    def delete_user_memories(self, user_id: str) -> int:
        """Delete all memories for a user."""
        return self._store.delete_user_memories(user_id)

    def consolidate(self, user_id: str) -> int:
        """Consolidate short-term to long-term memories."""
        return self._store.consolidate(user_id)

    def stats(self, user_id: str | None = None) -> MemoryStats:
        """Get memory statistics."""
        return self._store.stats(user_id)

    def health_check(self) -> MemoryHealth:
        """Check backend health."""
        return self._store.health_check()

    def recall_path(self, memory_id: str) -> dict[str, Any] | None:
        """Row 45's recall inspection (owner direction 2026-09-16): the
        real graph neighborhood around one memory. ``None`` when the
        active adapter has no graph substrate to inspect (e.g. the plain
        in-memory adapter) — the FE distinguishes "not supported here"
        from "no neighbors found" (an empty-but-present dict)."""
        method = getattr(self._store, "recall_path", None)
        return method(memory_id) if callable(method) else None

    def history(self, memory_id: str) -> list[Memory] | None:
        """Row 47's replaced-experiences history — every version of the
        chain containing ``memory_id``, newest first. ``None`` (not an
        empty list) when the active adapter has no supersession substrate
        to inspect — same "not supported" vs. "no history" distinction as
        ``recall_path``. Informational only: no restore action exists here
        by owner ruling (see ``graph_supersession.py`` module docstring —
        "never a user-facing restore action")."""
        method = getattr(self._store, "history", None)
        return method(memory_id) if callable(method) else None
