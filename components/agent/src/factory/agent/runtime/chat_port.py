"""ChatAgentPort — port for persistent chat agents."""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from .ports import AgentResult
from .models import ChatStreamEvent, FrontendToolSpec


@runtime_checkable
class ChatAgentPort(Protocol):
    """Port: Persistent chat agent with conversation memory.

    Two interaction modes:

    - ``invoke()`` — request/response, blocks until the assistant turn
      finishes. Kept for backward compatibility with non-streaming callers
      (``agent_reason``, eval harnesses).
    - ``stream()`` — yields a sequence of strict ``ChatStreamEvent``s as
      the model emits text, requests tools, and finishes. Bridges the
      chat agent to AG-UI without leaking SDK shapes.

    ``stream()`` accepts optional ``fe_tools`` (bd-115z) — the
    canvas-aware chat round-trip pushes FE-side tools (registered via
    CopilotKit ``useFrontendTool``) through the AG-UI request body. The
    Strands adapter registers them as stub ``AgentTool``s for the turn,
    then unregisters them in a ``finally``.

    ``stream()`` also accepts optional ``messages`` (bd-n368) — the
    full ``RunAgentInput.messages`` array CopilotKit re-POSTs on
    resume turns. The adapter inspects trailing ``role:"tool"``
    entries and patches matching ``_frontend_pending`` sentinel
    toolResults on the cached agent so the resume turn sees the FE
    handler's actual reply.
    """

    async def invoke(
        self, thread_id: str, message: str,
        tools: list[Any] | None = None, agent_id: str | None = None,
    ) -> AgentResult:
        """Send a message to a thread, optionally selecting a persona."""
        ...

    def stream(
        self,
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
        """Stream an assistant turn with optional verified identity.

        ``memory_mode`` (row 3, feature-map) carries an EXPLICIT per-chat
        choice only (Persistent/Incognito/Temporary) -- ``None`` means the
        caller made no explicit choice, and the session-binding seam then
        resolves the thread's already-materialized mode (or "persistent"
        on first creation). This port never invents an owner-preference
        default itself; the caller (the AG-UI/CopilotKit HTTP boundary)
        resolves that from Settings before calling stream().
        """
        ...

    async def steer(
        self, thread_id: str, send_id: str, message: str,
        *, agent_id: str | None = None,
        tenant_id: str | None = None, owner_id: str | None = None,
    ) -> Any | None:
        """Persist guidance only when the verified thread is actively running."""
        ...

    async def cancel(self, thread_id: str) -> bool:
        """Cancel the currently running turn(s) for a thread, if any."""
        ...

    def close(self, thread_id: str) -> None:
        """Release resources for a thread."""
        ...

    async def fork_thread(
        self, agent_id: str, source_thread_id: str, target_thread_id: str,
    ) -> bool:
        """Row 14 (feature-map) — copy a thread's checkpoint history onto
        a new thread id, under the same persona. Returns False when the
        source thread has no checkpoint yet (an empty session forks into
        an equally empty one, which is correct, not an error)."""
        ...
