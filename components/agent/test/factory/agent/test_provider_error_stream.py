"""Regression: provider status errors surface as specific RUN_ERROR text.

Live repro (2026-09-30, OpenRouter 402): the stream handler's blanket
``except Exception`` yielded the generic "Chat is temporarily unavailable"
with no status-code inspection and no server-side log of the cause.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.provider_errors import provider_error_message
from factory.agent.runtime.models import ErrorEvent


class _ExplodingRuntime:
    capability_scope_digest = "digest"

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def stream(self, request):
        del request
        raise self._exc
        yield  # pragma: no cover — makes this an async generator


def _chat(exc: Exception) -> LangChainChatAgent:
    return LangChainChatAgent(_ExplodingRuntime(exc))


class _StatusError(Exception):
    """Standalone stand-in for openai.APIStatusError with .status_code."""

    def __init__(self, status_code: int, message: str = "provider error") -> None:
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.asyncio
@pytest.mark.parametrize("status,needle", [
    (402, "credits exhausted"),
    (401, "authentication failed"),
    (403, "authentication failed"),
    (429, "rate limit"),
])
async def test_provider_status_errors_surface_specific_message(
    status: int, needle: str,
) -> None:
    chat = _chat(_StatusError(status))
    events = [event async for event in chat.stream("thread", "hi")]
    assert len(events) == 1 and isinstance(events[0], ErrorEvent)
    assert needle in events[0].message
    # Never the generic message when the cause is known.
    assert "temporarily unavailable" not in events[0].message


@pytest.mark.asyncio
async def test_unknown_error_keeps_generic_message() -> None:
    chat = _chat(RuntimeError("connection reset"))
    events = [event async for event in chat.stream("thread", "hi")]
    assert len(events) == 1 and isinstance(events[0], ErrorEvent)
    assert events[0].message == "Chat is temporarily unavailable. Please retry."


@pytest.mark.asyncio
@pytest.mark.parametrize("status,needle", [
    (402, "credits exhausted"),
    (401, "authentication failed"),
    (429, "rate limit"),
])
async def test_real_openai_api_status_error_maps(status: int, needle: str) -> None:
    openai = pytest.importorskip("openai")
    import httpx2

    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx2.Response(status_code=status, request=request)
    exc = openai.APIStatusError("provider said no", response=response, body=None)
    assert exc.status_code == status
    assert needle in provider_error_message(exc)
