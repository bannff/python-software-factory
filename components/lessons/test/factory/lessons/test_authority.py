from __future__ import annotations

import asyncio

import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.models import LessonSource
from factory.lessons.runtime.runtime import LessonsRuntime
from factory.lessons.server import create_mcp_server
from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path) -> LessonsRuntime:
    sql = StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "lessons.db"),
    )
    return LessonsRuntime(LessonLifecycle(SQLLessonStore(sql)))


def _session_factory(_caller):
    def invoke(target, **kwargs):
        assert target == {"brick_name": "session", "tool_name": "resolve_thread"}
        return {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"session": {
                "session_id": "session", "thread_id": "thread", "archived_at": None,
            }},
        }}}
    return invoke


def test_lessons_reads_use_owner_without_thread(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    lesson = runtime.lifecycle.add("tenant", "owner", "Read without chat").lesson
    tools = {
        tool.name: tool for tool in asyncio.run(create_mcp_server(runtime).list_tools())
    }
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        listed = tools["lessons_list"].fn()
        fetched = tools["lessons_get"].fn(lesson_id=lesson.lesson_id)
    finally:
        reset_envelope(token)
    assert [item.lesson_id for item in listed.data.lessons] == [lesson.lesson_id]
    assert fetched.data.lesson.lesson_id == lesson.lesson_id


def test_curation_merges_explicit_session_under_ambient_owner(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    lesson = runtime.lifecycle.add(
        "tenant", "owner", "Candidate", source=LessonSource.FEEDBACK, confidence=0.5,
    ).lesson
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _session_factory)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner", "session_id": None,
    })
    try:
        tool = asyncio.run(create_mcp_server(runtime).get_tool("lessons_accept"))
        result = asyncio.run(tool.fn(
            lesson_id=lesson.lesson_id, expected_revision=lesson.revision,
            envelope={
                "tenant_id": "forged", "principal_id": "forged",
                "session_id": "thread",
            },
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok
    assert result.data.lesson.tenant_id == "tenant"
    assert result.data.lesson.owner_id == "owner"
    assert result.data.lesson.status.value == "accepted"


def test_archived_session_is_restricted_for_lesson_writes() -> None:
    from factory.lessons.mcp.support import verify_session
    from factory.mcp_utils.interface import get_service, set_service

    def factory(_caller):
        return lambda target, **kw: {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"session": {
                "session_id": "s", "thread_id": "t", "archived_at": "2026-11-01T00:00:00Z",
            }},
        }}}

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        with pytest.raises(ValueError, match="lesson_session_restricted"):
            asyncio.run(verify_session("t", {"tenant_id": "tenant", "principal_id": "owner"}))
    finally:
        set_service("tool_invoker_for_caller", previous)


def test_thread_id_wins_over_session_id_when_both_are_sent() -> None:
    from factory.lessons.mcp.support import authority

    context = {"tenant_id": "t", "principal_id": "o",
               "session_id": "s_" + "a" * 32, "thread_id": "t_" + "b" * 32}
    assert authority(context)[2] == "t_" + "b" * 32
    assert authority({**context, "thread_id": None})[2] == "s_" + "a" * 32
