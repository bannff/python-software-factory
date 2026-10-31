"""Graph-entity <-> ``Memory`` model conversion for ``GraphMemoryStore``.

Extracted from ``graph_store.py`` (LOC ceiling) — a pure conversion helper
with no other state, the same kind of split ``networkx_adapter.py`` already
uses for its own run-scoped query methods.
"""
from __future__ import annotations

from datetime import datetime

from factory.graph.interface import Entity
from factory.memory.core import MemoryCategory
from factory.memory.runtime.models import Memory


def entity_to_memory(entity: Entity) -> Memory:
    props = entity.properties
    meta = {k[5:]: v for k, v in props.items() if k.startswith("meta_")}
    return Memory(
        id=entity.id, user_id=props["user_id"], content=props["content"],
        memory_type=props.get("memory_type", "short_term"),
        category=MemoryCategory(props.get("category", "custom")),
        metadata=meta, relevance_score=float(props.get("relevance_score", 1.0)),
        created_at=datetime.fromisoformat(props["created_at"]),
        updated_at=datetime.fromisoformat(props["updated_at"]) if props.get("updated_at") else None,
        expires_at=datetime.fromisoformat(props["expires_at"]) if props.get("expires_at") else None,
    )


__all__ = ["entity_to_memory"]
