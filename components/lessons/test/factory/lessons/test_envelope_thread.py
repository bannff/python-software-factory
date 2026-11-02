from __future__ import annotations

import asyncio

from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.runtime import LessonsRuntime
from factory.lessons.server import create_mcp_server
from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "lessons.db"))
    return LessonsRuntime(LessonLifecycle(SQLLessonStore(sql)))



def test_explicit_envelope_with_both_ids_resolves_by_thread_and_types_failures(tmp_path) -> None:
    seen: list[str] = []

    def factory(_caller):
        def invoke(target, **kwargs):
            seen.append(kwargs["arguments"]["thread_id"])
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"session": {"archived_at": None}}}}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "t", "principal_id": "o"})
    try:
        tool = asyncio.run(create_mcp_server(_runtime(tmp_path)).get_tool("lessons_add"))
        both = asyncio.run(tool.fn(rule="r", envelope={"session_id": "s_1", "thread_id": "t_1"}))
        none = asyncio.run(tool.fn(rule="r"))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert both.ok and seen == ["t_1"]
    assert none.error == "lesson_owner_context_required"
