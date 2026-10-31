"""A-MEM query and CRUD operations mixin.

Split from amem.py to stay under 200 LOC. Provides retrieve, get,
list_all, delete, consolidate, stats, and health_check methods.
"""

from __future__ import annotations

import time
from typing import Any

from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats
from factory.memory.runtime.adapters.amem_helpers import (
    flatten_meta,
    meta_to_memory,
    unflatten_meta,
)


class AMemQueryMixin:
    """Query/CRUD methods for AMemStore. Mixed into the main class."""

    # These attributes are set by AMemStore.__init__
    _collection: Any
    _cache: Any
    _evo_count: int

    def _load_meta(self, mid: str) -> dict[str, Any] | None:
        """Load metadata from cache or ChromaDB."""
        cached = self._cache.get(mid)
        if cached:
            return cached
        try:
            result = self._collection.get(ids=[mid])
            if result["ids"]:
                meta = unflatten_meta(result["metadatas"][0])
                doc = result["documents"][0] if result.get("documents") else ""
                meta["content"] = doc
                self._cache.put(mid, meta)
                return meta
        except Exception:
            pass
        return None

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        """Semantic search via ChromaDB vector similarity.

        bd:python-factory-26e2a (tags) + python-factory-b2d2o (metadata)
        push-down: SKIPPED here (Tier 2). ``amem_helpers.flatten_meta``
        JSON-encodes the entire ``metadata`` dict (including caller
        ``tags`` and arbitrary keys) into single string columns. So
        ``where={"tags": {"$in": [...]}}`` would compare to the literal
        JSON-string and ``where={"meta_run_id": "v"}`` would never bind
        because ``amem.py:103`` puts caller metadata at
        ``meta["extra"] = metadata`` rather than promoting keys to
        column names. Native push-down skipped — runtime post-filter at
        ``MemoryRuntime.retrieve`` covers ``query.tags`` AND
        ``query.metadata`` via the defense-in-depth path inherited by
        all adapters.
        """
        try:
            results = self._collection.query(
                query_texts=[query.query],
                n_results=query.limit * 2,
                where={"user_id": query.user_id},
            )
        except Exception:
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        memories: list[Memory] = []
        for i, mid in enumerate(results["ids"][0]):
            meta = self._load_meta(mid)
            if not meta:
                continue
            dist = results["distances"][0][i] if results.get("distances") else 0.0
            score = max(0.0, min(1.0, 1.0 - dist))
            if score < query.min_relevance:
                continue
            if query.memory_type and meta.get("memory_type") != query.memory_type:
                continue
            if query.category and meta.get("category") != query.category.value:
                continue
            memories.append(meta_to_memory(meta, score))
            if len(memories) >= query.limit:
                break
        return memories

    def get(self, memory_id: str) -> Memory | None:
        meta = self._load_meta(memory_id)
        return meta_to_memory(meta) if meta else None

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        try:
            results = self._collection.get(
                where={"user_id": user_id}, limit=limit,
            )
        except Exception:
            return []
        memories: list[Memory] = []
        for i, mid in enumerate(results["ids"]):
            meta_raw = results["metadatas"][i] if results.get("metadatas") else {}
            meta = unflatten_meta(meta_raw)
            doc = results["documents"][i] if results.get("documents") else ""
            meta["content"] = doc
            self._cache.put(mid, meta)
            memories.append(meta_to_memory(meta))
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:limit]

    def delete(self, memory_id: str) -> bool:
        try:
            self._collection.delete(ids=[memory_id])
            self._cache.pop(memory_id)
            return True
        except Exception:
            return False

    def delete_user_memories(self, user_id: str) -> int:
        try:
            results = self._collection.get(where={"user_id": user_id})
            ids = results["ids"]
            if ids:
                self._collection.delete(ids=ids)
                for mid in ids:
                    self._cache.pop(mid)
            return len(ids)
        except Exception:
            return 0

    def consolidate(self, user_id: str) -> int:
        try:
            results = self._collection.get(
                where={"$and": [
                    {"user_id": user_id},
                    {"memory_type": "short_term"},
                ]},
            )
            ids = results["ids"]
            for i, mid in enumerate(ids):
                meta_raw = results["metadatas"][i]
                meta_raw["memory_type"] = "long_term"
                self._collection.update(ids=[mid], metadatas=[meta_raw])
                cached = self._cache.get(mid)
                if cached:
                    cached["memory_type"] = "long_term"
            return len(ids)
        except Exception:
            return 0

    def stats(self, user_id: str | None = None) -> MemoryStats:
        try:
            if user_id:
                results = self._collection.get(where={"user_id": user_id})
            else:
                results = self._collection.get()
            by_type: dict[str, int] = {}
            by_cat: dict[str, int] = {}
            for meta in results.get("metadatas", []):
                t = meta.get("memory_type", "short_term")
                c = meta.get("category", "custom")
                by_type[t] = by_type.get(t, 0) + 1
                by_cat[c] = by_cat.get(c, 0) + 1
            return MemoryStats(
                total_memories=len(results["ids"]),
                by_type=by_type,
                by_category=by_cat,
            )
        except Exception:
            return MemoryStats()

    def health_check(self) -> MemoryHealth:
        start = time.perf_counter()
        try:
            count = self._collection.count()
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=True,
                backend="amem",
                latency_ms=latency,
                message=f"ChromaDB OK ({count} memories, {self._evo_count} evolutions)",
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return MemoryHealth(
                healthy=False, backend="amem",
                latency_ms=latency, message=str(e),
            )
