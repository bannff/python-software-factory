"""Cross-brick event emission for memory operations.

Emits events to the events brick via the tool_invoker service registry.
Gracefully degrades if the events brick or tool_invoker is not available.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_memory_event(
    event_type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
) -> None:
    """Emit a memory event to the events brick via MCP tool_invoker.

    Silently skips if tool_invoker is not registered (events brick unavailable).

    Args:
        event_type: Event type (e.g. "memory.store", "memory.evolve.failed")
        payload: Event payload dict
        user_id: Optional user context
    """
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
    except Exception as e:
        logger.warning("Events brick unavailable, skipping emit (%s): %s", event_type, e)
        return
    if invoker is None:
        return

    full_payload = {**payload}
    if user_id:
        full_payload["user_id"] = user_id
    run_id = full_payload.get("run_id")
    try:
        result = invoker(
            "events_publish",
            source="memory",
            event_type=event_type,
            payload=full_payload,
            run_id_authoritative=bool(run_id),
        )
        if isinstance(result, dict) and result.get("error"):
            logger.error(
                "Memory event emission rejected (%s, run_id=%s): %s",
                event_type, run_id, result.get("error"),
            )
    except Exception as e:
        logger.error(
            "events_publish failed for %s (source=memory, run_id=%s): %s",
            event_type, run_id, e, exc_info=True,
        )
