"""Row 43 bulk correction — owner ruling: bulk delete of matched memories
only, no bulk content edit.

Extracted from ``runtime.py`` (LOC ceiling) — the shared match logic
``memory_bulk_preview`` and ``MemoryRuntime.bulk_delete`` both need, so a
shown preview count can never disagree with what a real delete removes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from factory.memory.runtime.models import Memory

if TYPE_CHECKING:
    from factory.memory.runtime.runtime import MemoryRuntime


def bulk_match(
    runtime: "MemoryRuntime", user_id: str, query: str | None,
    memory_type: str | None, metadata: dict[str, str] | None, limit: int,
) -> list[Memory]:
    """The match set for a bulk filter. ``retrieve()``'s underlying
    ``MemoryQuery`` caps its own ``limit`` at 100 (unlike ``list_all()``,
    which has no such cap) — clamped here so a bulk request above that
    with a ``query`` set never raises a validation error the caller never
    asked for. Uses the model's own default ``min_relevance`` (0.3), NOT
    0 — a bulk DELETE must not match every fuzzy-adjacent record just
    because rapidfuzz never returns an exact zero for two non-empty
    strings; a real minimum relevance threshold is a safety property
    here, not an incidental default."""
    matched = (
        runtime.retrieve(user_id, query, memory_type=memory_type, limit=min(limit, 100), metadata=metadata)
        if query else runtime.list_all(user_id, limit, metadata=metadata)
    )
    if memory_type and not query:
        matched = [m for m in matched if m.memory_type == memory_type]
    return matched


__all__ = ["bulk_match"]
