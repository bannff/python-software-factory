from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.runtime import LessonsRuntime
from factory.lessons.server import create_mcp_server
from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
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
                "session_id": "session", "thread_id": "thread", "state": "active",
            }},
        }}}
    return invoke


def test_lessons_catalog_is_exact_strict_and_has_no_authority_ingress(tmp_path) -> None:
    tools = asyncio.run(create_mcp_server(_runtime(tmp_path)).list_tools())
    assert len(tools) == 9
    assert Counter(getattr(tool.fn, "_mcp_category", None) for tool in tools) == {
        "deterministic": 3, "operational": 6,
    }
    assert {tool.name for tool in tools} == {
        "lessons_get", "lessons_list", "lessons_recall", "lessons_add", "lessons_propose",
        "lessons_accept", "lessons_reject", "lessons_remove", "lessons_import_record",
    }
    imp = next(tool for tool in tools if tool.name == "lessons_import_record")
    assert imp.fn._mcp_service_callers == frozenset({"migration"})
    assert imp.fn._mcp_service_binding == "migration_import"
    add = next(tool for tool in tools if tool.name == "lessons_add")
    assert "source" not in add.fn._mcp_input_model.model_fields
    assert "confidence" not in add.fn._mcp_input_model.model_fields
    assert "status" not in add.fn._mcp_input_model.model_fields
    assert "owner_id" not in add.fn._mcp_input_model.model_fields
    assert add.fn._mcp_input_model.model_config["extra"] == "forbid"
    with pytest.raises(SchemaMigrationError):
        asyncio.run(add.fn(rule="valid", source="feedback"))


def test_lessons_add_uses_ambient_owner_and_verifies_session(tmp_path) -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _session_factory)
    token = set_envelope({
        "tenant_id": "ambient-tenant", "principal_id": "ambient-owner",
        "session_id": "thread",
    })
    try:
        tool = asyncio.run(create_mcp_server(_runtime(tmp_path)).get_tool("lessons_add"))
        result = asyncio.run(tool.fn(
            rule="Always preserve evidence",
            envelope={
                "tenant_id": "forged", "principal_id": "forged",
                "session_id": "forged",
            },
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok
    lesson = result.data.result.lesson
    assert lesson.tenant_id == "ambient-tenant"
    assert lesson.owner_id == "ambient-owner"
    assert lesson.source.value == "user_explicit"
    assert lesson.status.value == "accepted"


def test_archived_session_refuses_durable_lesson_write(tmp_path) -> None:
    def archived_factory(_caller):
        return lambda target, **kwargs: {
            "ok": True, "result": {"structured_content": {
                "ok": True, "data": {"session": {
                    "session_id": "session", "thread_id": "thread",
                    "state": "archived",
                }},
            }},
        }

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", archived_factory)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner", "session_id": "thread",
    })
    try:
        tool = asyncio.run(create_mcp_server(_runtime(tmp_path)).get_tool("lessons_add"))
        result = asyncio.run(tool.fn(rule="Do not persist this"))
        assert not result.ok
        assert result.data is None
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)


def test_lesson_events_are_owner_derived_and_content_free(tmp_path) -> None:
    calls = []

    def factory(_caller):
        def invoke(target, **kwargs):
            if target["brick_name"] == "session":
                return _session_factory(None)(target, **kwargs)
            calls.append((target, kwargs))
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"event_id": "evt-1"},
            }}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner", "session_id": "thread",
    })
    try:
        tool = asyncio.run(create_mcp_server(_runtime(tmp_path)).get_tool("lessons_add"))
        result = asyncio.run(tool.fn(rule="Keep event content private"))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok and len(calls) == 2
    target, call = calls[0]
    assert target == {"brick_name": "events", "tool_name": "events_publish"}
    payload = call["arguments"]["payload"]
    assert payload["lesson_id"] == result.data.result.lesson.lesson_id
    assert "rule" not in payload and "negative" not in payload
    assert call["envelope"]["principal_id"] == "owner"
    projection_target, projection = calls[1]
    assert projection_target == {
        "brick_name": "events", "tool_name": "events_publish_projection",
    }
    record = projection["arguments"]["record"]
    assert record["subject_local_id"] == result.data.result.lesson.lesson_id
    assert "rule" not in record and "negative" not in record
    assert projection["projection"]["owner_id"] == "owner"


def test_archived_session_refuses_lesson_curation(tmp_path) -> None:
    from factory.lessons.runtime.models import LessonSource

    runtime = _runtime(tmp_path)
    proposed = runtime.lifecycle.add(
        "tenant", "owner", "Candidate",
        source=LessonSource.FEEDBACK, confidence=0.5,
    ).lesson

    def archived_factory(_caller):
        return lambda target, **kwargs: {
            "ok": True, "result": {"structured_content": {
                "ok": True, "data": {"session": {
                    "session_id": "session", "thread_id": "thread",
                    "state": "archived",
                }},
            }},
        }

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", archived_factory)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner", "session_id": "thread",
    })
    try:
        tool = asyncio.run(create_mcp_server(runtime).get_tool("lessons_accept"))
        result = asyncio.run(tool.fn(
            lesson_id=proposed.lesson_id, expected_revision=proposed.revision,
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert not result.ok and result.data is None
    assert runtime.lifecycle.get(
        "tenant", "owner", proposed.lesson_id,
    ).status.value == "proposed"
