"""Event emission for game lifecycle.

Publishes events via the events brick MCP interface.
Gracefully no-ops if the events brick is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import build_event_publish_input, make_serializable

logger = logging.getLogger(__name__)
_warned = False


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
    # The API process builds the server before any game call, but only registers the
    # service lazily; read the aggregator if it already exists. Never call
    # get_server() here — it can block in standalone mode.
    try:
        import sys
        interface = sys.modules.get("factory.mcp_server.interface")
        aggregator = interface.get_aggregator() if interface is not None else None
        if aggregator is not None:
            return aggregator.invoke_tool
    except Exception:
        pass
    return None


def _failure(result: Any) -> str:
    """Error text when the invoker reports failure in its result instead of raising."""
    if isinstance(result, dict):
        return str(result.get("error") or "") if result.get("ok") is False or "error" in result else ""
    if getattr(result, "ok", True) is False:
        return str(getattr(result, "error", "") or "failed")
    return ""


def emit(event_type: str, payload: dict[str, Any]) -> None:
    """Publish a games event. No-ops if events brick unavailable."""
    invoker = _get_invoker()
    if invoker is None:
        global _warned
        if not _warned:
            _warned = True
            logger.warning("No event invoker available; games events are dropped (first: %s)", event_type)
        return
    try:
        publish_input = build_event_publish_input(make_serializable(payload))
    except Exception as e:
        logger.warning("Failed to build publish input for %s: %s", event_type, e)
        return
    run_id = publish_input.get("payload", {}).get("run_id")
    try:
        result = invoker(
            "events_publish",
            source="games",
            event_type=event_type,
            run_id_authoritative=bool(run_id),
            **publish_input,
        )
        failure = _failure(result)
        if failure:
            logger.warning("events_publish rejected %s (source=games): %s", event_type, failure)
    except Exception as e:
        logger.error(
            "events_publish failed for %s (source=games, run_id=%s): %s",
            event_type, run_id, e, exc_info=True,
        )
