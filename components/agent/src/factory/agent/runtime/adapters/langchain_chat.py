"""ChatAgentPort facade for the LangChain runtime adapter."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from ..models import (
    ChatStreamEvent,
    DoneEvent,
    ErrorEvent,
    FrontendToolSpec,
    InterruptEvent,
    StateDeltaEvent,
    TextDeltaEvent,
    ToolCallDeltaEvent,
    ToolResultEvent,
)
from ..ports import AgentResult
from ..personas import AGENT_ID_ENV, DEFAULT_AGENT_ID
from ..runtime_contracts import RuntimeInvocation
from .langchain_runtime import LangChainAgentRuntime


class LangChainChatAgent:
    """Persistent chat facade preserving persona and thread identity."""

    def __init__(
        self, runtime: LangChainAgentRuntime, model_factory: Any | None = None,
        model_id: str = "", memory_scope: str = "default",
        session_binding: Any | None = None,
    ) -> None:
        self._runtime = runtime
        self._model_factory = model_factory
        self._model_id = model_id
        self._memory_scope = memory_scope
        self._session_binding = session_binding

    def _request(
        self, thread_id: str, message: str, agent_id: str | None,
        *, fe_tools: list[FrontendToolSpec] | None = None,
        messages: list[dict[str, Any]] | None = None,
        model_id: str | None = None,
        tenant_id: str | None = None, owner_id: str | None = None,
        memory_mode: str | None = None,
    ) -> RuntimeInvocation:
        selected = agent_id or os.getenv(AGENT_ID_ENV, DEFAULT_AGENT_ID)
        request = RuntimeInvocation(
            invocation_id=f"chat-{uuid4().hex}",
            agent_id=selected,
            prompt=message,
            capability_scope_digest=self._runtime.capability_scope_digest,
            model_id=model_id or self._model_id,
            memory_scope=self._memory_scope,
            memory_mode=memory_mode or "",
            thread_id=thread_id, tenant_id=tenant_id, owner_id=owner_id,
            messages=tuple(messages or ()),
            frontend_tools=tuple(fe_tools or ()),
        )
        bind = getattr(self._session_binding, "bind", None)
        return bind(request) if callable(bind) else request

    async def invoke(
        self,
        thread_id: str,
        message: str,
        tools: list[Any] | None = None,
        agent_id: str | None = None,
    ) -> AgentResult:
        del tools
        request = self._request(thread_id, message, agent_id)
        try:
            result = await self._runtime.invoke(request)
        except Exception as exc:
            if "ExpiredTokenException" not in str(exc) or self._model_factory is None:
                raise
            from .aws_creds import force_refresh
            force_refresh()
            self._runtime.refresh_model(
                request.model_id, self._model_factory(request.model_id),
            )
            result = await self._runtime.invoke(request)
        return AgentResult(result.output, result.status, dict(result.metadata))

    async def stream(
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
        try:
            for attempt in range(2):
                produced = False
                request = self._request(
                    thread_id, message, agent_id, fe_tools=fe_tools,
                    messages=messages, model_id=model_id, tenant_id=tenant_id,
                    owner_id=owner_id, memory_mode=memory_mode,
                )
                async for event in self._runtime.stream(request):
                    payload = dict(event.payload)
                    if event.kind == "text_delta":
                        produced = produced or bool(str(payload.get("content", "")).strip())
                        yield TextDeltaEvent(**payload)
                    elif event.kind == "tool_call_delta":
                        produced = True
                        yield ToolCallDeltaEvent(**payload)
                    elif event.kind == "tool_result":
                        produced = True
                        yield ToolResultEvent(**payload)
                    elif event.kind == "state_delta":
                        produced = True
                        yield StateDeltaEvent(**payload)
                    elif event.kind == "interrupt":
                        produced = True
                        yield InterruptEvent(**payload)
                    elif event.kind == "done":
                        if produced or attempt == 1:
                            yield DoneEvent(**payload)
                            return
                    else:
                        yield ErrorEvent(message="Chat produced an unsupported event")
                        return
                if produced:
                    return
        except Exception as exc:  # noqa: BLE001 - expose only a stable safe error
            from .provider_errors import log_stream_failure, provider_error_message
            log_stream_failure(exc)
            yield ErrorEvent(message=provider_error_message(exc))

    async def history(self, agent_id: str, thread_id: str) -> list[dict[str, Any]]:
        """Return the durable transcript in AG-UI message shape."""
        return await self._runtime.history(agent_id, thread_id)

    async def fork_thread(
        self, agent_id: str, source_thread_id: str, target_thread_id: str,
    ) -> bool:
        """Row 14 (feature-map) — copy a thread's checkpoint history onto
        a new thread id, under the same persona. Returns False when the
        source thread has no checkpoint yet."""
        return await self._runtime.fork_thread(agent_id, source_thread_id, target_thread_id)

    async def regenerate_turn(
        self, agent_id: str, thread_id: str, message_id: str, new_prompt: str,
    ) -> str | None:
        """Row 16 (feature-map) — see ``langchain_thread_history.regenerate_turn``."""
        from .langchain_thread_history import regenerate_turn
        return await regenerate_turn(
            self._runtime, self._request, agent_id, thread_id, message_id, new_prompt,
        )

    async def rewind_to_message(
        self, agent_id: str, thread_id: str, message_id: str,
    ) -> str | None:
        """Row 15 (feature-map) — see ``langchain_thread_history.rewind_to_message``."""
        from .langchain_thread_history import rewind_to_message
        return await rewind_to_message(self._runtime, agent_id, thread_id, message_id)

    async def steer(
        self, thread_id: str, send_id: str, message: str,
        *, agent_id: str | None = None,
        tenant_id: str | None = None, owner_id: str | None = None,
    ) -> Any | None:
        request = self._request(
            thread_id, message, agent_id,
            tenant_id=tenant_id, owner_id=owner_id,
        )
        return await self._runtime.offer_steer(request, send_id, message)

    async def cancel(self, thread_id: str) -> bool:
        """Cancel the currently running turn(s) for a thread, if any."""
        return await self._runtime.cancel_thread(thread_id)

    def close(self, thread_id: str) -> None:
        """Synchronously delete every persona checkpoint for one thread."""
        self._runtime.close_thread(thread_id)

    async def aclose(self) -> None:
        """Deterministically release the runtime and capability client."""
        await self._runtime.close()


__all__ = ["LangChainChatAgent"]
