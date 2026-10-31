"""Trusted Events-to-Graph projection dispatch."""
from __future__ import annotations

from typing import Any

from ..mcp.contracts.projection import TrustedProjectionInput
from .models import Event


def dispatch_projection(event: Event) -> dict[str, Any]:
    parsed = TrustedProjectionInput.model_validate(event.payload)
    from factory.mcp_utils.interface import get_service

    factory = get_service("tool_invoker_for_caller")
    invoke = factory("events") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("caller-bound Graph projector unavailable")
    binding = {
        "tenant_id": parsed.tenant_id, "owner_id": parsed.owner_id,
        "event_type": parsed.event_type, "subject_id": parsed.subject_id,
        "revision": parsed.revision, "payload_digest": parsed.payload_digest,
    }
    return invoke(
        {"brick_name": "graph", "tool_name": "graph_project_event"},
        arguments={**binding, "record": parsed.record.model_dump(mode="json")},
        idempotency_key=f"graph-projection:{event.id}",
        envelope={
            "tenant_id": parsed.tenant_id, "principal_id": parsed.owner_id,
            "correlation_id": event.id,
        },
        projection=binding,
    )


__all__ = ["dispatch_projection"]
