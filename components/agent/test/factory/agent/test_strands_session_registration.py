"""Chat turns must land in the Session registry even with no default Crew (#54).

The Welcome-flow thread has no pre-created Session row; the Strands runtime
is responsible for registering it on the first turn, the way the retired
LangChain path did through ``ensure_thread``.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent


class _NullClient:
    scope = type("Scope", (), {"digest": "d"})()


class _Port:
    def __init__(self, fail: bool = False) -> None:
        self.seen: list[Any] = []
        self.fail = fail

    def ensure(self, request: Any) -> str:
        self.seen.append(request)
        if self.fail:
            raise RuntimeError("session registration failed")
        return "s_1"


class _Stop(Exception):
    pass


def _chat(port: _Port) -> StrandsChatAgent:
    chat = StrandsChatAgent(_NullClient(), lambda *a, **k: None, session_port=port)

    async def stop(*_a: Any, **_k: Any) -> Any:
        raise _Stop

    chat._agent_for = stop  # type: ignore[method-assign]
    return chat


def _drain(chat: StrandsChatAgent, **identity: str | None) -> None:
    async def run() -> None:
        async for _ in chat.stream("t-1", "hello", agent_id=None, **identity):
            pass

    with pytest.raises(_Stop):
        asyncio.run(run())


def test_identified_turn_registers_session_before_agent_build() -> None:
    port = _Port()
    _drain(_chat(port), tenant_id="tenant", owner_id="owner")
    assert [(r.thread_id, r.tenant_id, r.owner_id) for r in port.seen] == [
        ("t-1", "tenant", "owner")]


def test_anonymous_turn_skips_registration() -> None:
    port = _Port()
    _drain(_chat(port))
    assert port.seen == []


def test_registration_failure_is_logged_not_fatal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    port = _Port(fail=True)
    _drain(_chat(port), tenant_id="tenant", owner_id="owner")
    assert "session registration failed" in caplog.text


def test_title_comes_from_raw_user_text_not_context_prefix() -> None:
    from factory.agent.runtime.adapters.session_registration import session_title, user_text

    messages = [
        {"role": "user", "content": "older"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "Summarize this document\nplease"},
    ]
    assert user_text(messages) == "Summarize this document\nplease"
    assert user_text([{"role": "user", "content": [{"type": "text"}]}]) is None
    assert user_text(None) is None
    assert session_title("Summarize this document\nplease") == "Summarize this document"
    assert session_title("   ") == "New chat"


def test_multiline_context_never_reaches_the_title() -> None:
    port = _Port()
    prompt = "Canvas context (system-supplied, FE-pushed):\n- a: Intro\n\nContext paragraph\n\nSummarize"
    chat = _chat(port)

    async def run() -> None:
        async for _ in chat.stream(
            "t-1", prompt, agent_id=None, tenant_id="t", owner_id="o",
            messages=[{"role": "user", "content": "Summarize this document"}],
        ):
            pass

    with pytest.raises(_Stop):
        asyncio.run(run())
    assert port.seen[0].prompt == "Summarize this document"
