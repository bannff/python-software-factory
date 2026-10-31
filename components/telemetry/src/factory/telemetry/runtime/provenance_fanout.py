"""Replay-safe downstream fan-out for immutable Telemetry mappings."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from factory.mcp_utils.interface import get_envelope, reset_envelope, set_envelope

from .provenance_mapping_models import is_graph_relationship_target
from .provenance_models import (
    AuthenticatedTelemetryContext, MaterializationMapping, TelemetryStoredRecord,
)
from .provenance_payload import GraphRelationshipPayload
from .provenance_resolution import invocation_failure
from .provenance_store import ProvenanceStore

ServiceGetter = Callable[[str], Any]


def _key(record: TelemetryStoredRecord, mapping: MaterializationMapping, index: int) -> str:
    base = (
        f"telemetry-materialize:{record.telemetry_ref}:"
        f"{mapping.mapping_id}:{mapping.version}"
    )
    return base if mapping.max_fan_out == 1 else f"{base}:{index}"


def fan_out(
    store: ProvenanceStore,
    record: TelemetryStoredRecord,
    mappings: list[MaterializationMapping],
    context: AuthenticatedTelemetryContext,
    get_service: ServiceGetter,
) -> bool:
    """Invoke only incomplete targets and persist each successful acknowledgement."""
    if any(not is_graph_relationship_target(mapping) for mapping in mappings):
        return False
    pending = [
        (mapping, index)
        for mapping in mappings
        for index in range(mapping.max_fan_out)
        if not store.has_materialization_completion(
            record.telemetry_ref, mapping.mapping_id, mapping.version, index,
        )
    ]
    if not pending:
        return True
    structured = get_service("tool_invoker_envelope")
    legacy = get_service("tool_invoker")
    if not callable(structured) and not callable(legacy):
        return False
    payload = GraphRelationshipPayload.from_record(record, context).model_dump(mode="json")
    for mapping, index in pending:
        target = {
            "brick_name": mapping.target_brick,
            "tool_name": mapping.target_capability,
            "version": mapping.target_version,
        }
        key = _key(record, mapping, index)
        envelope = dict(get_envelope() or {})
        envelope.update(context.model_dump(mode="json"))
        attributes = dict(envelope.get("attributes") or {})
        attributes["workflow_attempt_id"] = key
        envelope["attributes"] = attributes
        token = set_envelope(envelope)
        try:
            if callable(structured):
                result = structured(
                    target, arguments=payload, idempotency_key=key, envelope=envelope,
                )
            else:
                result = legacy(mapping.target_capability, **payload)
        except Exception:
            return False
        finally:
            reset_envelope(token)
        if invocation_failure(result) is not None:
            return False
        try:
            store.mark_materialization_completion(
                record.telemetry_ref, mapping.mapping_id, mapping.version, index,
            )
        except Exception:
            return False
    return True


__all__ = ["fan_out"]
