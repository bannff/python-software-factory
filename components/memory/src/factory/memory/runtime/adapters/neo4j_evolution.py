"""Neo4j evolution helpers — A-MEM Zettelkasten + cross-domain linking.

Handles neighbor lookup, evolution analysis, applying results (RELATED_TO
edges, neighbor updates, EVOLVED_FROM trail), and cross-domain edges
(REFERENCES → KBDocument, MENTIONS → Finding) via Cypher.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from factory.memory.runtime.evolution import (
    EvolutionEngine, EvolutionResult, NeighborInfo, analyze_content,
)

logger = logging.getLogger(__name__)
_utcnow = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


def run_content_analysis(llm_complete: Any, content: str) -> dict[str, Any]:
    """Extract keywords, context, tags from content via LLM."""
    return analyze_content(llm_complete, content)


def set_evolution_properties(
    driver: Any, database: str, memory_id: str, analysis: dict[str, Any],
    evolution_status: str = "success",
) -> None:
    """SET keywords, context, tags, and evolution_status on a Memory node."""
    with driver.session(database=database) as s:
        s.run(
            "MATCH (m:Memory {id: $mid}) "
            "SET m.keywords = $keywords, m.context = $context, "
            "m.tags = $tags, m.evolution_status = $status",
            mid=memory_id, keywords=analysis.get("keywords", []),
            context=analysis.get("context", "General"), tags=analysis.get("tags", []),
            status=evolution_status,
        )


def evolve(
    engine: EvolutionEngine, driver: Any, database: str,
    memory_id: str, user_id: str, content: str,
    analysis: dict[str, Any], vector_search_fn: Any,
    memory_embedding: list[float] | None = None,
) -> None:
    """Run full evolution cycle: find neighbors → analyze → apply."""
    try:
        neighbors = _find_neighbors(driver, database, user_id, vector_search_fn)
        if neighbors:
            result = engine.analyze(
                content=content, context=analysis.get("context", ""),
                keywords=analysis.get("keywords", []),
                tags=analysis.get("tags", []), neighbors=neighbors,
            )
            if result.should_evolve:
                _apply_evolution_result(driver, database, result, memory_id)
    except Exception as e:
        logger.warning("Neo4j evolution failed for %s: %s", memory_id, e)
    # Cross-domain linking (independent of intra-memory evolution)
    if memory_embedding is not None:
        try:
            cross = _find_cross_domain_neighbors(
                driver, database, memory_embedding, analysis.get("keywords", []),
            )
            if cross:
                _create_cross_domain_edges(driver, database, memory_id, cross)
        except Exception as e:
            logger.warning("Cross-domain evolution failed for %s: %s", memory_id, e)


def _find_neighbors(
    driver: Any, database: str, user_id: str, vector_search_fn: Any,
) -> list[NeighborInfo]:
    """Use vector search results, then read evolution props from Neo4j."""
    memories = vector_search_fn()
    if not memories:
        return []
    ids = [m.id for m in memories[:5]]
    cypher = (
        "UNWIND $ids AS mid MATCH (m:Memory {id: mid}) "
        "RETURN m.id AS id, m.content AS content, "
        "m.context AS context, m.keywords AS keywords, m.tags AS tags"
    )
    neighbors: list[NeighborInfo] = []
    with driver.session(database=database) as s:
        for r in s.run(cypher, ids=ids):
            neighbors.append(NeighborInfo(
                memory_id=r["id"], content=r["content"] or "",
                context=r["context"] or "", keywords=r["keywords"] or [],
                tags=r["tags"] or [],
            ))
    return neighbors


def _apply_evolution_result(
    driver: Any, database: str, result: EvolutionResult, memory_id: str,
) -> None:
    """Create RELATED_TO edges, update neighbors, create EVOLVED_FROM trail."""
    now = _utcnow()
    with driver.session(database=database) as s:
        for nid in result.connections:
            if nid == memory_id:
                continue
            s.run(
                "MATCH (m:Memory {id: $mid}), (n:Memory {id: $nid}) "
                "CREATE (m)-[:RELATED_TO {created_at: $now, reason: 'evolution'}]->(n)",
                mid=memory_id, nid=nid, now=now,
            )
        for update in result.neighbor_updates:
            nid = update["memory_id"]
            sets: list[str] = ["m.updated_at = $now"]
            params: dict[str, Any] = {"mid": nid, "now": now}
            if "context" in update:
                sets.append("m.context = $context")
                params["context"] = update["context"]
            if "tags" in update:
                sets.append("m.tags = $tags")
                params["tags"] = update["tags"]
            s.run(f"MATCH (m:Memory {{id: $mid}}) SET {', '.join(sets)}", **params)
            s.run(
                "MATCH (m:Memory {id: $mid}), (n:Memory {id: $nid}) "
                "CREATE (n)-[:EVOLVED_FROM {created_at: $now, trigger: $trigger}]->(m)",
                mid=memory_id, nid=nid, now=now, trigger="store",
            )


def _find_cross_domain_neighbors(
    driver: Any, database: str, vec: list[float], keywords: list[str],
) -> list[dict[str, Any]]:
    """Search KBDocument (vector) and Finding (keyword) nodes."""
    results: list[dict[str, Any]] = []
    with driver.session(database=database) as s:
        try:
            for r in s.run(
                "CALL db.index.vector.queryNodes('kb_documents', $k, $vec) "
                "YIELD node, score WHERE score >= $min "
                "RETURN node.id AS id, node.content AS content, "
                "score, 'KBDocument' AS label LIMIT $lim",
                k=5, vec=vec, min=0.6, lim=3,
            ):
                results.append({"node_id": r["id"], "label": r["label"],
                                "score": r["score"], "content": r["content"] or ""})
        except Exception:
            pass  # Index may not exist
        if keywords:
            try:
                for r in s.run(
                    "UNWIND $kws AS kw MATCH (f:Finding) "
                    "WHERE toLower(f.title) CONTAINS toLower(kw) "
                    "OR toLower(f.description) CONTAINS toLower(kw) "
                    "RETURN DISTINCT f.id AS id, f.title AS content, "
                    "0.7 AS score, 'Finding' AS label LIMIT $lim",
                    kws=keywords, lim=2,
                ):
                    results.append({"node_id": r["id"], "label": r["label"],
                                    "score": r["score"], "content": r["content"] or ""})
            except Exception:
                pass  # Finding nodes may not exist
    return results


def _create_cross_domain_edges(
    driver: Any, database: str, memory_id: str,
    neighbors: list[dict[str, Any]],
) -> None:
    """Create REFERENCES (→KBDocument) and MENTIONS (→Finding) edges."""
    now = _utcnow()
    _edge_map = {"KBDocument": ("KBDocument", "REFERENCES"), "Finding": ("Finding", "MENTIONS")}
    with driver.session(database=database) as s:
        for nb in neighbors:
            label, rel = _edge_map.get(nb["label"], (None, None))
            if not label:
                continue
            s.run(
                f"MATCH (m:Memory {{id: $mid}}), (t:{label} {{id: $nid}}) "
                f"CREATE (m)-[:{rel} {{created_at: $now, score: $score, "
                f"reason: 'cross_domain_evolution'}}]->(t)",
                mid=memory_id, nid=nb["node_id"], now=now, score=nb["score"],
            )
