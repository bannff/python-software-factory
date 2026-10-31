"""Service-only, tenant-bound publication of protected downstream signals.

``reward.computed`` and ``memory.learning_stored`` are reserved from public
``events_publish``. Only the Events brick's own reward/learning handlers may
emit them, and only through this digest- and tenant-bound service binding.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, operational, protected_canonical_json, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.projection import PublishOutput, TrustedLearningSignalInput
from ..runtime.envelope import ContextEnvelope
from ..runtime.learning_contracts import validate_learning_payload

if TYPE_CHECKING:
    from ..runtime.runtime import EventsRuntime

# Canonical source system per protected signal — preserves the byte-identical
# ``source`` the pre-protection public publish carried.
_SIGNAL_SOURCE = {
    "reward.computed": "events.rewards",
    "memory.learning_stored": "events.learning",
}


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"]) -> None:
    @typed_tool(mcp)
    @service_only(callers={"events"}, binding="projection")
    @operational(input_model=TrustedLearningSignalInput, output_model=PublishOutput)
    def events_publish_learning_signal(
        tenant_id: str, owner_id: str, event_type: str,
        subject_id: str, revision: int, payload_digest: str,
        payload: dict[str, Any],
    ) -> ToolResult[PublishOutput]:
        if payload_digest != hashlib.sha256(
            protected_canonical_json(payload),
        ).hexdigest():
            return ToolResult(ok=False, error="learning_signal_digest_mismatch")
        # Tenant binding: any identity the payload carries must not contradict
        # the attested authority. Absent payload identity inherits the binding.
        p_tenant = str(payload.get("tenant_id") or "")
        p_owner = str(payload.get("principal_id") or "")
        if (p_tenant and p_tenant != tenant_id) or (p_owner and p_owner != owner_id):
            return ToolResult(ok=False, error="learning_signal_tenant_mismatch")
        try:
            validated = validate_learning_payload(event_type, payload)
        except ValueError:
            return ToolResult(ok=False, error="learning_signal_payload_invalid")
        result = get_runtime().publish(
            event_type=event_type, payload=validated,
            source=_SIGNAL_SOURCE[event_type],
            envelope=ContextEnvelope(
                tenant_id=tenant_id, principal_id=owner_id,
                session_id=str(payload.get("session_id") or "") or None,
            ),
        )
        return PublishOutput(
            event_id=result.event_id, status=result.status,
            subscriptions_matched=result.subscriptions_matched,
            subscriptions_dispatched=result.subscriptions_dispatched,
            timestamp=str(result.timestamp),
        )


__all__ = ["register"]
