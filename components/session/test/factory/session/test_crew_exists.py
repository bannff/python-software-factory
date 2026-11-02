"""A Session may only bind a Crew that exists for its owner."""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime

ENV = {"tenant_id": "tenant-a", "principal_id": "owner-a"}


def _tools(tmp_path: Path):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "s.db"))
    return create_tool_catalog(SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))).tool_map()


def _invoker(existing: set[str]):
    def factory(_caller):
        def invoke(target, **kwargs):
            assert target == {"brick_name": "agent", "tool_name": "agent_get_crew"}
            assert kwargs["envelope"]["principal_id"] == "owner-a"
            found = kwargs["arguments"]["crew_id"] in existing
            return {"ok": True, "result": {"structured_content": (
                {"ok": True, "data": {}} if found else {"ok": False, "error": "crew_not_found"})}}
        return invoke
    return factory


@pytest.fixture
def agent_brick():
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker({"real-crew"}))
    yield
    set_service("tool_invoker_for_caller", previous)


def _create(tools, crew_id: str):
    return tools["session_create"].fn(
        title="t", agent_id="companion-x-default", model="anthropic.claude-sonnet",
        crew_id=crew_id, memory_scope="scope" if crew_id else "", envelope=ENV,
    )


def test_ghost_crew_is_a_typed_not_found(tmp_path, agent_brick) -> None:
    result = _create(_tools(tmp_path), "ghost-crew")
    assert result.ok is False and result.error == "crew_not_found"


def test_existing_crew_and_no_crew_are_accepted(tmp_path, agent_brick) -> None:
    tools = _tools(tmp_path)
    assert _create(tools, "real-crew").ok is True
    assert _create(tools, "").ok is True


def test_ensure_thread_also_rejects_a_ghost_crew(tmp_path, agent_brick) -> None:
    result = _tools(tmp_path)["session_ensure_thread"].fn(
        thread_id="th-1", title="t", agent_id="companion-x-default",
        model="anthropic.claude-sonnet", crew_id="ghost-crew", memory_scope="scope",
        envelope=ENV,
    )
    assert result.ok is False and result.error == "crew_not_found"


def test_without_an_agent_brick_the_reference_stays_opaque(tmp_path) -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", None)
    try:
        assert _create(_tools(tmp_path), "anything").ok is True
    finally:
        set_service("tool_invoker_for_caller", previous)
