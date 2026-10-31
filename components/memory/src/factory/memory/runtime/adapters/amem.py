"""A-MEM adapter — self-evolving Zettelkasten memory with ChromaDB.

Implements MemoryStore protocol with:
- ChromaDB for vector storage and semantic search
- LLM-driven content analysis (keyword/context/tag extraction)
- Memory evolution (new memories trigger neighbor updates)
- LRU cache for fast reads

Requires: chromadb, sentence-transformers (via chromadb)
LLM calls go through llm_gateway (polymorphic, no hardcoded backend).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import timedelta
from typing import Any

from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory
from factory.memory.runtime.evolution import (
    EvolutionEngine,
    NeighborInfo,
    analyze_content,
)
from factory.memory.runtime.adapters.amem_helpers import (
    LRUCache,
    flatten_meta,
    utcnow,
)
from factory.memory.runtime.adapters.amem_queries import AMemQueryMixin

logger = logging.getLogger(__name__)

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None  # type: ignore[assignment]


class AMemStore(AMemQueryMixin):
    """A-MEM implementation of MemoryStore protocol.

    Self-evolving memory with ChromaDB vector storage and LLM-driven
    Zettelkasten-style evolution.
    """

    def __init__(
        self,
        storage_path: str | None = None,
        llm_complete: Any | None = None,
        evo_threshold: int = 100,
        cache_size: int = 1000,
    ) -> None:
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb required: pip install chromadb")

        self._storage_path = storage_path or os.environ.get(
            "AMEM_STORAGE_PATH", "./chroma_db"
        )
        self._evo_threshold = evo_threshold
        self._evo_count = 0

        self._client = chromadb.PersistentClient(path=self._storage_path)
        self._collection = self._client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )

        self._cache = LRUCache(max_size=cache_size)
        self._llm_complete = llm_complete
        self._engine: EvolutionEngine | None = None

    def _get_engine(self) -> EvolutionEngine | None:
        if self._engine is None and self._llm_complete is not None:
            self._engine = EvolutionEngine(self._llm_complete)
        return self._engine

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
        now = utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None

        analysis = {"keywords": [], "context": "General", "tags": []}
        if self._llm_complete:
            analysis = analyze_content(self._llm_complete, content)

        meta: dict[str, Any] = {
            "id": memory_id, "user_id": user_id, "content": content,
            "memory_type": memory_type, "category": category,
            "created_at": now.isoformat(),
            "keywords": analysis.get("keywords", []),
            "context": analysis.get("context", "General"),
            "tags": analysis.get("tags", []),
            "links": [], "retrieval_count": 0,
        }
        if expires_at:
            meta["expires_at"] = expires_at.isoformat()
        if metadata:
            meta["extra"] = metadata

        engine = self._get_engine()
        if engine and self._collection.count() > 0:
            self._evolve(engine, meta)

        self._collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[flatten_meta(meta)],
        )
        self._cache.put(memory_id, meta)

        return Memory(
            id=memory_id, user_id=user_id, content=content,
            memory_type=memory_type, category=MemoryCategory(category),
            metadata=metadata or {}, expires_at=expires_at, created_at=now,
        )

    def _evolve(self, engine: EvolutionEngine, meta: dict[str, Any]) -> None:
        """Run evolution: find neighbors, analyze, apply updates."""
        try:
            results = self._collection.query(
                query_texts=[meta["content"]],
                n_results=5,
                where={"user_id": meta["user_id"]},
            )
            if not results["ids"] or not results["ids"][0]:
                return

            neighbors = []
            for nid in results["ids"][0]:
                nmeta = self._load_meta(nid)
                if nmeta:
                    neighbors.append(NeighborInfo(
                        memory_id=nid, content=nmeta.get("content", ""),
                        context=nmeta.get("context", ""),
                        keywords=nmeta.get("keywords", []),
                        tags=nmeta.get("tags", []),
                    ))

            result = engine.analyze(
                content=meta["content"], context=meta.get("context", ""),
                keywords=meta.get("keywords", []),
                tags=meta.get("tags", []), neighbors=neighbors,
            )
            if not result.should_evolve:
                return

            if result.connections:
                meta["links"] = result.connections
            if result.tags:
                meta["tags"] = result.tags
            for update in result.neighbor_updates:
                self._apply_neighbor_update(update)
            self._evo_count += 1
        except Exception as e:
            logger.warning("Evolution failed: %s", e)

    def _apply_neighbor_update(self, update: dict[str, Any]) -> None:
        """Apply a single neighbor update from evolution."""
        nid = update["memory_id"]
        nmeta = self._load_meta(nid)
        if not nmeta:
            return
        if "context" in update:
            nmeta["context"] = update["context"]
        if "tags" in update:
            nmeta["tags"] = update["tags"]
        self._collection.update(
            ids=[nid], metadatas=[flatten_meta(nmeta)],
        )
        self._cache.put(nid, nmeta)
