"""Event emission for sandbox lifecycle activity.

Publishes sandbox activity through the events brick MCP interface.
Gracefully no-ops if the events brick is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import build_event_publish_input

logger = logging.getLogger(__name__)


def _get_invoker():
    """Get the MCP tool invoker from the shared service registry."""
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def emit(event_type: str, payload: dict[str, Any]) -> None:
    """Publish a sandbox event when the events brick is available."""
    invoker = _get_invoker()
    if invoker is None:
        logger.debug("No event invoker available, skipping: %s", event_type)
        return
    try:
        publish_input = build_event_publish_input(payload)
        invoker(
            "events_publish",
            source="sandbox",
            event_type=event_type,
            **publish_input,
        )
    except Exception as exc:
        logger.warning("Failed to emit %s: %s", event_type, exc)