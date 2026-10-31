"""session_stop MCP tool — row 61 slice (cross-brick call to agent.cancel_turn)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from factory.mcp_utils.interface import get_service, set_service
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path: Path) -> SessionRuntime:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "session.db"))
    return SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))


def _tools(tmp_path: Path):
    return create_tool_catalog(_runtime(tmp_path)).tool_map()


def _env(owner: str = "owner-a") -> dict[str, str]:
    return {"tenant_id": "tenant-a", "principal_id": owner}


def _create(tools):
    result = tools["session_create"].fn(
        title="New session", agent_id="companion-x-default", model="openrouter",
        envelope=_env(),
    )
    assert result.ok is True
    return result.data.session


def _invoker_returning(cancelled: bool, calls: list):
    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            calls.append((caller, target, arguments))
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"thread_id": arguments["thread_id"], "cancelled": cancelled},
            }}}
        return invoke
    return factory


def test_session_stop_calls_agent_cancel_turn_with_the_sessions_thread_id(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    calls: list = []
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker_returning(True, calls))
    try:
        result = asyncio.run(tools["session_stop"].fn(
            session_id=created.session_id, expected_revision=created.revision, envelope=_env(),
        ))
    finally:
        set_service("tool_invoker_for_caller", previous)

    assert result.ok is True
    assert result.data.session_id == created.session_id and result.data.cancelled is True
    assert calls == [("session", {"brick_name": "agent", "tool_name": "agent.cancel_turn"},
                       {"thread_id": created.thread_id})]


def test_session_stop_reports_false_when_nothing_was_running(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker_returning(False, []))
    try:
        result = asyncio.run(tools["session_stop"].fn(
            session_id=created.session_id, expected_revision=created.revision, envelope=_env(),
        ))
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True and result.data.cancelled is False


def test_session_stop_rejects_a_stale_revision(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    result = asyncio.run(tools["session_stop"].fn(
        session_id=created.session_id, expected_revision=created.revision + 1, envelope=_env(),
    ))
    assert result.ok is False and result.error == "session_revision_conflict"


def test_session_stop_rejects_an_unknown_session(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    _create(tools)
    result = asyncio.run(tools["session_stop"].fn(
        session_id="s_missing", expected_revision=1, envelope=_env(),
    ))
    assert result.ok is False and result.error == "session_not_found"


def test_session_stop_degrades_gracefully_when_no_invoker_is_registered(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", None)
    try:
        result = asyncio.run(tools["session_stop"].fn(
            session_id=created.session_id, expected_revision=created.revision, envelope=_env(),
        ))
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True and result.data.cancelled is False
