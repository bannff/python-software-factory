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


def test_title_skips_fe_pushed_context_prefix() -> None:
    from factory.agent.runtime.adapters.session_registration import session_title

    prompt = "Canvas context (system-supplied, FE-pushed):\n- a: b\n\nwhat is up?\nmore"
    assert session_title(prompt) == "what is up?"
    assert session_title("  plain first line\nx") == "plain first line"
    assert session_title("   ") == "New chat"
