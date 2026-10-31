"""Service-only publication of content-free Graph projection requests."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, operational, protected_canonical_json, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.projection import PublishOutput, TrustedProjectionInput
from ..runtime.envelope import ContextEnvelope

if TYPE_CHECKING:
    from ..runtime.runtime import EventsRuntime

PROTECTED_EVENT_TYPES = frozenset({
    "graph.projection.requested", "dev_loop.cycle.completed",
    "reward.computed", "memory.learning_stored",
})


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"]) -> None:
    @typed_tool(mcp)
    @service_only(
        callers={"lessons", "kb", "memory", "workflow"}, binding="projection",
    )
    @operational(input_model=TrustedProjectionInput, output_model=PublishOutput)
    def events_publish_projection(
        tenant_id: str, owner_id: str, event_type: str,
        subject_id: str, revision: int, payload_digest: str,
        record: dict[str, Any],
    ) -> ToolResult[PublishOutput]:
        expected = hashlib.sha256(protected_canonical_json(record)).hexdigest()
        if payload_digest != expected:
            return ToolResult(ok=False, error="projection_payload_digest_mismatch")
        payload = {
            "tenant_id": tenant_id, "owner_id": owner_id,
            "event_type": event_type, "subject_id": subject_id,
            "revision": revision, "payload_digest": payload_digest,
            "record": record,
        }
        result = get_runtime().publish(
            event_type=event_type, payload=payload,
            source=str(record["source_system"]),
            envelope=ContextEnvelope(tenant_id=tenant_id, principal_id=owner_id),
        )
        return PublishOutput(
            event_id=result.event_id, status=result.status,
            subscriptions_matched=result.subscriptions_matched,
            subscriptions_dispatched=result.subscriptions_dispatched,
            timestamp=str(result.timestamp),
        )


__all__ = ["PROTECTED_EVENT_TYPES", "register"]
