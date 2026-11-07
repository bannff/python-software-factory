"""A no-op replay must not republish the lifecycle event (issue #345).

The event idempotency key is lesson/revision scoped, so republishing with a
different outcome payload for the same key is an idempotency conflict.
"""
from __future__ import annotations

import pytest

from factory.lessons.mcp.events import emit_lesson_event
from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.mcp_utils.interface import get_service, set_service
from factory.storage.interface import StorageRuntime


def _lifecycle(tmp_path) -> LessonLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "l.db"))
    return LessonLifecycle(SQLLessonStore(sql))


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,published", [
    ("inserted", 1), ("enriched", 1), ("unchanged", 0), ("deduped", 0),
])
async def test_replays_publish_nothing(tmp_path, outcome, published) -> None:
    lesson = _lifecycle(tmp_path).add("t", "o", "Always cite evidence").lesson
    calls: list[dict] = []

    def factory(caller):
        def invoke(target, **kwargs):
            calls.append(target)
            return {"ok": True, "result": {"structured_content": {"ok": True, "data": {}}}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        await emit_lesson_event(lesson, "lesson.accepted", outcome=outcome)
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert len([c for c in calls if c["tool_name"] == "events_publish"]) == published
