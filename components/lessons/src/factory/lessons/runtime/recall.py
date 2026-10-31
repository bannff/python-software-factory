"""Authoritative recall over Memory-ranked accepted projections."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_service

from .models import LessonScope, LessonStatus, RecallLesson


async def recall(
    store: Any, tenant_id: str, owner_id: str, persona_id: str,
    query: str, limit: int = 8,
) -> tuple[RecallLesson, ...]:
    data = await _memory_rank(tenant_id, owner_id, query, limit * 2)
    output = []
    seen = set()
    for item in data:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        lesson_id = metadata.get("lesson_id") if isinstance(metadata, dict) else None
        if not isinstance(lesson_id, str) or lesson_id in seen:
            continue
        record = store.get(tenant_id, owner_id, lesson_id)
        if not _matches(record, item, metadata, persona_id):
            continue
        seen.add(lesson_id)
        output.append(RecallLesson(
            lesson_id=record.lesson_id, rule=record.rule,
            negative=record.negative, scope=record.scope,
            scope_id=record.scope_id,
        ))
        if len(output) >= limit:
            break
    return tuple(output)


def _matches(record: Any, item: dict, metadata: dict, persona_id: str) -> bool:
    if record is None or record.status is not LessonStatus.ACCEPTED:
        return False
    if record.memory_id != item.get("id"):
        return False
    if metadata.get("owner_id") != record.owner_id:
        return False
    if metadata.get("lesson_revision") != str(record.memory_revision):
        return False
    return (record.scope is LessonScope.GLOBAL or
            record.scope is LessonScope.PERSONA and record.scope_id == persona_id)


async def _memory_rank(
    tenant_id: str, owner_id: str, query: str, limit: int,
) -> list[dict[str, Any]]:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("lessons") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("Lessons Memory MCP unavailable")
    envelope = {"tenant_id": tenant_id, "principal_id": owner_id}
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "memory", "tool_name": "memory_retrieve"},
        arguments={
            "query": query, "user_id": "kiro-agent", "memory_type": "long_term",
            "limit": min(max(limit, 1), 32), "tags": ["accepted-lessons"],
            "metadata": {"owner_id": owner_id, "status": "accepted"},
        }, idempotency_key=f"lessons-recall:{owner_id}:{persona_id_key(query)}",
        envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    memories = data.get("memories") if isinstance(data, dict) else None
    if not isinstance(memories, list):
        raise RuntimeError("Lessons Memory recall failed")
    return memories


def persona_id_key(query: str) -> str:
    import hashlib
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


__all__ = ["recall"]
