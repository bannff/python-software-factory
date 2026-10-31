"""WorkCompletedEmitterPlugin — AfterInvocationEvent hook completing the
chat-turn reward circuit (epic #124 S4a / bd pfvo9 slice 2).

``auto-reward-on-chat-turn.yaml`` subscribes to ``chat.turn.completed``
and scores the turn via the Learning reward-source seam — but the
producer that publishes that event never shipped. This hook is that
producer: one strands chat Agent invocation fires exactly
``chat.turn.completed`` with the four keys the handler ingests
(``run_id``, ``agent_id``, ``input_summary``, ``output_summary``).
Identity (tenant/principal) rides the MCP call envelope, never the
payload (S5 landing-zone discipline).

Deduped on the events brick's idempotency surface (same pattern as
``improvement._already_published``): a replayed invocation probes
``events_query_events`` first, so a duplicate AfterInvocationEvent (or
runtime replay) cannot double-score.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry

from .strands_agent_factory import _CURRENT_INVOCATION

logger = logging.getLogger(__name__)

# Chars, mirroring chat_turn_handler._MAX_FEEDBACK_TEXT (str slicing).
_MAX_SUMMARY_CHARS = 65_536

SKIPPED_STOP_REASONS = frozenset({"cancelled", "interrupt"})

__all__ = ["WorkCompletedEmitterPlugin", "build_payload", "assistant_text"]


def assistant_text(messages: Any) -> str:
    """Join the text blocks of the latest assistant message."""
    if not isinstance(messages, (list, tuple)):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "assistant":
            return "".join(
                block["text"] for block in message.get("content") or ()
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
    return ""


def build_payload(request: Any, event: AfterInvocationEvent) -> dict[str, str]:
    """The handler-consumed turn payload (one key per handler read)."""
    agent = getattr(event, "agent", None)
    return {
        "run_id": request.invocation_id,
        "agent_id": request.agent_id,
        "input_summary": str(request.prompt or "")[:_MAX_SUMMARY_CHARS],
        "output_summary": assistant_text(
            getattr(agent, "messages", None))[:_MAX_SUMMARY_CHARS],
        "idempotency_key": f"chat-turn:{request.invocation_id}",
    }


class WorkCompletedEmitterPlugin(HookProvider):
    """Publish ``chat.turn.completed`` once per strands chat invocation."""

    def __init__(self, invoker: Any = None) -> None:
        self._invoker = invoker
        self._tasks: set[asyncio.Task] = set()
        self._inflight: set[str] = set()

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterInvocationEvent, self._after_invocation)

    def _after_invocation(self, event: AfterInvocationEvent) -> None:
        request = _CURRENT_INVOCATION.get()
        stop_reason = getattr(event.result, "stop_reason", "") if event.result else None
        if request is None or stop_reason is None or stop_reason in SKIPPED_STOP_REASONS:
            # The terminal AfterInvocationEvent also fires from failure
            # paths (finally) where ``result`` is None — a turn that never
            # completed must never be scored.
            logger.debug("work-completed: skip invocation_id=%s", getattr(
                request, "invocation_id", ""))
            return
        payload = build_payload(request, event)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._emit(request, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def settled(self) -> None:
        """Await in-flight emissions (test seam; keeps tasks observed)."""
        while self._tasks:
            tasks = set(self._tasks)
            await asyncio.gather(*tasks)

    def _bound_invoker(self) -> Any:
        if self._invoker is not None:
            return self._invoker
        try:
            from factory.mcp_utils.interface import get_service
            factory = get_service("tool_invoker_for_caller")
            return factory("agent") if callable(factory) else None
        except Exception as exc:
            logger.warning("work-completed: invoker unavailable (%s)", exc)
            return None

    @staticmethod
    def _envelope(request: Any) -> dict[str, str]:
        return {
            key: value for key, value in {
                "tenant_id": request.tenant_id, "principal_id": request.owner_id,
                "session_id": request.thread_id or "",
            }.items() if value
        }

    async def _emit(self, request: Any, payload: dict[str, str]) -> None:
        try:
            invoker = self._bound_invoker()
            if invoker is None:
                return
            key = payload["idempotency_key"]
            if key in self._inflight:
                return
            self._inflight.add(key)
            try:
                if await self._already_published(invoker, key, request):
                    return
                await asyncio.to_thread(
                    invoker, {"brick_name": "events", "tool_name": "events_publish"},
                    arguments={
                        "event_type": "chat.turn.completed", "source": "agent",
                        "payload": payload,
                    },
                    idempotency_key=f"agent-chat-turn:{key}",
                    envelope=self._envelope(request),
                )
            finally:
                self._inflight.discard(key)
        except Exception as exc:
            # Fire-and-forget: never break the chat turn over observability.
            logger.warning("work-completed emit failed: %s", type(exc).__name__)

    @staticmethod
    async def _already_published(invoker: Any, key: str, request: Any) -> bool:
        raw = await asyncio.to_thread(
            invoker, {"brick_name": "events", "tool_name": "events_query_events"},
            arguments={
                "event_type": "chat.turn.completed",
                "payload_key": "idempotency_key", "payload_value": key,
                "limit": 1,
            },
            idempotency_key=f"agent-chat-turn-probe:{key}",
            envelope=WorkCompletedEmitterPlugin._envelope(request),
        )
        structured = raw.get("result", {}).get("structured_content") \
            if isinstance(raw, dict) else None
        data = structured.get("data") \
            if isinstance(structured, dict) and structured.get("ok") else None
        return bool(isinstance(data, dict) and data.get("events"))
