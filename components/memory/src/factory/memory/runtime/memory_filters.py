"""Post-retrieval tag/metadata filters for ``MemoryRuntime``.

Extracted from ``runtime.py`` (LOC ceiling) — pure filter predicates with no
runtime state, applied at the runtime layer (not the ``MemoryStore``
Protocol) so every adapter inherits them for free.
"""
from __future__ import annotations

from factory.memory.runtime.models import Memory


def matches_tags(memory: Memory, required_tags: list[str]) -> bool:
    """ANY-match between ``memory.metadata.tags`` and ``required_tags``.

    Semantics (bd:python-factory-lin6p):

    * ``required_tags=[]`` -> always ``False`` (match nothing).
    * Memory with no ``metadata`` or no ``tags`` key -> ``False`` whenever
      ``required_tags`` is set.
    * Otherwise return ``True`` iff the intersection is non-empty.
    """
    if not required_tags:
        return False
    metadata = memory.metadata if isinstance(memory.metadata, dict) else {}
    tags = metadata.get("tags")
    if not isinstance(tags, (list, tuple, set)):
        return False
    required = set(required_tags)
    return any(isinstance(t, str) and t in required for t in tags)


def matches_metadata(memory: Memory, required: dict[str, str]) -> bool:
    """Per-key AND match between ``memory.metadata`` and ``required``.

    Semantics (bd:python-factory-b2d2o):

    * ``required={}`` -> ``True`` (no constraints; asymmetric vs ``tags=[]``).
    * Memory with no ``metadata`` -> ``False`` whenever ``required`` non-empty.
    * Otherwise return ``True`` iff every ``required`` key=value matches.
    """
    if not required:
        return True
    metadata = memory.metadata if isinstance(memory.metadata, dict) else {}
    for k, v in required.items():
        if metadata.get(k) != v:
            return False
    return True


__all__ = ["matches_metadata", "matches_tags"]
