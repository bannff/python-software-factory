"""The opencode session token must reach the model client and be wired.

Two independent guarantees: (1) ``build_strands_model`` injects the generated
per-thread session header into the injected ``AsyncOpenAI`` default headers;
(2) ``StrandsChatAgent._agent_for`` passes the conversation thread id as
``session_id`` to the model factory. A revert of ``strands_chat.py``'s
``session_id=thread_id`` makes (2) fail.
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_model import build_strands_model
from factory.llm_gateway.runtime.openai_compat_policy import session_token

_HEADER = "x-opencode-session"


def _configure_opencode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_PROFILES", "opencode")
    monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
    monkeypatch.setenv("COMPANION_X_OPENAI_COMPAT_REMOTE_ORIGINS", "https://opencode.ai")
    monkeypatch.setenv("OPENCODE_API_KEY", "session-secret")
    monkeypatch.setenv("OPENCODE_MODEL", "deepseek-v4.1-flash")
    monkeypatch.setenv("OPENCODE_SESSION_HEADER", _HEADER)


def test_session_token_lands_in_injected_async_openai_default_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    class _FakeOpenAIModel:
        def __init__(self, **kwargs: Any) -> None:
            captured["model"] = kwargs

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_FakeAsyncOpenAI))
    monkeypatch.setitem(
        sys.modules, "strands.models.openai", SimpleNamespace(OpenAIModel=_FakeOpenAIModel),
    )
    _configure_opencode(monkeypatch)

    build_strands_model("openai-compat/opencode", session_id="thread-42")

    assert captured["default_headers"] == {_HEADER: session_token("thread-42")}


def test_agent_for_passes_the_thread_id_as_the_model_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("STRANDS_OFFLOAD_BACKEND", "STRANDS_OFFLOAD_DIR"):
        monkeypatch.delenv(var, raising=False)
    from factory.agent.runtime.adapters import strands_agent_factory, strands_chat

    from ._strands_contract_fakes import NullClient, RepliedModel

    async def _no_tools(_client: Any, _persona: Any) -> list[Any]:
        return []

    monkeypatch.setattr(strands_agent_factory, "build_thread_agent_tools", _no_tools)
    seen: list[dict[str, str]] = []

    def fake_model_factory(model_id: str, session_id: str = "") -> Any:
        seen.append({"model_id": model_id, "session_id": session_id})
        return RepliedModel()

    chat = strands_chat.StrandsChatAgent(
        NullClient(), fake_model_factory, model_id="openai-compat/opencode",
    )

    agent = asyncio.run(chat._agent_for("thread-42", "companion-x-default"))

    assert agent is not None
    assert seen == [{"model_id": "openai-compat/opencode", "session_id": "thread-42"}]
