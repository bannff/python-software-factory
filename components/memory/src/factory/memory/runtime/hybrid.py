"""Hybrid memory search: semantic + structural + graph traversal.

Combines three retrieval signals:
1. Semantic similarity — HNSW vector search on Memory.embedding
2. Structural similarity — GDS embeddings (FastRP) on Memory.structural_embedding
3. Graph traversal — FOLLOWED_BY temporal chains and HAS_MEMORY ownership

Results are fused via reciprocal rank fusion (RRF).
"""

from __future__ import annotations

from typing import Any

from factory.memory.runtime.models import Memory
from factory.memory.runtime.adapters.neo4j import to_memory


def hybrid_search(
    driver: Any,
    database: str,
    user_id: str,
    query_vector: list[float] | None = None,
    anchor_memory_id: str | None = None,
    limit: int = 10,
    semantic_weight: float = 0.5,
    structural_weight: float = 0.3,
    traversal_weight: float = 0.2,
) -> list[dict[str, Any]]:
    """Run hybrid search combining semantic, structural, and graph signals.

    Args:
        driver: Neo4j driver instance
        database: Neo4j database name
        user_id: Filter to this user's memories
        query_vector: Semantic embedding of the query (for HNSW search)
        anchor_memory_id: Starting memory for graph traversal + structural
        limit: Max results to return
        semantic_weight: Weight for semantic similarity (0-1)
        structural_weight: Weight for structural similarity (0-1)
        traversal_weight: Weight for graph traversal proximity (0-1)

    Returns:
        List of dicts with memory, scores, and signal breakdown
    """
    scores: dict[str, dict[str, float]] = {}

    if query_vector:
        _add_semantic_scores(driver, database, user_id, query_vector, limit * 3, scores)

    if anchor_memory_id:
        _add_structural_scores(driver, database, anchor_memory_id, limit * 3, scores)
        _add_traversal_scores(driver, database, anchor_memory_id, limit * 3, scores)

    if not scores:
        return []

    # Reciprocal rank fusion
    results = _fuse_scores(scores, semantic_weight, structural_weight, traversal_weight)
    top_ids = [r["memory_id"] for r in results[:limit]]

    # Fetch full memories
    memories = _fetch_memories(driver, database, top_ids)
    mem_map = {m.id: m for m in memories}

    return [
        {
            "memory": mem_map[r["memory_id"]].model_dump() if r["memory_id"] in mem_map else None,
            "combined_score": r["combined_score"],
            "semantic_score": r.get("semantic", 0.0),
            "structural_score": r.get("structural", 0.0),
            "traversal_score": r.get("traversal", 0.0),
        }
        for r in results[:limit]
        if r["memory_id"] in mem_map
    ]


def _add_semantic_scores(
    driver: Any, database: str, user_id: str,
    query_vector: list[float], k: int, scores: dict[str, dict[str, float]],
) -> None:
    """HNSW vector search on Memory.embedding."""
    cypher = (
        "CALL db.index.vector.queryNodes('memory_embedding', $k, $vec) "
        "YIELD node AS m, score WHERE m.user_id = $uid "
        "RETURN m.id AS id, score LIMIT $k"
    )
    with driver.session(database=database) as s:
        try:
            for r in s.run(cypher, vec=query_vector, k=k, uid=user_id):
                scores.setdefault(r["id"], {})["semantic"] = float(r["score"])
        except Exception:
            pass


def _add_structural_scores(
    driver: Any, database: str, anchor_id: str, k: int,
    scores: dict[str, dict[str, float]],
) -> None:
    """Cosine similarity on GDS structural embeddings (structural_embedding property)."""
    cypher = (
        "MATCH (anchor:Memory {id: $aid}) "
        "WHERE anchor.structural_embedding IS NOT NULL "
        "MATCH (m:Memory) WHERE m.id <> $aid AND m.structural_embedding IS NOT NULL "
        "WITH m, vector.similarity.cosine(anchor.structural_embedding, m.structural_embedding) AS sim "
        "WHERE sim > 0 RETURN m.id AS id, sim ORDER BY sim DESC LIMIT $k"
    )
    with driver.session(database=database) as s:
        try:
            for r in s.run(cypher, aid=anchor_id, k=k):
                scores.setdefault(r["id"], {})["structural"] = float(r["sim"])
        except Exception:
            pass


def _add_traversal_scores(
    driver: Any, database: str, anchor_id: str, k: int,
    scores: dict[str, dict[str, float]],
) -> None:
    """Score by graph proximity via FOLLOWED_BY chains (decay by hop distance)."""
    cypher = (
        "MATCH (anchor:Memory {id: $aid}) "
        "MATCH path = (anchor)-[:FOLLOWED_BY*1..5]-(m:Memory) "
        "WHERE m.id <> $aid "
        "WITH m.id AS id, min(length(path)) AS hops "
        "RETURN id, 1.0 / (1.0 + hops) AS proximity ORDER BY proximity DESC LIMIT $k"
    )
    with driver.session(database=database) as s:
        try:
            for r in s.run(cypher, aid=anchor_id, k=k):
                scores.setdefault(r["id"], {})["traversal"] = float(r["proximity"])
        except Exception:
            pass


def _fuse_scores(
    scores: dict[str, dict[str, float]],
    w_sem: float, w_struct: float, w_trav: float,
) -> list[dict[str, Any]]:
    """Reciprocal rank fusion across the three signals."""
    results: list[dict[str, Any]] = []
    for mid, sigs in scores.items():
        combined = (
            sigs.get("semantic", 0.0) * w_sem
            + sigs.get("structural", 0.0) * w_struct
            + sigs.get("traversal", 0.0) * w_trav
        )
        results.append({"memory_id": mid, "combined_score": combined, **sigs})
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results


def _fetch_memories(driver: Any, database: str, ids: list[str]) -> list[Memory]:
    """Fetch full Memory objects by ID list."""
    if not ids:
        return []
    cypher = "UNWIND $ids AS mid MATCH (m:Memory {id: mid}) RETURN m"
    with driver.session(database=database) as s:
        return [to_memory(r["m"]) for r in s.run(cypher, ids=ids)]
