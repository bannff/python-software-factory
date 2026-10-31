"""Shared filter-clause builder for neo4j memory adapters.

bd:python-factory-26e2a (tags) + python-factory-b2d2o (metadata).
Meta-architect verdict f279063c Q7. Both
``Neo4jMemoryStore.retrieve`` and
``Neo4jEmbeddingMemoryStore._vector_search`` need to conditionally
append the same ``tags`` + ``metadata`` WHERE clauses; centralising
here keeps the Cypher-injection guard (``safe_property_key``) in one
place and lets the two adapters share defense-in-depth.

Property names CANNOT be parameterised in Cypher, so the guard is a
hard requirement — without it, a key like
``"x; MATCH (n) DETACH DELETE n; //"`` would be Cypher injection.
Precedent: ``components/graph/.../runtime/adapters/_neo4j_finding.py
::safe_label``.
"""
from __future__ import annotations

import re
from typing import Any

# Mirror of MemoryQuery._validate_metadata_keys (defense-in-depth).
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def safe_property_key(key: str) -> str:
    """Reject Cypher-unsafe metadata keys at the adapter boundary."""
    if not isinstance(key, str) or not _SAFE_KEY_RE.fullmatch(key):
        raise ValueError(
            f"Unsafe metadata key: {key!r} — must match {_SAFE_KEY_RE.pattern}",
        )
    return key


def build_filter_clauses(query: Any, params: dict[str, Any]) -> str:
    """Build the conditional WHERE-fragment for tags + metadata filters.

    Mutates ``params`` in place. Returns the clause string to append to
    an existing WHERE clause (with leading ``" AND "``). Empty string
    when neither filter is set (or when ``tags=[]`` short-circuits per
    bd:python-factory-26e2a).

    Mapping rules:

    * ``query.tags`` truthy (non-None, non-empty) -> ``ANY(t IN m.tags
      WHERE t IN $tags)`` plus ``params["tags"] = list(query.tags)``.
    * ``query.metadata`` truthy (non-None, non-empty) -> for each key
      ``k`` -> ``m.meta_<k> = $meta_<k>`` plus
      ``params["meta_<k>"] = v``. The writer side stores caller
      metadata at ``props[f"meta_{k}"] = v`` (see
      ``Neo4jMemoryStore.store``), so ``m.meta_<k>`` is the correct
      projection.
    * Both falsy -> ``""``. Runtime post-filter at
      ``MemoryRuntime.retrieve`` covers the ``tags=[]`` and
      ``metadata={}`` short-circuit cases per b2d2o asymmetric default.
    """
    fragments: list[str] = []
    if query.tags:
        fragments.append("ANY(t IN m.tags WHERE t IN $tags)")
        params["tags"] = list(query.tags)
    if query.metadata:
        for k, v in query.metadata.items():
            safe_key = safe_property_key(k)
            param_key = f"meta_{safe_key}"
            fragments.append(f"m.{param_key} = ${param_key}")
            params[param_key] = v
    if not fragments:
        return ""
    return " AND " + " AND ".join(fragments)
