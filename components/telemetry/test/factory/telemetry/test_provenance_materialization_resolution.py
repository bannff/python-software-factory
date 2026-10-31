"""Structured Telemetry provenance materialization contracts."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import pytest

from factory.graph.runtime.provenance_models import GraphRelationshipWrite
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_result import fail
from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    MaterializationMapping,
    TelemetryIngestBatch,
    TelemetryIngestItem,
    TelemetryMaterialize,
)
from factory.telemetry.runtime.provenance_runtime import TelemetryProvenanceRuntime
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore


_EXPECTED_FIELDS = set(GraphRelationshipWrite.model_fields)


def _context() -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id="tenant-1", producer_id="producer-1", principal_id="principal-1",
        visibility="private", source_namespace="tests",
    )


def _mapping(mapping_id: str = "graph") -> MaterializationMapping:
    return MaterializationMapping(
        mapping_id=mapping_id, version="1", accepted_signals=("span",),
        target_brick="graph", target_capability="graph_write_relationship",
        target_version="1", max_fan_out=1,
    )


def _batch() -> TelemetryIngestBatch:
    return TelemetryIngestBatch(
        batch_id="batch-1",
        items=[TelemetryIngestItem(
            source_id="source-1", canonical_payload={"value": 1}, signal="span",
        )],
    )


def _runtime(resolver) -> TelemetryProvenanceRuntime:
    runtime = TelemetryProvenanceRuntime(
        JsonProvenanceStore(), target_resolver=resolver,
    )
    runtime.activate_mapping(MappingActivationRecord(
        registry_version="1", mappings=(_mapping(),), edges=(),
        activated_at=datetime.now(timezone.utc),
    ))
    return runtime


@contextmanager
def _structured_invoker(callback) -> Iterator[None]:
    previous_structured = get_service("tool_invoker_envelope")
    previous_legacy = get_service("tool_invoker")
    set_service("tool_invoker_envelope", callback)
    set_service("tool_invoker", None)
    try:
        yield
    finally:
        set_service("tool_invoker_envelope", previous_structured)
        set_service("tool_invoker", previous_legacy)


def test_activation_rejects_unresolved_target() -> None:
    runtime = TelemetryProvenanceRuntime(
        JsonProvenanceStore(), target_resolver=lambda _target: None,
    )
    record = MappingActivationRecord(
        registry_version="1", mappings=(_mapping(),), edges=(),
        activated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(
        ValueError,
        match="unresolved materialization target: graph/graph_write_relationship@1",
    ):
        runtime.activate_mapping(record)


def test_activation_rejects_payload_incompatible_target() -> None:
    mapping = _mapping().model_copy(update={
        "target_brick": "events", "target_capability": "events_publish",
    })
    with pytest.raises(ValueError, match="compatible with GraphRelationshipPayload"):
        MappingActivationRecord(
            registry_version="1", mappings=(mapping,), edges=(),
            activated_at=datetime.now(timezone.utc),
        )


    context = _context()
    runtime = _runtime(lambda target: target.version)
    reference = runtime.ingest(_batch(), context).outcomes[0].telemetry_ref
    assert reference is not None
    calls: list[dict[str, Any]] = []

    def invoke(target, *, arguments, idempotency_key, envelope):
        assert target == {
            "brick_name": "graph",
            "tool_name": "graph_write_relationship",
            "version": "1",
        }
        assert set(arguments) == _EXPECTED_FIELDS
        payload = GraphRelationshipWrite.model_validate(arguments)
        assert payload.source_system == "telemetry"
        assert payload.source_identity.startswith("telemetry-source-")
        assert len(payload.source_digest) == 64
        assert payload.relation_type == "OBSERVED"
        assert payload.source_endpoint == reference
        assert payload.target_endpoint == "source:tests:source-1"
        assert payload.source_ref == reference
        assert payload.visibility == context.visibility
        assert payload.browse_metadata["tenant_id"] == context.tenant_id
        assert payload.browse_metadata["producer_id"] == context.producer_id
        assert "canonical_payload" not in payload.browse_metadata
        assert envelope["tenant_id"] == context.tenant_id
        assert envelope["producer_id"] == context.producer_id
        assert envelope["principal_id"] == context.principal_id
        assert envelope["source_namespace"] == context.source_namespace
        assert idempotency_key == f"telemetry-materialize:{reference}:graph:1"
        calls.append({"target": target, "payload": payload, "envelope": envelope})
        return {"ok": True, "result": {"structured_content": {"accepted": True}}}

    with _structured_invoker(invoke):
        result = runtime.materialize(
            TelemetryMaterialize(
                telemetry_ids=[reference], mappings=[("graph", "1")],
            ),
            context,
        )

    assert result.materialized == 1
    assert result.retained_unmaterialized == 0
    assert len(calls) == 1


@pytest.mark.parametrize("failure_kind", ["typed", "legacy"])
def test_typed_and_legacy_invocation_failures_remain_retryable(failure_kind: str) -> None:
    context = _context()
    runtime = _runtime(lambda target: target.version)
    reference = runtime.ingest(_batch(), context).outcomes[0].telemetry_ref
    assert reference is not None

    def invoke(*_args, **_kwargs):
        return fail("unsupported_backend") if failure_kind == "typed" else {"error": "legacy-failure"}

    with _structured_invoker(invoke):
        result = runtime.materialize(
            TelemetryMaterialize(
                telemetry_ids=[reference], mappings=[("graph", "1")],
            ),
            context,
        )

    assert result.materialized == 0
    assert result.retained_unmaterialized == 1
    assert result.retryable_telemetry_ids == [reference]
    stored = runtime.store.get_record(reference)
    assert stored is not None and not stored.materialized


def test_partial_fan_out_retry_skips_acknowledged_target_and_reuses_key() -> None:
    context = _context()
    mappings = (_mapping("a"), _mapping("b"))
    runtime = TelemetryProvenanceRuntime(
        JsonProvenanceStore(), target_resolver=lambda target: target.version,
    )
    runtime.activate_mapping(MappingActivationRecord(
        registry_version="1", mappings=mappings, edges=(),
        activated_at=datetime.now(timezone.utc),
    ))
    reference = runtime.ingest(_batch(), context).outcomes[0].telemetry_ref
    assert reference is not None
    calls: list[str] = []
    failures = {"b": 1}

    def invoke(_target, *, idempotency_key, **_kwargs):
        calls.append(idempotency_key)
        mapping_id = idempotency_key.rsplit(":", 2)[-2]
        if failures.get(mapping_id, 0):
            failures[mapping_id] -= 1
            return fail("temporary")
        return {"ok": True, "result": {"structured_content": {"accepted": True}}}

    request = TelemetryMaterialize(
        telemetry_ids=[reference], mappings=[("a", "1"), ("b", "1")],
    )
    with _structured_invoker(invoke):
        first = runtime.materialize(request, context)
        retry = runtime.materialize(request, context)

    key_a = f"telemetry-materialize:{reference}:a:1"
    key_b = f"telemetry-materialize:{reference}:b:1"
    assert first.retained_unmaterialized == 1
    assert retry.materialized == 1
    assert calls == [key_a, key_b, key_b]
