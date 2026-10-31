"""Focused Telemetry provenance authentication and replay tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from factory.mcp_utils.interface import get_envelope, reset_envelope, set_envelope
from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    MappingEdge,
    MappingNodeRef,
    MaterializationMapping,
    TelemetryIngestBatch,
    TelemetryIngestItem,
    TelemetryMaterialize,
    TelemetryReferenceRead,
)
from factory.telemetry.runtime.provenance_runtime import (
    TelemetryProvenanceRuntime,
)
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore

def _context(tenant: str = "tenant-1") -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id=tenant, producer_id="producer-1", principal_id="principal-1",
        visibility="private", source_namespace="tests",
    )


def _batch(value: int = 1) -> TelemetryIngestBatch:
    return TelemetryIngestBatch(
        batch_id="batch-1",
        items=[TelemetryIngestItem(
            source_id="source-1", canonical_payload={"value": value}, signal="span",
        )],
    )

def test_authenticated_context_scopes_idempotency_and_reference_fields() -> None:
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    context = _context()
    token = set_envelope(context.model_dump())
    try:
        accepted = runtime.ingest(_batch())
        duplicate = runtime.ingest(_batch())
        conflict = runtime.ingest(_batch(2))
    finally:
        reset_envelope(token)

    assert accepted.status == "accepted"
    assert duplicate.status == "duplicate"
    assert conflict.status == "conflict"
    reference = accepted.outcomes[0].telemetry_ref
    assert reference is not None
    allowed = runtime.read_reference(
        TelemetryReferenceRead(telemetry_id=reference, requested_fields={"source_id"}),
        context,
    )
    denied = runtime.read_reference(
        TelemetryReferenceRead(telemetry_id=reference, requested_fields={"source_id"}),
        _context("tenant-2"),
    )
    assert allowed.authorized and allowed.fields == {"source_id": "source-1"}
    assert denied.found and not denied.authorized

def test_materialize_without_allowlisted_mapping_is_retryable() -> None:
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    accepted = runtime.ingest(_batch(), _context())
    reference = accepted.outcomes[0].telemetry_ref
    result = runtime.materialize(
        TelemetryMaterialize(telemetry_ids=[reference], mappings=[]), _context(),
    )

    assert result.materialized == 0
    assert result.retained_unmaterialized == 1
    assert result.retryable_telemetry_ids == [reference]

def test_mapping_activation_rejects_cycles_and_forbidden_targets() -> None:
    mapping_a = MaterializationMapping(
        mapping_id="a", version="1", accepted_signals=("span",),
        target_brick="graph", target_capability="graph_write_relationship",
        target_version="1", max_fan_out=1,
    )
    mapping_b = mapping_a.model_copy(update={"mapping_id": "b"})
    cycle = (
        MappingEdge(source=MappingNodeRef(mapping_id="a", version="1"), target=MappingNodeRef(mapping_id="b", version="1")),
        MappingEdge(source=MappingNodeRef(mapping_id="b", version="1"), target=MappingNodeRef(mapping_id="a", version="1")),
    )
    with pytest.raises(ValidationError, match="acyclic"):
        MappingActivationRecord(
            registry_version="1", mappings=(mapping_a, mapping_b), edges=cycle,
            activated_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError, match="allowed capability"):
        MappingActivationRecord(
            registry_version="1", mappings=(mapping_a.model_copy(update={"target_brick": "telemetry"}),),
            edges=(), activated_at=datetime.now(timezone.utc),
        )

@given(st.integers(min_value=0, max_value=1000))
def test_same_source_replay_is_duplicate_for_any_json_scalar(value: int) -> None:
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    batch = _batch(value)
    first = runtime.ingest(batch, _context())
    second = runtime.ingest(batch, _context())
    assert first.status == "accepted"
    assert second.status == "duplicate"

def test_mapping_activation_survives_store_restart(tmp_path) -> None:
    path = tmp_path / "provenance.json"
    mapping = MaterializationMapping(
        mapping_id="graph", version="1", accepted_signals=("span",),
        target_brick="graph", target_capability="graph_write_relationship",
        target_version="1", max_fan_out=1,
    )
    record = MappingActivationRecord(
        registry_version="1", mappings=(mapping,), edges=(),
        activated_at=datetime.now(timezone.utc),
    )
    TelemetryProvenanceRuntime(
        JsonProvenanceStore(path), target_resolver=lambda target: target.version,
    ).activate_mapping(record)
    restored = TelemetryProvenanceRuntime(JsonProvenanceStore(path))

    assert restored._activation is not None
    assert restored._activation.graph_digest == record.graph_digest

def test_reference_and_materialization_require_source_namespace() -> None:
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    context = _context()
    accepted = runtime.ingest(_batch(), context)
    reference = accepted.outcomes[0].telemetry_ref
    other_namespace = context.model_copy(update={"source_namespace": "other"})

    denied = runtime.read_reference(
        TelemetryReferenceRead(telemetry_id=reference, requested_fields={"source_id"}),
        other_namespace,
    )
    materialized = runtime.materialize(
        TelemetryMaterialize(telemetry_ids=[reference], mappings=[]), other_namespace,
    )

    assert denied.found and not denied.authorized
    assert denied.decision.denial_code == "source_namespace_mismatch"
    assert materialized.outcomes[0].reason == "source_inaccessible"
    assert materialized.outcomes[0].retryable is False

def test_materialization_replay_is_duplicate_and_binds_context(monkeypatch) -> None:
    mapping = MaterializationMapping(
        mapping_id="graph", version="1", accepted_signals=("span",),
        target_brick="graph", target_capability="graph_write_relationship",
        target_version="1", max_fan_out=1,
    )
    runtime = TelemetryProvenanceRuntime(
        JsonProvenanceStore(), target_resolver=lambda target: target.version,
    )
    runtime.activate_mapping(MappingActivationRecord(
        registry_version="1", mappings=(mapping,), edges=(),
        activated_at=datetime.now(timezone.utc),
    ))
    context = _context()
    reference = runtime.ingest(_batch(), context).outcomes[0].telemetry_ref
    calls: list[dict] = []

    def invoke(_tool_name: str, **_kwargs):
        calls.append(dict(get_envelope() or {}))
        return {"ok": True}

    monkeypatch.setattr(
        "factory.telemetry.runtime.provenance_runtime.get_service",
        lambda name: invoke if name == "tool_invoker" else None,
    )
    request = TelemetryMaterialize(
        telemetry_ids=[reference], mappings=[("graph", "1")],
    )
    first = runtime.materialize(request, context)
    replay = runtime.materialize(request, context)

    assert first.materialized == 1
    assert replay.materialized == 0
    assert replay.outcomes[0].status == "duplicate"
    assert replay.outcomes[0].reason == "already_materialized"
    assert len(calls) == 1
    assert calls[0]["tenant_id"] == context.tenant_id
    assert calls[0]["source_namespace"] == context.source_namespace

def test_strict_ingress_rejects_all_zero_w3c_identifiers() -> None:
    for field, length in (("trace_id", 32), ("span_id", 16), ("parent_span_id", 16)):
        with pytest.raises(ValidationError, match="must not be all zero"):
            TelemetryIngestItem(
                source_id=f"zero-{field}",
                canonical_payload={},
                signal="span",
                **{field: "0" * length},
            )
