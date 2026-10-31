from __future__ import annotations

import pytest

from factory.agent.mcp.session_fork_transcript import register
from factory.mcp_utils.interface import (
    ToolCatalog, get_service, reset_envelope, set_envelope, set_service,
)


class Chat:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def fork_thread(self, agent_id: str, source_thread_id: str, target_thread_id: str) -> bool:
        self.calls.append((agent_id, source_thread_id, target_thread_id))
        return source_thread_id == "thread-source"


async def _tools():
    catalog = ToolCatalog("test")
    register(catalog)
    return {tool.name: tool for tool in await catalog.list_tools()}


_SESSIONS = {
    "session-source": {"session_id": "session-source", "thread_id": "thread-source", "agent_id": "persona-a"},
    "session-target": {"session_id": "session-target", "thread_id": "thread-target", "agent_id": "persona-a"},
    "session-other-persona": {"session_id": "session-other-persona", "thread_id": "thread-other", "agent_id": "persona-b"},
}


def _invoker(_caller: str):
    def invoke(target, **kwargs):
        assert target == {"brick_name": "session", "tool_name": "get"}
        session_id = kwargs["arguments"]["session_id"]
        session = _SESSIONS.get(session_id)
        if session is None:
            structured = {"ok": False, "data": None, "error": "session_not_found"}
        else:
            structured = {"ok": True, "data": {"session": session}, "error": None}
        return {"ok": True, "result": {"structured_content": structured}}
    return invoke


@pytest.mark.asyncio
async def test_fork_transcript_copies_the_source_checkpoint_onto_the_target(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    chat = Chat()
    monkeypatch.setattr(chat_module, "_chat_agent", chat)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_fork_transcript"].fn(
            source_session_id="session-source", target_session_id="session-target",
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True and result.data.copied is True
    assert chat.calls == [("persona-a", "thread-source", "thread-target")]


@pytest.mark.asyncio
async def test_fork_transcript_reports_false_for_an_empty_source(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    monkeypatch.setattr(chat_module, "_chat_agent", Chat())
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_fork_transcript"].fn(
            source_session_id="session-target", target_session_id="session-source",
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True and result.data.copied is False


@pytest.mark.asyncio
async def test_fork_transcript_refuses_a_cross_persona_copy(monkeypatch) -> None:
    """A fork never changes persona (session_fork enforces this on the
    row too) -- refusing here prevents a transcript landing under a
    checkpoint key neither session's real chat adapter would read."""
    from factory.agent.runtime import chat as chat_module
    chat = Chat()
    monkeypatch.setattr(chat_module, "_chat_agent", chat)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_fork_transcript"].fn(
            source_session_id="session-source", target_session_id="session-other-persona",
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is False and result.error == "session_agent_mismatch"
    assert chat.calls == []


@pytest.mark.asyncio
async def test_fork_transcript_denies_missing_authenticated_identity() -> None:
    result = await (await _tools())["session_fork_transcript"].fn(
        source_session_id="session-source", target_session_id="session-target",
    )
    assert result.ok is False and result.error == "session_not_found"


@pytest.mark.asyncio
async def test_fork_transcript_maps_session_transport_failure_to_typed_error() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: lambda *args, **kwargs: {})
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_fork_transcript"].fn(
            source_session_id="session-source", target_session_id="session-target",
        )
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is False and result.error == "history_unavailable"
