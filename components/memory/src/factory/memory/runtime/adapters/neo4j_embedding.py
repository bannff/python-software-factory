"""Embedding-enhanced Neo4j memory store with HNSW vector search."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats
from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore, to_memory
from factory.memory.runtime.adapters._neo4j_filters import build_filter_clauses
from factory.memory.runtime.emit import emit_memory_event

logger = logging.getLogger(__name__)

class Neo4jEmbeddingMemoryStore:
    def __init__(self, base: Neo4jMemoryStore, embedder: Any,
                 llm_complete: Any | None = None) -> None:
        self._base = base
        self._embedder = embedder
        self._llm_complete = llm_complete
        self._engine: Any = None
        self._ensure_vector_index()
        if llm_complete:
            self._ensure_evolution_constraints()

    def _get_engine(self) -> Any:
        if self._engine is None and self._llm_complete is not None:
            from factory.memory.runtime.evolution import EvolutionEngine
            self._engine = EvolutionEngine(self._llm_complete)
        return self._engine

    def _session(self) -> Any:
        return self._base.driver.session(database=self._base.database)

    def _ensure_vector_index(self) -> None:
        dims = self._embedder.dimensions
        if dims <= 0:
            return
        with self._session() as s:
            try:
                s.run(
                    "CREATE VECTOR INDEX memory_embedding IF NOT EXISTS "
                    "FOR (m:Memory) ON (m.embedding) OPTIONS {indexConfig: {"
                    "`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}",
                    dims=dims)
            except Exception:
                pass
    def _ensure_evolution_constraints(self) -> None:
        with self._session() as s:
            for q in ["CREATE INDEX mem_keywords IF NOT EXISTS FOR (m:Memory) ON (m.keywords)",
                      "CREATE INDEX mem_tags IF NOT EXISTS FOR (m:Memory) ON (m.tags)"]:
                try: s.run(q)
                except Exception: pass

    def _set_evolution_status(self, mid: str, status: str) -> None:
        with self._session() as s:
            s.run("MATCH (m:Memory {id: $id}) SET m.evolution_status = $s", id=mid, s=status)

    def _embed_and_set(self, memory_id: str, content: str) -> None:
        try:
            vectors = self._embedder.embed([content])
            if vectors and vectors[0]:
                with self._session() as s:
                    s.run("MATCH (m:Memory {id: $id}) SET m.embedding = $vec",
                          id=memory_id, vec=vectors[0])
        except Exception as e:
            logger.warning("Embedding failed for %s: %s", memory_id, e)
            emit_memory_event("memory.embed.failed",
                              {"memory_id": memory_id, "error": str(e)})
    def _link_temporal(self, memory: Memory) -> None:
        try:
            with self._session() as s:
                s.run(
                    "MATCH (prev:Memory {user_id: $uid}), (new:Memory {id: $mid}) "
                    "WHERE prev.id <> $mid AND prev.created_at IS NOT NULL "
                    "WITH prev, new ORDER BY prev.created_at DESC LIMIT 1 "
                    "CREATE (prev)-[:FOLLOWED_BY {created_at: $now}]->(new)",
                    uid=memory.user_id, mid=memory.id,
                    now=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.warning("Temporal linking failed for %s: %s", memory.id, e)
    def store(self, user_id: str, content: str, memory_type: str = "short_term",
              category: str = "custom", metadata: dict[str, Any] | None = None,
              ttl_seconds: int | None = None) -> Memory:
        memory = self._base.store(user_id, content, memory_type, category, metadata, ttl_seconds)
        self._embed_and_set(memory.id, content)
        self._link_temporal(memory)
        if self._llm_complete:
            self._store_with_evolution(memory, content)
        else:
            self._set_evolution_status(memory.id, "pending")
        emit_memory_event("memory.store", {
            "memory_id": memory.id, "category": category,
            "memory_type": memory_type, "has_embedding": True}, user_id=user_id)
        return memory

    def _store_with_evolution(self, memory: Memory, content: str) -> None:
        from factory.memory.runtime.adapters.neo4j_evolution import (
            run_content_analysis, set_evolution_properties)
        try:
            analysis = run_content_analysis(self._llm_complete, content)
            is_fallback = not analysis.get("keywords") and analysis.get("context") == "General"
            set_evolution_properties(
                self._base.driver, self._base.database, memory.id, analysis,
                evolution_status="failed" if is_fallback else "success")
            if is_fallback:
                emit_memory_event("memory.evolve.failed",
                                  {"memory_id": memory.id, "reason": "llm_fallback"},
                                  user_id=memory.user_id)
            else:
                emit_memory_event("memory.evolve.success", {
                    "memory_id": memory.id,
                    "keywords_count": len(analysis.get("keywords", []))},
                    user_id=memory.user_id)
                engine = self._get_engine()
                if engine:
                    self._run_evolution(engine, memory, analysis)
        except Exception as e:
            logger.warning("Evolution failed for %s: %s", memory.id, e)
            emit_memory_event("memory.evolve.failed",
                              {"memory_id": memory.id, "error": str(e)}, user_id=memory.user_id)
            set_evolution_properties(
                self._base.driver, self._base.database, memory.id,
                {"keywords": [], "context": "General", "tags": []},
                evolution_status="failed")

    def _run_evolution(self, engine: Any, memory: Memory, analysis: dict[str, Any]) -> None:
        from factory.memory.runtime.adapters.neo4j_evolution import evolve
        with self._session() as s:
            rec = s.run(
                "MATCH (m:Memory {user_id: $uid}) WHERE m.id <> $mid RETURN count(m) AS c",
                uid=memory.user_id, mid=memory.id).single()
        if not rec or rec["c"] == 0:
            return
        try:
            vecs = self._embedder.embed([memory.content])
            vec = vecs[0] if vecs and vecs[0] else None
        except Exception:
            vec = None
        search_q = MemoryQuery(query=memory.content, user_id=memory.user_id, limit=5, min_relevance=0.0)
        search_fn = (lambda: self._vector_search(search_q, vec)) if vec else (lambda: [])
        evolve(engine, self._base.driver, self._base.database,
               memory.id, memory.user_id, memory.content, analysis,
               search_fn, memory_embedding=vec)

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        """Semantic retrieval via HNSW, fallback to text search."""
        method, results = "text_fallback", None
        try:
            vectors = self._embedder.embed([query.query])
            if vectors and vectors[0]:
                results = self._vector_search(query, vectors[0])
                method = "vector"
        except Exception as e:
            logger.warning("Vector retrieval failed (query=%r), text fallback: %s",
                           query.query[:50], e)
            emit_memory_event("memory.retrieve.embedding_failed", {
                "query_length": len(query.query), "error": str(e)[:200],
                "method": "text_fallback"}, user_id=query.user_id)
        if results is None:
            results = self._base.retrieve(query)
        emit_memory_event("memory.retrieve", {
            "query_length": len(query.query), "result_count": len(results),
            "method": method}, user_id=query.user_id)
        return results

    def _vector_search(self, query: MemoryQuery, vec: list[float]) -> list[Memory]:
        # Tags + metadata push-down (bd:python-factory-26e2a + b2d2o).
        # HNSW WHERE-clause already filters user_id+min_relevance; the
        # conditional ANY-match on m.tags + per-key m.meta_<k> piggy-back
        # there via _neo4j_filters.build_filter_clauses.
        params: dict[str, Any] = {
            "vec": vec, "k": query.limit * 3, "uid": query.user_id,
            "min_rel": query.min_relevance, "lim": query.limit,
        }
        filter_clauses = build_filter_clauses(query, params)
        cypher = (
            "CALL db.index.vector.queryNodes('memory_embedding', $k, $vec) "
            "YIELD node AS m, score WHERE m.user_id = $uid AND score >= $min_rel"
            f"{filter_clauses} RETURN m, score ORDER BY score DESC LIMIT $lim")
        with self._session() as s:
            recs = list(s.run(cypher, **params))
        return [to_memory(r["m"], r["score"]) for r in recs] if recs else self._base.retrieve(query)

    # Delegate all other methods to base store
    def get(self, memory_id: str) -> Memory | None: return self._base.get(memory_id)
    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]: return self._base.list_all(user_id, limit)
    def delete(self, memory_id: str) -> bool: return self._base.delete(memory_id)
    def delete_user_memories(self, user_id: str) -> int: return self._base.delete_user_memories(user_id)
    def consolidate(self, user_id: str) -> int: return self._base.consolidate(user_id)
    def stats(self, user_id: str | None = None) -> MemoryStats: return self._base.stats(user_id)

    def health_check(self) -> MemoryHealth:
        health = self._base.health_check()
        if health.healthy:
            health.message = (f"Neo4j connected (embeddings: enabled, evolution: "
                              f"{'enabled' if self._llm_complete else 'disabled'})")
        return health