"""Row 16 (feature-map) — session regenerate: re-run a turn onto a new
sibling checkpoint branch, then persist it as the thread's current one.
Mirrors ``test_session_rewind_mcp.py``'s exact fake-invoker convention."""
from __future__ import annotations

import pytest

from factory.agent.mcp.session_regenerate import register
from factory.mcp_utils.interface import (
    ToolCatalog, get_service, reset_envelope, set_envelope, set_service,
)


class Chat:
    def __init__(self, checkpoint_id: str | None) -> None:
        self._checkpoint_id = checkpoint_id
        self.calls: list[tuple[str, str, str, str]] = []

    async def regenerate_turn(
        self, agent_id: str, thread_id: str, message_id: str, new_prompt: str,
    ) -> str | None:
        self.calls.append((agent_id, thread_id, message_id, new_prompt))
        return self._checkpoint_id


async def _tools():
    catalog = ToolCatalog("test")
    register(catalog)
    return {tool.name: tool for tool in await catalog.list_tools()}


_SESSIONS = {
    "session-a": {"session_id": "session-a", "thread_id": "thread-a", "agent_id": "persona-a"},
}


def _invoker(persist_ok: bool = True):
    calls: list[dict] = []

    def factory(_caller: str):
        def invoke(target, **kwargs):
            calls.append({"target": target, "kwargs": kwargs})
            if target == {"brick_name": "session", "tool_name": "get"}:
                session_id = kwargs["arguments"]["session_id"]
                session = _SESSIONS.get(session_id)
                structured = (
                    {"ok": True, "data": {"session": session}, "error": None} if session is not None
                    else {"ok": False, "data": None, "error": "session_not_found"}
                )
                return {"ok": True, "result": {"structured_content": structured}}
            if target == {"brick_name": "session", "tool_name": "set_active_checkpoint"}:
                structured = {"ok": persist_ok, "data": None, "error": None if persist_ok else "session_revision_conflict"}
                return {"ok": True, "result": {"structured_content": structured}}
            raise AssertionError(f"unexpected target {target}")
        return invoke
    return factory, calls


@pytest.mark.asyncio
async def test_regenerate_persists_the_new_branch_as_active(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    chat = Chat("checkpoint-456")
    monkeypatch.setattr(chat_module, "_chat_agent", chat)
    factory, calls = _invoker()
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_regenerate"].fn(
            session_id="session-a", message_id="msg-1", new_prompt="try again",
            expected_revision=1,
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True
    assert result.data.regenerated is True and result.data.checkpoint_id == "checkpoint-456"
    assert chat.calls == [("persona-a", "thread-a", "msg-1", "try again")]
    persist_call = next(c for c in calls if c["target"]["tool_name"] == "set_active_checkpoint")
    assert persist_call["kwargs"]["arguments"]["checkpoint_id"] == "checkpoint-456"


@pytest.mark.asyncio
async def test_regenerate_reports_false_for_an_unknown_message(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    chat = Chat(None)
    monkeypatch.setattr(chat_module, "_chat_agent", chat)
    factory, _ = _invoker()
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_regenerate"].fn(
            session_id="session-a", message_id="msg-unknown", new_prompt="try again",
            expected_revision=1,
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True and result.data.regenerated is False and result.data.checkpoint_id is None


@pytest.mark.asyncio
async def test_regenerate_reports_a_stale_revision_conflict(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    monkeypatch.setattr(chat_module, "_chat_agent", Chat("checkpoint-456"))
    factory, _ = _invoker(persist_ok=False)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_regenerate"].fn(
            session_id="session-a", message_id="msg-1", new_prompt="try again",
            expected_revision=1,
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is False and result.error == "session_revision_conflict"


@pytest.mark.asyncio
async def test_regenerate_denies_missing_authenticated_identity() -> None:
    result = await (await _tools())["session_regenerate"].fn(
        session_id="session-a", message_id="msg-1", new_prompt="try again",
        expected_revision=1,
    )
    assert result.ok is False and result.error == "session_not_found"


@pytest.mark.asyncio
async def test_regenerate_maps_session_transport_failure_to_typed_error() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: lambda *args, **kwargs: {})
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_regenerate"].fn(
            session_id="session-a", message_id="msg-1", new_prompt="try again",
            expected_revision=1,
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is False and result.error == "history_unavailable"
