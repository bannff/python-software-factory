from __future__ import annotations

import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.projection import project_accepted
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path) -> LessonLifecycle:
    sql = StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "lessons.db"),
    )
    return LessonLifecycle(SQLLessonStore(sql))


def _response(data):
    return {"ok": True, "result": {"structured_content": {
        "ok": True, "data": data,
    }}}


@pytest.mark.asyncio
async def test_accepted_lesson_projects_once_with_owner_metadata(tmp_path) -> None:
    lifecycle = _runtime(tmp_path)
    lesson = lifecycle.add(
        "tenant", "owner", "Always cite exact evidence",
        negative="Never fabricate sources",
    ).lesson
    calls = []

    def factory(caller):
        def invoke(target, **kwargs):
            calls.append((caller, target, kwargs))
            if target["tool_name"] == "memory_retrieve":
                return _response({"memories": [], "count": 0})
            return _response({"stored": True, "memory": {"id": "memory-1"}})
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        assert await project_accepted(lifecycle.store) == (lesson.lesson_id,)
        assert await project_accepted(lifecycle.store) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
    projected = lifecycle.get("tenant", "owner", lesson.lesson_id)
    assert projected.memory_id == "memory-1"
    assert projected.memory_revision == lesson.revision
    assert [call[1]["tool_name"] for call in calls] == [
        "memory_retrieve", "memory_store",
    ]
    metadata = calls[1][2]["arguments"]["metadata"]
    assert metadata["owner_id"] == "owner"
    assert metadata["lesson_id"] == lesson.lesson_id


@pytest.mark.asyncio
async def test_restart_finds_existing_projection_before_store(tmp_path) -> None:
    lifecycle = _runtime(tmp_path)
    lesson = lifecycle.add("tenant", "owner", "Prefer compact answers").lesson
    calls = []

    def factory(_caller):
        def invoke(target, **kwargs):
            calls.append(target["tool_name"])
            assert target["tool_name"] == "memory_retrieve"
            return _response({"memories": [{
                "id": "existing-memory", "metadata": {
                    "lesson_id": lesson.lesson_id,
                    "lesson_revision": str(lesson.revision),
                    "owner_id": "owner",
                },
            }], "count": 1})
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    restarted = _runtime(tmp_path)
    try:
        assert await project_accepted(restarted.store) == (lesson.lesson_id,)
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert calls == ["memory_retrieve"]
    assert restarted.get("tenant", "owner", lesson.lesson_id).memory_id == "existing-memory"
