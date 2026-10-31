"""In-memory ChatAgentPort mock for testing.

Split out of ``memory.py`` to keep that file under the 200 LOC ceiling
once the fork_thread mock (row 14, feature-map) pushed it over --
``MemoryChatAgent`` is a genuinely separate concern from the
``MemoryAgentRuntime``/``MemorySwarmRuntime`` mocks that remain there.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from factory.agent.runtime.ports import AgentResult


class MemoryChatAgent:
    """In-memory ChatAgentPort for testing. Returns canned responses.

    ``stream()`` emits a deterministic 3-event sequence
    (``text_delta``, ``text_delta``, ``done``) so unit tests can assert
    ordering invariants without an LLM. Backwards-compat: ``invoke``
    still returns the same canned ``AgentResult``.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[str]] = {}
        self._default = "Mock chat response"

    def set_default_response(self, response: str) -> None:
        self._default = response

    async def invoke(self, thread_id: str, message: str,
                     tools: list[Any] | None = None, agent_id: str | None = None) -> AgentResult:
        self._history.setdefault(thread_id, []).append(message)
        return AgentResult(
            output=f"{self._default} for: {message[:50]}",
            status="completed",
            metadata={"thread_id": thread_id,
                       "turn": len(self._history[thread_id])},
        )

    async def stream(
        self,
        thread_id: str,
        message: str,
        fe_tools: list[Any] | None = None,
        messages: list[dict[str, Any]] | None = None,
        agent_id: str | None = None,
        model_id: str | None = None,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        memory_mode: str | None = None,
    ) -> AsyncIterator[Any]:
        """Deterministic stream for tests: 2 text deltas + done.

        ``fe_tools`` (bd-115z), ``messages`` (bd-n368), ``agent_id``
        (bd-d4roe.3) and ``memory_mode`` (row 3, feature-map) are
        accepted for ChatAgentPort conformance and ignored — the memory
        mock has no LLM to register tools against, no agent.messages
        history to sync, no persona registry, and no durable session
        to materialize a mode onto.
        """
        from factory.agent.runtime.models import (
            DoneEvent, TextDeltaEvent,
        )
        del fe_tools, messages, agent_id, model_id, tenant_id, owner_id, memory_mode
        self._history.setdefault(thread_id, []).append(message)
        message_id = f"mock-{thread_id}-{len(self._history[thread_id])}"
        yield TextDeltaEvent(content="Hello ", message_id=message_id)
        yield TextDeltaEvent(content="world", message_id=message_id)
        yield DoneEvent(reason="stop")

    def close(self, thread_id: str) -> None:
        self._history.pop(thread_id, None)

    async def fork_thread(
        self, agent_id: str, source_thread_id: str, target_thread_id: str,
    ) -> bool:
        """Row 14 (feature-map) mock: copy the in-memory turn list,
        matching the real adapter's "False when the source has no
        checkpoint yet" contract."""
        del agent_id
        source = self._history.get(source_thread_id)
        if not source:
            return False
        self._history[target_thread_id] = list(source)
        return True


__all__ = ["MemoryChatAgent"]
