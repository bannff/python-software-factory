from __future__ import annotations

import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.models import LessonScope
from factory.lessons.runtime.recall import recall
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "lessons.db"))
    return LessonLifecycle(SQLLessonStore(sql))


def _response(memories):
    return {"ok": True, "result": {"structured_content": {
        "ok": True, "data": {"memories": memories, "count": len(memories)},
    }}}


@pytest.mark.asyncio
async def test_recall_verifies_authoritative_projection_owner_and_persona(tmp_path) -> None:
    lifecycle = _runtime(tmp_path)
    global_record = lifecycle.add("tenant", "owner", "Always cite evidence").lesson
    global_record = lifecycle.store.mark_projected(
        global_record, "memory-global", global_record.revision,
    )
    persona_record = lifecycle.add(
        "tenant", "owner", "Use developer terminology",
        scope=LessonScope.PERSONA, scope_id="developer",
    ).lesson
    persona_record = lifecycle.store.mark_projected(
        persona_record, "memory-persona", persona_record.revision,
    )
    memories = [
        {"id": "forged", "metadata": {
            "lesson_id": global_record.lesson_id,
            "lesson_revision": str(global_record.memory_revision), "owner_id": "owner",
        }},
        {"id": "memory-global", "metadata": {
            "lesson_id": global_record.lesson_id,
            "lesson_revision": str(global_record.memory_revision), "owner_id": "owner",
        }},
        {"id": "memory-persona", "metadata": {
            "lesson_id": persona_record.lesson_id,
            "lesson_revision": str(persona_record.memory_revision), "owner_id": "owner",
        }},
    ]
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs:
                _response(memories))
    try:
        developer = await recall(
            lifecycle.store, "tenant", "owner", "developer", "evidence",
        )
        other = await recall(
            lifecycle.store, "tenant", "owner", "other", "evidence",
        )
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert [item.lesson_id for item in developer] == [
        global_record.lesson_id, persona_record.lesson_id,
    ]
    assert [item.lesson_id for item in other] == [global_record.lesson_id]
