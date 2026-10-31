"""Helper utilities for the A-MEM adapter.

Handles ChromaDB metadata flattening/unflattening, LRU cache,
and Memory model conversion. Split from amem.py to stay under 200 LOC.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -- ChromaDB metadata serialization --
# ChromaDB only allows flat str/int/float/bool values in metadata.

_LIST_KEYS = {"keywords", "tags", "links", "evolution_history"}
_DICT_KEYS = {"extra"}


def flatten_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Flatten complex types for ChromaDB (only str/int/float/bool allowed)."""
    flat: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            flat[k] = v
        elif isinstance(v, (list, dict)):
            flat[k] = json.dumps(v)
        elif v is not None:
            flat[k] = str(v)
    return flat


def unflatten_meta(flat: dict[str, Any]) -> dict[str, Any]:
    """Restore complex types from ChromaDB flat metadata."""
    meta: dict[str, Any] = {}
    for k, v in flat.items():
        if k in _LIST_KEYS and isinstance(v, str):
            try:
                meta[k] = json.loads(v)
            except (ValueError, TypeError):
                meta[k] = []
        elif k in _DICT_KEYS and isinstance(v, str):
            try:
                meta[k] = json.loads(v)
            except (ValueError, TypeError):
                meta[k] = {}
        else:
            meta[k] = v
    return meta


def meta_to_memory(meta: dict[str, Any], score: float = 1.0) -> Memory:
    """Convert internal metadata dict to a Memory model."""
    created = meta.get("created_at")
    created_dt = datetime.fromisoformat(created) if created else utcnow()
    expires = meta.get("expires_at")
    expires_dt = datetime.fromisoformat(expires) if expires else None
    return Memory(
        id=meta.get("id", ""),
        user_id=meta.get("user_id", ""),
        content=meta.get("content", ""),
        memory_type=meta.get("memory_type", "short_term"),
        category=MemoryCategory(meta.get("category", "custom")),
        metadata=meta.get("extra", {}),
        relevance_score=min(score, 1.0),
        created_at=created_dt,
        expires_at=expires_dt,
    )


class LRUCache:
    """Simple LRU cache for memory metadata."""

    def __init__(self, max_size: int = 1000) -> None:
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> dict[str, Any] | None:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self._max_size:
            self._data.popitem(last=False)
        self._data[key] = value

    def pop(self, key: str) -> dict[str, Any] | None:
        return self._data.pop(key, None)
