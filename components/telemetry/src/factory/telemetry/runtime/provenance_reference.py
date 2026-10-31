"""Authenticated raw-reference reads for Telemetry provenance."""
from __future__ import annotations

from .provenance_models import (
    AuthenticatedTelemetryContext,
    AuthorizationDecision,
    TelemetryReferenceRead,
    TelemetryReferenceResult,
)
from .provenance_store import ProvenanceStore

_ALLOWED_FIELDS = frozenset({
    "telemetry_ref", "source_id", "canonical_payload", "trace_id", "span_id",
    "parent_span_id", "trace_flags", "tracestate", "trace_context", "signal",
    "attributes", "retained_at", "materialized",
})


def read_reference(
    store: ProvenanceStore,
    request: TelemetryReferenceRead,
    context: AuthenticatedTelemetryContext,
) -> TelemetryReferenceResult:
    """Return only fields authorized by the producer, tenant, namespace, and principal."""
    request = TelemetryReferenceRead.model_validate(request)
    record = store.get_record(request.telemetry_id)
    if record is None:
        decision = AuthorizationDecision(
            permitted=False, permitted_fields=set(), denial_code="source_unavailable",
        )
        return TelemetryReferenceResult(
            telemetry_id=request.telemetry_id, found=False, authorized=False,
            decision=decision,
        )

    same_tenant_producer = (
        record.context.tenant_id == context.tenant_id
        and record.context.producer_id == context.producer_id
    )
    same_scope = (
        same_tenant_producer
        and record.context.source_namespace == context.source_namespace
    )
    principal_allowed = (
        record.context.visibility != "private"
        or record.context.principal_id == context.principal_id
    )
    permitted = same_scope and principal_allowed
    if permitted:
        denial = None
    elif not same_tenant_producer:
        denial = "tenant_or_producer_mismatch"
    elif record.context.source_namespace != context.source_namespace:
        denial = "source_namespace_mismatch"
    else:
        denial = "source_inaccessible"

    permitted_fields = request.requested_fields & _ALLOWED_FIELDS if permitted else set()
    fields = None
    if permitted:
        raw = {
            "telemetry_ref": record.telemetry_ref,
            **record.item.model_dump(mode="json"),
            "retained_at": record.retained_at.isoformat(),
            "materialized": record.materialized,
        }
        fields = {key: raw[key] for key in permitted_fields if key in raw}
    decision = AuthorizationDecision(
        permitted=permitted,
        permitted_fields=permitted_fields,
        denial_code=denial,
    )
    return TelemetryReferenceResult(
        telemetry_id=request.telemetry_id, found=True, authorized=permitted,
        fields=fields, decision=decision,
    )


__all__ = ["read_reference"]
