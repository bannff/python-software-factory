"""Retryable blocker-once projection for Workflow loops."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from factory.mcp_utils.interface import get_service

logger = logging.getLogger(__name__)


async def project_blockers(store: Any, limit: int = 100) -> tuple[str, ...]:
    projected = []
    for loop in store.list_unprojected_blockers(limit):
        if not loop.blocker_digest:
            continue
        try:
            await _publish(loop)
        except Exception as exc:
            logger.warning("Workflow loop blocker projection failed: %s", exc)
            continue
        if store.mark_blocker_projected(loop, loop.revision) is not None:
            projected.append(loop.loop_id)
    return tuple(projected)


async def _publish(loop: Any) -> None:
    envelope = loop.initiation_envelope.model_dump(mode="json")
    await _invoke(
        "events", "events_publish", envelope,
        {
            "event_type": "workflow.loop.blocked", "source": "workflow",
            "payload": {
                "loop_id": loop.loop_id, "blocker_digest": loop.blocker_digest,
                "state": "blocked",
            },
            "tenant_id": loop.tenant_id, "principal_id": loop.owner_id,
            "session_id": loop.origin_thread_id,
        },
        f"workflow-loop-blocked:{loop.loop_id}:{loop.blocker_digest}",
    )
    await _invoke(
        "notification", "send_notification", envelope,
        {
            "recipient": loop.owner_id, "subject": "Workflow loop blocked",
            "content": f"Loop {loop.loop_id} is blocked. Review its cycle evidence.",
            "priority": "high", "envelope": envelope,
        },
        f"workflow-loop-blocked-notify:{loop.loop_id}:{loop.blocker_digest}",
    )


async def _invoke(
    brick: str, tool: str, envelope: dict[str, Any],
    arguments: dict[str, Any], key: str,
) -> None:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("Workflow observability MCP unavailable")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": brick, "tool_name": tool},
        arguments=arguments, idempotency_key=key, envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise RuntimeError(f"Workflow {brick} projection failed")


__all__ = ["project_blockers"]
