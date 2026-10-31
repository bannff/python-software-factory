"""Restart-safe accepted Lesson projection into existing Memory retrieval."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_service


async def project_accepted(store: Any, limit: int = 100) -> tuple[str, ...]:
    projected = []
    for lesson in store.list_unprojected(limit):
        memory_id = await _find_projection(lesson)
        if memory_id is None:
            memory_id = await _store_projection(lesson)
        if store.mark_projected(lesson, memory_id, lesson.revision) is not None:
            projected.append(lesson.lesson_id)
    return tuple(projected)


async def _find_projection(lesson: Any) -> str | None:
    data = await _call(lesson, "memory_retrieve", {
        "query": lesson.rule, "user_id": "kiro-agent",
        "memory_type": "long_term", "limit": 5,
        "metadata": {
            "lesson_id": lesson.lesson_id,
            "lesson_revision": str(lesson.revision),
            "owner_id": lesson.owner_id,
        },
    }, f"lessons-projection-find:{lesson.lesson_id}:{lesson.revision}")
    memories = data.get("memories")
    if not isinstance(memories, list):
        raise RuntimeError("Lessons Memory retrieval failed")
    for item in memories:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        if isinstance(metadata, dict) and (
            metadata.get("lesson_id") == lesson.lesson_id
            and metadata.get("lesson_revision") == str(lesson.revision)
            and metadata.get("owner_id") == lesson.owner_id
            and isinstance(item.get("id"), str)
        ):
            return item["id"]
    return None


async def _store_projection(lesson: Any) -> str:
    content = f"Rule: {lesson.rule}"
    if lesson.negative:
        content += f"\nDo not: {lesson.negative}"
    tags = ["lessons", "accepted-lessons"]
    if lesson.scope.value == "persona":
        tags.append(f"persona:{lesson.scope_id}")
    data = await _call(lesson, "memory_store", {
        "content": content, "user_id": "kiro-agent",
        "memory_type": "long_term", "category": "preference",
        "metadata": {
            "tags": tags, "kind": "lesson", "status": "accepted",
            "lesson_id": lesson.lesson_id,
            "lesson_revision": str(lesson.revision),
            "owner_id": lesson.owner_id, "scope": lesson.scope.value,
            "scope_id": lesson.scope_id or "",
        },
    }, f"lessons-projection-store:{lesson.lesson_id}:{lesson.revision}")
    memory = data.get("memory")
    memory_id = memory.get("id") if isinstance(memory, dict) else None
    if not data.get("stored") or not isinstance(memory_id, str):
        raise RuntimeError("Lessons Memory projection failed")
    return memory_id


async def _call(lesson: Any, tool: str, arguments: dict[str, Any], key: str) -> dict:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("lessons") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("Lessons Memory MCP unavailable")
    envelope = {"tenant_id": lesson.tenant_id, "principal_id": lesson.owner_id}
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "memory", "tool_name": tool},
        arguments=arguments, idempotency_key=key, envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    if not isinstance(data, dict):
        raise RuntimeError("Lessons Memory MCP failed")
    return data


__all__ = ["project_accepted"]
