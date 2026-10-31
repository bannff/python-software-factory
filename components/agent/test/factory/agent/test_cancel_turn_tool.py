"""agent.cancel_turn MCP tool — row 61 slice."""
from __future__ import annotations

import asyncio

from factory.agent.mcp.cancel_tool import register
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def _catalog(monkeypatch, cancel_return: bool) -> ToolCatalog:
    catalog = ToolCatalog("agent-test")

    async def fake_cancel(thread_id: str) -> bool:
        fake_cancel.calls.append(thread_id)  # type: ignore[attr-defined]
        return cancel_return
    fake_cancel.calls = []  # type: ignore[attr-defined]

    import factory.agent.runtime.chat as chat_module
    monkeypatch.setattr(chat_module, "cancel_chat_turn", fake_cancel)
    register(catalog, agent=object())
    return catalog, fake_cancel


def test_cancel_turn_reports_true_when_a_turn_was_live(monkeypatch) -> None:
    catalog, fake_cancel = _catalog(monkeypatch, cancel_return=True)
    tools = {t.name: t for t in asyncio.run(catalog.list_tools())}
    result = asyncio.run(tools["agent.cancel_turn"].fn(thread_id="thread-1"))
    assert result.ok is True
    assert result.data.thread_id == "thread-1" and result.data.cancelled is True
    assert fake_cancel.calls == ["thread-1"]


def test_cancel_turn_reports_false_when_nothing_was_running(monkeypatch) -> None:
    catalog, _ = _catalog(monkeypatch, cancel_return=False)
    tools = {t.name: t for t in asyncio.run(catalog.list_tools())}
    result = asyncio.run(tools["agent.cancel_turn"].fn(thread_id="thread-idle"))
    assert result.ok is True and result.data.cancelled is False
