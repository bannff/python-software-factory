"""Runtime helper for memory evolution (A-MEM backfill)."""

from __future__ import annotations

from typing import Any

from factory.memory.runtime.runtime import MemoryRuntime


def run_evolve(runtime: MemoryRuntime, user_id: str, memory_ids: list[str] | None) -> dict[str, Any]:
    """Run A-MEM evolution on memories that missed it at store time.

    Validates the runtime store, builds the search function, and delegates
    to evolve_memories. Returns a summary dict.
    """
    from factory.memory.mcp.hybrid_tools import _get_neo4j_driver, _get_embedder
    from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
    from factory.memory.runtime.evolve_backfill import evolve_memories, fetch_unevolved_memories
    from factory.memory.runtime.models import MemoryQuery

    store = runtime._store  # noqa: SLF001
    driver, database = _get_neo4j_driver(store)
    embedder = _get_embedder(store)

    if driver is None or embedder is None:
        return {"error": "Requires neo4j backend with embeddings enabled"}
    if not isinstance(store, Neo4jEmbeddingMemoryStore):
        return {"error": "Evolution requires Neo4jEmbeddingMemoryStore"}

    llm_complete = store._llm_complete  # noqa: SLF001
    if llm_complete is None:
        return {"error": "Evolution requires llm_complete (LLM gateway not configured)"}

    records = fetch_unevolved_memories(driver, database, user_id, memory_ids)
    if not records:
        return {"evolved_count": 0, "failed_count": 0, "details": []}

    def _make_search_fn(content: str, uid: str):
        def _search():
            vecs = embedder.embed([content])
            if not (vecs and vecs[0]):
                return []
            q = MemoryQuery(query=content, user_id=uid, limit=5, min_relevance=0.0)
            return store._vector_search(q, vecs[0])  # noqa: SLF001
        return _search

    return evolve_memories(
        driver, database, user_id, llm_complete, embedder,
        _make_search_fn, records,
    )
