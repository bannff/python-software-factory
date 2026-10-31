"""Shared event emission for workflow lifecycle activity."""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import (
    build_event_publish_input, is_protected_payload, protected_error_text,
    protected_error_value,
)

from .graph_sync import sync_activity

logger = logging.getLogger(__name__)


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def emit(event_type: str, payload: dict[str, Any], *sources: Any) -> None:
    protected = is_protected_payload(payload)
    payload = protected_error_value(payload, protected=protected)
    invoker = _get_invoker()
    sync_activity(event_type, payload, *sources)
    if invoker is None:
        logger.debug("No event invoker available, skipping shared emit: %s", event_type)
        return
    try:
        publish_input = build_event_publish_input(
            payload, *sources, authoritative_run_id=payload.get("run_id"),
        )
    except Exception as exc:
        logger.warning(
            "Failed to build publish input for %s: %s",
            event_type, protected_error_text(str(exc), protected=protected),
        )
        return
    run_id = publish_input.get("payload", {}).get("run_id")
    try:
        invoker(
            "events_publish",
            source="workflow",
            event_type=event_type,
            run_id_authoritative=bool(run_id),
            **publish_input,
        )
    except Exception as exc:
        logger.error(
            "events_publish failed for %s (source=workflow, run_id=%s): %s",
            event_type, run_id, protected_error_text(str(exc), protected=protected),
        )