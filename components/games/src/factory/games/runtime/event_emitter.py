"""Event emission for game lifecycle.

Publishes events via the events brick MCP interface.
Gracefully no-ops if the events brick is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import build_event_publish_input

logger = logging.getLogger(__name__)


def _get_invoker():
    """Get the MCP tool invoker (service registry or aggregator).

    Returns None quickly if no invoker is available — never blocks.
    """
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    # Skip aggregator path in standalone mode — get_server() can block
    return None


def emit(event_type: str, payload: dict[str, Any]) -> None:
    """Publish a games event. No-ops if events brick unavailable."""
    invoker = _get_invoker()
    if invoker is None:
        logger.debug("No event invoker available, skipping: %s", event_type)
        return
    try:
        publish_input = build_event_publish_input(payload)
    except Exception as e:
        logger.warning("Failed to build publish input for %s: %s", event_type, e)
        return
    run_id = publish_input.get("payload", {}).get("run_id")
    try:
        invoker(
            "events_publish",
            source="games",
            event_type=event_type,
            run_id_authoritative=bool(run_id),
            **publish_input,
        )
    except Exception as e:
        logger.error(
            "events_publish failed for %s (source=games, run_id=%s): %s",
            event_type, run_id, e, exc_info=True,
        )
