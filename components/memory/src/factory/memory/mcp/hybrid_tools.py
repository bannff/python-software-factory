"""Typed MCP tools for hybrid Memory search and embedding maintenance."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from factory.memory.runtime.runtime import MemoryRuntime

from .contracts.advanced import (
    EmbedBackfillInput, EmbedBackfillOutput, HybridSearchInput, HybridSearchOutput,
)


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register the three existing operational Memory tools unchanged."""

    @mcp.tool()
    @operational(input_model=HybridSearchInput, output_model=HybridSearchOutput)
    def memory_hybrid_search(user_id: str, query: str | None = None, anchor_memory_id: str | None = None, limit: int = 10, semantic_weight: float = 0.5, structural_weight: float = 0.3, traversal_weight: float = 0.2) -> ToolResult[HybridSearchOutput]:
        store = runtime._store  # noqa: SLF001
        driver, database = _get_neo4j_driver(store)
        if driver is None:
            return {"available": False, "error": "Hybrid search requires neo4j backend"}
        from factory.memory.runtime.hybrid import hybrid_search
        results = hybrid_search(driver=driver, database=database, user_id=user_id, query_vector=_embed_query(store, query), anchor_memory_id=anchor_memory_id, limit=limit, semantic_weight=semantic_weight, structural_weight=structural_weight, traversal_weight=traversal_weight)
        return {"available": True, "results": results, "count": len(results)}

    @mcp.tool()
    @operational(input_model=EmbedBackfillInput, output_model=EmbedBackfillOutput)
    def memory_embed_backfill(user_id: str, limit: int = 100) -> ToolResult[EmbedBackfillOutput]:
        store = runtime._store  # noqa: SLF001
        driver, database = _get_neo4j_driver(store)
        embedder = _get_embedder(store)
        if driver is None or embedder is None:
            return {"available": False, "user_id": user_id, "error": "Requires neo4j backend with embeddings enabled"}
        records = _unembedded_records(driver, database, user_id, limit)
        embedded = _backfill_records(driver, database, embedder, records)
        return {"available": True, "user_id": user_id, "embedded": embedded, "total_checked": len(records)}


def _unembedded_records(driver: Any, database: str, user_id: str, limit: int) -> list[Any]:
    with driver.session(database=database) as session:
        return list(session.run("MATCH (m:Memory {user_id: $uid}) WHERE m.embedding IS NULL RETURN m.id AS id, m.content AS content LIMIT $lim", uid=user_id, lim=limit))


def _backfill_records(driver: Any, database: str, embedder: Any, records: list[Any]) -> int:
    embedded = 0
    for record in records:
        try:
            vectors = embedder.embed([record["content"]])
            if vectors and vectors[0]:
                with driver.session(database=database) as session:
                    session.run("MATCH (m:Memory {id: $id}) SET m.embedding = $vec", id=record["id"], vec=vectors[0])
                embedded += 1
        except Exception:
            continue
    return embedded


def _get_neo4j_driver(store: Any) -> tuple[Any, str]:
    from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
    from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
    if isinstance(store, Neo4jEmbeddingMemoryStore):
        return store._base.driver, store._base.database  # noqa: SLF001
    if isinstance(store, Neo4jMemoryStore):
        return store.driver, store.database
    return None, "neo4j"


def _get_embedder(store: Any) -> Any:
    from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
    return store._embedder if isinstance(store, Neo4jEmbeddingMemoryStore) else None  # noqa: SLF001


def _embed_query(store: Any, query: str | None) -> list[float] | None:
    if not query or (embedder := _get_embedder(store)) is None:
        return None
    try:
        vectors = embedder.embed([query])
        return vectors[0] if vectors else None
    except Exception:
        return None
