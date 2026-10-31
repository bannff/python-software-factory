"""Singleton LangChain chat-agent accessor."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from factory.agent.runtime.ports import ChatAgentPort
from factory.agent.runtime.models import ChatStreamEvent, FrontendToolSpec
logger = logging.getLogger(__name__)

_chat_agent: Any | None = None


def get_chat_agent() -> ChatAgentPort:
    """Return the singleton chat agent, creating it on first call."""
    global _chat_agent
    if _chat_agent is not None:
        return _chat_agent

    from factory.agent.runtime.adapters import create_chat_agent

    logger.info("Creating chat agent from trusted runtime selection")
    _chat_agent = create_chat_agent()
    return _chat_agent


def get_chat_agent_stream(
    thread_id: str,
    message: str,
    fe_tools: list[FrontendToolSpec] | None = None,
    messages: list[dict[str, Any]] | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    tenant_id: str | None = None,
    owner_id: str | None = None,
    memory_mode: str | None = None,
) -> AsyncIterator[ChatStreamEvent]:
    """Stable wrapper over ``get_chat_agent().stream(...)``.

    The api base imports this from ``factory.agent.interface`` to drive
    the AG-UI SSE endpoint. Keeping the wrapper here lets the singleton
    accessor stay the only place that decides which adapter to build.

    ``fe_tools`` and ``messages`` carry CopilotKit resume context. The
    LangChain adapter currently consumes the normalized user turn while
    preserving ``agent_id`` as the per-thread persona selector. ``None``
    uses the configured default persona.

    ``memory_mode`` (row 3, feature-map) is the caller's resolved choice
    for this turn -- ``None`` when the user made no explicit per-chat
    pick. The api base is expected to resolve the owner's saved
    ``default_memory_mode`` preference (Settings -> Chat) and pass it
    here ONLY on a thread's first turn; every later turn on an
    already-materialized thread may omit it, since the session-binding
    seam re-reads the durable session's own mode regardless of what
    (if anything) is passed on a warm turn.
    """
    return get_chat_agent().stream(
        thread_id, message, fe_tools=fe_tools, messages=messages,
        agent_id=agent_id, model_id=model_id,
        tenant_id=tenant_id, owner_id=owner_id, memory_mode=memory_mode,
    )


def reset_chat_agent() -> None:
    """Reset the singleton (for testing)."""
    global _chat_agent
    _chat_agent = None


async def cancel_chat_turn(thread_id: str) -> bool:
    """Cancel the currently running turn(s) for a thread, if any are live."""
    return await get_chat_agent().cancel(thread_id)


async def close_chat_agent() -> None:
    """Close and release the singleton chat runtime at process shutdown."""
    global _chat_agent
    agent, _chat_agent = _chat_agent, None
    close = getattr(agent, "aclose", None)
    if close is not None:
        await close()
