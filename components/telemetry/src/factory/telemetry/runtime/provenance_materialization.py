"""Allowlisted Telemetry provenance materialization and context binding."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    MaterializationMapping,
    TelemetryItemOutcome,
    TelemetryMaterialize,
    TelemetryMaterializeResult,
    TelemetryStoredRecord,
)
from .provenance_fanout import fan_out
from .provenance_store import ProvenanceStore

ServiceGetter = Callable[[str], Any]


def _selected_mappings(
    activation: MappingActivationRecord | None,
    request: TelemetryMaterialize,
) -> list[MaterializationMapping]:
    if activation is None:
        return []
    chosen = set(request.mappings)
    return [item for item in activation.mappings
            if (item.mapping_id, item.version) in chosen]


def materialize(
    store: ProvenanceStore,
    activation: MappingActivationRecord | None,
    request: TelemetryMaterialize,
    context: AuthenticatedTelemetryContext,
    get_service: ServiceGetter,
) -> TelemetryMaterializeResult:
    """Materialize only authenticated references through active mappings."""
    request = TelemetryMaterialize.model_validate(request)
    mappings = _selected_mappings(activation, request)
    outcomes: list[TelemetryItemOutcome] = []
    retryable: list[str] = []
    for telemetry_id in request.telemetry_ids:
        record = store.get_record(telemetry_id)
        if record is None:
            outcomes.append(TelemetryItemOutcome(
                source_id=telemetry_id, status="retained_unmaterialized",
                telemetry_ref=telemetry_id, retryable=True,
                reason="source_unavailable",
            ))
            retryable.append(telemetry_id)
            continue
        same_scope = (
            record.context.tenant_id == context.tenant_id
            and record.context.producer_id == context.producer_id
            and record.context.source_namespace == context.source_namespace
        )
        principal_allowed = (
            record.context.visibility != "private"
            or record.context.principal_id == context.principal_id
        )
        if not (same_scope and principal_allowed):
            outcomes.append(TelemetryItemOutcome(
                source_id=record.item.source_id,
                status="retained_unmaterialized", telemetry_ref=telemetry_id,
                retryable=False, reason="source_inaccessible",
            ))
            continue
        if record.materialized:
            outcomes.append(TelemetryItemOutcome(
                source_id=record.item.source_id, status="duplicate",
                telemetry_ref=telemetry_id, retryable=False,
                reason="already_materialized",
            ))
            continue
        selected = [item for item in mappings
                    if record.item.signal in item.accepted_signals]
        if not selected:
            outcomes.append(TelemetryItemOutcome(
                source_id=record.item.source_id,
                status="retained_unmaterialized", telemetry_ref=telemetry_id,
                retryable=True, reason="mapping_unavailable_or_failed",
            ))
            retryable.append(telemetry_id)
            continue
        if not store.claim_materialization(telemetry_id):
            current = store.get_record(telemetry_id)
            if current is not None and current.materialized:
                outcomes.append(TelemetryItemOutcome(
                    source_id=current.item.source_id, status="duplicate",
                    telemetry_ref=telemetry_id, retryable=False,
                    reason="already_materialized",
                ))
            else:
                outcomes.append(TelemetryItemOutcome(
                    source_id=record.item.source_id,
                    status="retained_unmaterialized", telemetry_ref=telemetry_id,
                    retryable=True, reason="materialization_in_progress",
                ))
                retryable.append(telemetry_id)
            continue
        if not fan_out(store, record, selected, context, get_service):
            store.release_materialization(telemetry_id)
            outcomes.append(TelemetryItemOutcome(
                source_id=record.item.source_id,
                status="retained_unmaterialized", telemetry_ref=telemetry_id,
                retryable=True, reason="mapping_unavailable_or_failed",
            ))
            retryable.append(telemetry_id)
            continue
        store.complete_materialization(telemetry_id)
        outcomes.append(TelemetryItemOutcome(
            source_id=record.item.source_id, status="materialized",
            telemetry_ref=telemetry_id, retryable=False,
        ))
    return TelemetryMaterializeResult(
        outcomes=outcomes,
        materialized=sum(item.status == "materialized" for item in outcomes),
        retained_unmaterialized=sum(
            item.status == "retained_unmaterialized" for item in outcomes
        ),
        retryable_telemetry_ids=retryable,
    )


__all__ = ["materialize"]
