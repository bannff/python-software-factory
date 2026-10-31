"""Shared helpers for learning event handlers."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from ..mcp_result import successful_data
from ..models import Event

logger = logging.getLogger(__name__)

# Downstream signals reserved from public ``events_publish``; internal
# producers emit them only through the tenant-bound service publisher.
_PROTECTED_LEARNING_SIGNALS = frozenset({"reward.computed", "memory.learning_stored"})


def _base_payload(event: Event) -> dict[str, Any]:
    payload = event.payload
    run_id = payload.get("run_id", "")
    workflow_id = payload.get("workflow_id") or payload.get("graph_id", "")
    return {
        "run_id": run_id,
        "workflow_run_id": payload.get("workflow_run_id", run_id),
        "workflow_id": workflow_id,
        "graph_id": workflow_id,
        "session_id": event.session_id or payload.get("session_id", ""),
        "tenant_id": payload.get("tenant_id", ""),
        "principal_id": event.principal_id or payload.get("principal_id", ""),
        "profile_id": payload.get("profile_id", "default"),
        "profile_version": payload.get("profile_version", "v1"),
        "target_app": payload.get("target_app", ""),
        "workflow_type": payload.get("workflow_type", "auto"),
        "vuln_class": payload.get("vuln_class", ""),
        # bd:python-factory-twxj0 — dual-emit so domain handlers (which key
        # off domain_class) and security handlers (which key off vuln_class)
        # both receive a populated payload. Coalesces with vuln_class for
        # legacy producers per the meta-architect Q4 verdict.
        "domain_class": payload.get("domain_class") or payload.get("vuln_class", ""),
    }


def _publish(invoker: Any, event: Event, event_type: str, payload: dict[str, Any]) -> None:
    if event_type in _PROTECTED_LEARNING_SIGNALS:
        publish_learning_signal(invoker, event, event_type, payload)
        return
    invoker(
        "events_publish",
        event_type=event_type,
        source="events.learning",
        payload=payload,
        principal_id=event.principal_id,
        session_id=event.session_id,
        request_id=event.trace_id,
    )


def publish_learning_signal(
    invoker: Any, event: Event, event_type: str, payload: dict[str, Any],
) -> None:
    """Emit a protected downstream signal through the tenant-bound service."""
    from factory.mcp_utils.interface import get_service, protected_canonical_json

    factory = get_service("tool_invoker_for_caller")
    invoke = factory("events") if callable(factory) else None
    if callable(invoke):
        owner_id = str(payload.get("principal_id") or event.principal_id or "kiro-agent")
        tenant_id = str(payload.get("tenant_id") or "") or owner_id
        subject_id = str(payload.get("idempotency_key") or "")
        if subject_id:
            binding = {
                "tenant_id": tenant_id, "owner_id": owner_id,
                "event_type": event_type, "subject_id": subject_id,
                "revision": 1,
                "payload_digest": hashlib.sha256(
                    protected_canonical_json(payload),
                ).hexdigest(),
            }
            try:
                invoke(
                    {"brick_name": "events", "tool_name": "events_publish_learning_signal"},
                    arguments={**binding, "payload": payload},
                    idempotency_key=f"learning-signal:{event_type}:{subject_id}",
                    envelope={
                        "tenant_id": tenant_id, "principal_id": owner_id,
                        "session_id": event.session_id or "",
                    },
                    projection=binding,
                )
            except Exception:
                logger.warning("learning signal service publish failed (%s)", event_type)
            return
    logger.warning("learning signal service publisher unavailable (%s)", event_type)


def _already_published(invoker: Any, event_type: str, idempotency_key: str) -> bool:
    """Check whether a downstream canonical event already exists."""
    try:
        result = invoker(
            "events_query_events",
            event_type=event_type,
            payload_key="idempotency_key",
            payload_value=idempotency_key,
            limit=50,
        )
        data = successful_data(result)
        return bool(data and data.get("events"))
    except Exception:
        return False


# Sources whose score IS a ground-truth F1 (legacy empty = pre-seam gt path).
# The pipeline-f1 baseline / drift / improvement handlers ingest ONLY these,
# so quality (llm-judge), explicit feedback (user-feedback) and penalty
# (telemetry) signals never pollute the GT metric pools — and a negative
# PENALIZED scalar never enters trend math (bd:python-factory-pfvo9, Q5).
_GT_REWARD_SOURCES: frozenset[str] = frozenset({"", "gt-findings"})


def _is_gt_reward(payload: dict[str, Any]) -> bool:
    """True when a reward.computed payload is a ground-truth F1 signal."""
    return str(payload.get("source_id", "")) in _GT_REWARD_SOURCES
