"""Backfill evolution for memories that missed A-MEM analysis.

When LLM credentials are expired at store time, memories are saved with
empty keywords/tags/context. This module re-runs evolution on those memories:
content analysis, property updates, and RELATED_TO edge creation.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.memory.runtime.adapters.neo4j_evolution import (
    evolve,
    run_content_analysis,
    set_evolution_properties,
)
from factory.memory.runtime.evolution import EvolutionEngine

logger = logging.getLogger(__name__)


def fetch_unevolved_memories(
    driver: Any, database: str, user_id: str,
    memory_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch memories needing evolution from Neo4j."""
    if memory_ids:
        cypher = (
            "UNWIND $ids AS mid "
            "MATCH (m:Memory {id: mid, user_id: $uid}) "
            "RETURN m.id AS id, m.content AS content"
        )
        with driver.session(database=database) as s:
            return list(s.run(cypher, ids=memory_ids, uid=user_id))
    cypher = (
        "MATCH (m:Memory {user_id: $uid}) "
        "WHERE (m.keywords = [] OR m.keywords IS NULL) "
        "OR m.evolution_status = 'failed' OR m.evolution_status IS NULL "
        "RETURN m.id AS id, m.content AS content LIMIT 200"
    )
    with driver.session(database=database) as s:
        return list(s.run(cypher, uid=user_id))


def evolve_memories(
    driver: Any, database: str, user_id: str,
    llm_complete: Any, embedder: Any, vector_search_fn_factory: Any,
    records: list[Any],
) -> dict[str, Any]:
    """Run evolution on a batch of memory records.

    Args:
        driver: Neo4j driver
        database: Neo4j database name
        user_id: Owner of the memories
        llm_complete: LLM completion callable
        embedder: Embedding model
        vector_search_fn_factory: Callable(content, user_id) -> vector_search_fn
        records: Neo4j records with id and content fields

    Returns:
        Summary dict with evolved_count, failed_count, details
    """
    engine = EvolutionEngine(llm_complete)
    evolved, failed, details = 0, 0, []

    for rec in records:
        mid, content = rec["id"], rec["content"]
        try:
            analysis = run_content_analysis(llm_complete, content)
            set_evolution_properties(driver, database, mid, analysis)
            evolve(
                engine, driver, database, mid, user_id, content, analysis,
                vector_search_fn_factory(content, user_id),
            )
            evolved += 1
            details.append({
                "memory_id": mid, "status": "evolved",
                "keywords": analysis.get("keywords", []),
            })
        except Exception as e:
            logger.warning("Evolution failed for %s: %s", mid, e)
            failed += 1
            details.append({"memory_id": mid, "status": "failed", "error": str(e)})

    return {"evolved_count": evolved, "failed_count": failed, "details": details}
