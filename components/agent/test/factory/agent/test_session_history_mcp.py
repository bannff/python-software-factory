from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.agent.mcp.session_history import register
from factory.mcp_utils.interface import (
    ToolCatalog, get_service, reset_envelope, set_envelope, set_service,
)


class Chat:
    async def history(self, agent_id: str, thread_id: str):
        assert (agent_id, thread_id) == ("persona-a", "thread-a")
        return [{
            "id": "m1", "role": "user", "content": "hello",
            "tool_calls": [], "tool_call_id": None,
        }]


async def _tools():
    catalog = ToolCatalog("test")
    register(catalog)
    return {tool.name: tool for tool in await catalog.list_tools()}


def _invoker(_caller: str):
    def invoke(target, **kwargs):
        assert target == {"brick_name": "session", "tool_name": "get"}
        assert kwargs["arguments"]["session_id"] == "session-a"
        session = {
            "session_id": "session-a", "thread_id": "thread-a",
            "agent_id": "persona-a",
        }
        structured = {"ok": True, "data": {"session": session}, "error": None}
        return {"ok": True, "result": {"structured_content": structured}}
    return invoke


@pytest.mark.asyncio
async def test_history_authorizes_session_before_reading_agent_checkpoint(monkeypatch) -> None:
    from factory.agent.runtime import chat as chat_module
    monkeypatch.setattr(chat_module, "_chat_agent", Chat())
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_history"].fn(session_id="session-a")
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is True
    assert result.data.thread_id == "thread-a"
    assert result.data.messages[0].content == "hello"


@pytest.mark.asyncio
async def test_history_denies_missing_authenticated_identity() -> None:
    result = await (await _tools())["session_history"].fn(session_id="session-a")
    assert result.ok is False and result.error == "session_not_found"


@pytest.mark.asyncio
async def test_history_maps_session_transport_failure_to_typed_error() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: lambda *args, **kwargs: {})
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        result = await (await _tools())["session_history"].fn(session_id="session-a")
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert result.ok is False and result.error == "history_unavailable"
