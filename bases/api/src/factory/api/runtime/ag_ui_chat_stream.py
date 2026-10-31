"""Merged chat-agent + event_bus stream for the AG-UI SSE route.

The browser ``runId`` is a chat correlation ID. Nested durable workflows
retain their own ``run_id``, so event-bus traffic is admitted only when its
``correlation_id`` matches the active chat request.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


def _event_correlation_id(evt: dict[str, Any]) -> str | None:
    """Extract trusted chat correlation from a raw event or its payload."""
    if not isinstance(evt, dict):
        return None
    correlation_id = evt.get("correlation_id") or evt.get("request_id")
    if correlation_id:
        return str(correlation_id)
    payload = evt.get("payload")
    if isinstance(payload, dict):
        correlation_id = payload.get("correlation_id") or payload.get("request_id")
        if correlation_id:
            return str(correlation_id)
    return None


async def merged_chat_stream(
    thread_id: str,
    user_message: str,
    run_id: str,
    fe_tools: list[Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    identity: dict[str, str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield chat events plus workflow events correlated to this AG-UI run."""
    from factory.agent.interface import get_chat_agent_stream
    from factory.mcp_utils.interface import event_bus

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def _drain_chat() -> None:
        try:
            identity_args = {} if identity is None else {
                "tenant_id": identity["tenant_id"],
                "owner_id": identity["principal_id"],
            }
            model_args = {} if model_id is None else {"model_id": model_id}
            async for ev in get_chat_agent_stream(
                thread_id, user_message,
                fe_tools=fe_tools, messages=messages,
                agent_id=agent_id, **model_args, **identity_args,
            ):
                queue.put_nowait({"kind": "chat", "event": ev})
        except Exception as exc:  # noqa: BLE001 — surface to UI
            logger.error("chat stream drain error: %s", exc)
            queue.put_nowait({"kind": "chat_error", "message": str(exc)})
        finally:
            # Flush call_soon_threadsafe publish -> bus subscriber -> merged queue.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            queue.put_nowait({"kind": "chat_done"})

    async def _drain_bus() -> None:
        try:
            async for raw in event_bus.subscribe():
                if not isinstance(raw, dict):
                    continue
                if _event_correlation_id(raw) != run_id:
                    continue
                queue.put_nowait({"kind": "workflow", "event": raw})
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — defence in depth
            logger.debug("event_bus drain error", exc_info=True)

    bus_task = asyncio.create_task(_drain_bus(),
                                    name=f"ag-ui-bus-{thread_id}")
    await asyncio.sleep(0)
    chat_task = asyncio.create_task(_drain_chat(),
                                     name=f"ag-ui-chat-{thread_id}")
    try:
        chat_done = False
        while not chat_done:
            evt = await queue.get()
            if evt is None:
                continue
            kind = evt.get("kind")
            if kind == "chat_done":
                chat_done = True
                continue
            if kind == "chat_error":
                from factory.agent.runtime.models import ErrorEvent
                yield {"kind": "chat",
                       "event": ErrorEvent(message=evt["message"])}
                chat_done = True
                continue
            yield evt
    finally:
        for t in (chat_task, bus_task):
            if not t.done():
                t.cancel()
        for t in (chat_task, bus_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


__all__ = ["merged_chat_stream"]
