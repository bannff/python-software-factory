"""Cross-brick event emission for ML operations.

Emits events to the events brick via the tool_invoker service registry.
Gracefully degrades if the events brick or tool_invoker is not available.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_ml_event(event_type: str, payload: dict[str, Any]) -> None:
    """Emit an ML event via tool_invoker. Fire-and-forget."""
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is None:
            return
        invoker("events_publish", source="machine_learning",
                event_type=event_type, payload=payload)
    except Exception as e:
        logger.debug("ML event emission skipped (%s): %s", event_type, e)
