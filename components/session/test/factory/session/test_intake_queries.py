"""Intake queries required by cooperative Agent steering."""
from __future__ import annotations

from pathlib import Path

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _tools(tmp_path: Path):
    sql = StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "sessions.db"),
    )
    runtime = SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))
    return create_tool_catalog(runtime).tool_map()


def _env(owner: str = "owner-a") -> dict[str, str]:
    return {"tenant_id": "tenant-a", "principal_id": owner}


def _create(tools, title: str = "Session"):
    result = tools["session_create"].fn(
        title=title, agent_id="companion-x-default", model="openrouter",
        envelope=_env(),
    )
    assert result.ok
    return result.data.session


def test_resolve_thread_is_owner_scoped_and_typed(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    tool = tools["session_resolve_thread"].fn
    assert getattr(tool, "_mcp_category") == "deterministic"
    resolved = tool(thread_id=session.thread_id, envelope=_env())
    assert resolved.ok and resolved.data.session.session_id == session.session_id
    foreign = tool(thread_id=session.thread_id, envelope=_env("owner-b"))
    assert foreign.ok is False and foreign.error == "session_not_found"
    missing = tool(thread_id="t_missing", envelope=_env())
    assert missing.ok is False and missing.error == "session_not_found"


def test_written_steers_are_active_owner_scoped_and_ordered(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    first = tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_1",
        content="first", envelope=_env(),
    ).data.steer
    second = tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_2",
        content="second", envelope=_env(),
    ).data.steer
    runtime = tools["session_list_written_steers"].fn
    assert getattr(runtime, "_mcp_category") == "deterministic"
    values = runtime(session_id=session.session_id, envelope=_env())
    assert [item.delivery_id for item in values.data.steers] == [
        first.delivery_id, second.delivery_id,
    ]

    lifecycle = tools["session_get_steer"].fn
    assert lifecycle(
        session_id=session.session_id, delivery_id=first.delivery_id,
        envelope=_env(),
    ).data.steer.state.value == "written"
    foreign = runtime(session_id=session.session_id, envelope=_env("owner-b"))
    assert foreign.ok is False and foreign.error == "session_not_found"


def test_archived_session_exposes_no_written_intake(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_1",
        content="later", envelope=_env(),
    )
    tools["session_archive"].fn(
        session_id=session.session_id, expected_revision=session.revision,
        envelope=_env(),
    )
    result = tools["session_list_written_steers"].fn(
        session_id=session.session_id, envelope=_env(),
    )
    assert result.ok is False and result.error == "session_not_found"
