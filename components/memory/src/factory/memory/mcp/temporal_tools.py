"""MCP tools for temporal memory search.

Enables time-range queries on memories, optionally combined with
semantic similarity filtering via HNSW vector search.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from .contracts.advanced import SearchByTimeInput, SearchByTimeOutput

from factory.memory.runtime.runtime import MemoryRuntime


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register temporal search tools."""

    @mcp.tool()
    @operational(input_model=SearchByTimeInput, output_model=SearchByTimeOutput)
    def memory_search_by_time(
        user_id: str | None = None,
        time_from: str | None = None,
        time_to: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> ToolResult[SearchByTimeOutput]:
        """Search memories within a time range, optionally filtered by semantic query.

        Time-only mode returns memories ordered by recency. When a query is
        provided, HNSW vector search finds semantic candidates first, then
        filters by the time window.

        Args:
            user_id: User whose memories to search (optional when authenticated)
            time_from: Start of time range (ISO-8601, inclusive)
            time_to: End of time range (ISO-8601, inclusive)
            query: Optional semantic query to combine with time filter
            limit: Maximum results to return
        """
        if user_id is None:
            from factory.mcp_utils.interface import get_principal_id
            user_id = get_principal_id()
        if user_id is None:
            return {"available": False, "error": "user_id required: pass explicitly or authenticate via Bearer token"}

        if not time_from and not time_to:
            return {"available": False, "error": "At least one of time_from or time_to is required"}

        store = runtime._store  # noqa: SLF001
        driver, database = _get_neo4j_driver(store)
        if driver is None:
            return {"available": False, "error": "Temporal search requires neo4j backend"}

        if query:
            results = _semantic_time_search(
                store, driver, database, user_id, query, time_from, time_to, limit,
            )
        else:
            results = _time_only_search(
                driver, database, user_id, time_from, time_to, limit,
            )

        return {"available": True, "results": results, "count": len(results)}


def _time_only_search(
    driver: Any, database: str, user_id: str,
    time_from: str | None, time_to: str | None, limit: int,
) -> list[dict[str, Any]]:
    """Query memories by time range only, ordered by recency."""
    from factory.memory.runtime.adapters.neo4j import to_memory

    clauses = ["m.user_id = $uid"]
    params: dict[str, Any] = {"uid": user_id, "lim": limit}
    if time_from:
        clauses.append("m.created_at >= $t_from")
        params["t_from"] = time_from
    if time_to:
        clauses.append("m.created_at <= $t_to")
        params["t_to"] = time_to

    where = " AND ".join(clauses)
    cypher = (
        f"MATCH (m:Memory) WHERE {where} "
        "RETURN m ORDER BY m.created_at DESC LIMIT $lim"
    )
    with driver.session(database=database) as s:
        records = list(s.run(cypher, **params))
    return [to_memory(r["m"], score=1.0).model_dump() for r in records]


def _semantic_time_search(
    store: Any, driver: Any, database: str, user_id: str,
    query: str, time_from: str | None, time_to: str | None, limit: int,
) -> list[dict[str, Any]]:
    """Vector search candidates filtered by time range in Cypher."""
    from factory.memory.runtime.adapters.neo4j import to_memory
    from factory.memory.mcp.hybrid_tools import _get_embedder

    embedder = _get_embedder(store)
    if embedder is None:
        return _time_only_search(driver, database, user_id, time_from, time_to, limit)

    try:
        vecs = embedder.embed([query])
        if not (vecs and vecs[0]):
            return _time_only_search(driver, database, user_id, time_from, time_to, limit)
    except Exception:
        return _time_only_search(driver, database, user_id, time_from, time_to, limit)

    time_clauses: list[str] = []
    params: dict[str, Any] = {
        "vec": vecs[0], "k": limit * 3, "uid": user_id, "lim": limit,
    }
    if time_from:
        time_clauses.append("m.created_at >= $t_from")
        params["t_from"] = time_from
    if time_to:
        time_clauses.append("m.created_at <= $t_to")
        params["t_to"] = time_to

    time_filter = " AND " + " AND ".join(time_clauses) if time_clauses else ""
    cypher = (
        "CALL db.index.vector.queryNodes('memory_embedding', $k, $vec) "
        "YIELD node AS m, score "
        f"WHERE m.user_id = $uid{time_filter} "
        "RETURN m, score ORDER BY score DESC LIMIT $lim"
    )
    with driver.session(database=database) as s:
        records = list(s.run(cypher, **params))

    if not records:
        return _time_only_search(driver, database, user_id, time_from, time_to, limit)

    return [to_memory(r["m"], r["score"]).model_dump() for r in records]


def _get_neo4j_driver(store: Any) -> tuple[Any, str]:
    """Extract Neo4j driver from the store chain."""
    from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
    from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
    if isinstance(store, Neo4jEmbeddingMemoryStore):
        return store._base.driver, store._base.database  # noqa: SLF001
    if isinstance(store, Neo4jMemoryStore):
        return store.driver, store.database
    return None, "neo4j"
