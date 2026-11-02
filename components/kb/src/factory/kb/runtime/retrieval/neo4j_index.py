"""Create or resize a Neo4j vector index.

``CREATE VECTOR INDEX ... IF NOT EXISTS`` never resizes, so a provider change
(different embedding dimensions) would leave an index that rejects every query.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def sync_vector_index(session: Any, name: str, label: str, prop: str, dims: int) -> None:
    """Ensure ``name`` exists with ``dims`` dimensions, rebuilding it if it differs."""
    try:
        have = session.run(
            "SHOW VECTOR INDEXES YIELD name, options WHERE name = $n RETURN options", n=name,
        ).single()
        if have is not None:
            size = have["options"].get("indexConfig", {}).get("vector.dimensions")
            if size == dims:
                return
            logger.warning("vector index %s is %s-d, embedder is %s-d: rebuilding "
                           "(re-ingest to re-embed)", name, size, dims)
            session.run(f"DROP INDEX {name}")
        session.run(
            f"CREATE VECTOR INDEX {name} FOR (n:{label}) ON (n.{prop}) OPTIONS "
            "{indexConfig: {`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}",
            dims=dims,
        )
    except Exception as exc:  # noqa: BLE001 - search falls back to text, never breaks startup
        logger.warning("vector index %s setup failed: %s", name, exc)
