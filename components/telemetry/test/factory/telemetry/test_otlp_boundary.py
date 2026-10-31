"""Focused OTLP HTTP/gRPC adapter boundary tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from pydantic import ValidationError

from factory.mcp_utils.interface import get_envelope
from factory.telemetry.runtime.otlp_boundary import (
    OTLPBatchAdapter, TelemetryOTLPBoundary,
)
from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext, TelemetryReferenceRead,
)
from factory.telemetry.runtime.provenance_runtime import TelemetryProvenanceRuntime
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore


def _context() -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id="tenant-1", producer_id="collector-1", principal_id="principal-1",
        visibility="private", source_namespace="otlp-tests",
    )


def test_http_otlp_trace_is_typed_and_context_bound() -> None:
    request = trace_service_pb2.ExportTraceServiceRequest()
    span = request.resource_spans.add().scope_spans.add().spans.add()
    span.trace_id = bytes.fromhex("1234" * 8)
    span.span_id = bytes.fromhex("abcd" * 4)
    span.parent_span_id = bytes.fromhex("beef" * 4)
    span.trace_state = "vendor=value"
    span.flags = 1
    span.name = "ingress"
    span.attributes.add(key="component", value={"string_value": "test"})

    context = _context()
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    result = TelemetryOTLPBoundary(runtime).ingest_http(
        request.SerializeToString(), signal="traces", context=context,
        batch_id="http-batch",
    )

    assert result.status == "accepted"
    reference = result.outcomes[0].telemetry_ref
    assert reference is not None
    stored = runtime.store.get_record(reference)
    assert stored is not None
    assert stored.item.trace_id == "1234" * 8
    assert stored.item.parent_span_id == "beef" * 4
    assert stored.item.trace_flags == 1
    assert stored.item.tracestate == "vendor=value"
    assert stored.context == context
    assert get_envelope() is None


def test_grpc_otlp_metric_uses_generated_batch_id() -> None:
    request = metrics_service_pb2.ExportMetricsServiceRequest()
    metric = request.resource_metrics.add().scope_metrics.add().metrics.add()
    metric.name = "latency"
    point = metric.gauge.data_points.add()
    point.time_unix_nano = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    point.as_double = 3.5
    point.attributes.add(key="run_id", value={"string_value": "run-1"})

    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    result = TelemetryOTLPBoundary(runtime).ingest_grpc(
        request.SerializeToString(), signal="metrics", context=_context(),
    )

    assert result.status == "accepted"
    assert result.batch_id.startswith("otlp-")
    assert result.outcomes[0].source_id.startswith("metric:latency:")


def test_otlp_adapter_rejects_zero_span_ids_before_retention() -> None:
    request = trace_service_pb2.ExportTraceServiceRequest()
    span = request.resource_spans.add().scope_spans.add().spans.add()
    span.trace_id = b"\x00" * 16
    span.span_id = bytes.fromhex("abcd" * 4)

    with pytest.raises(ValidationError, match="must not be all zero"):
        OTLPBatchAdapter().from_http(
            request.SerializeToString(), signal="traces", context=_context(),
        )


def test_optional_w3c_carrier_is_preserved_in_ingest_and_reference() -> None:
    request = trace_service_pb2.ExportTraceServiceRequest()
    span = request.resource_spans.add().scope_spans.add().spans.add()
    span.trace_id = bytes.fromhex("1234" * 8)
    span.span_id = bytes.fromhex("abcd" * 4)
    carrier = {
        "traceparent": (
            "00-0af7651916cd43dd8448eb211c80319c-"
            "b7ad6b7169203331-01"
        ),
        "tracestate": "vendor=value,other=state",
        "x-request": "preserved",
    }
    context = _context()
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore())
    decoded = OTLPBatchAdapter().from_http(
        request.SerializeToString(), signal="traces", context=context,
        carrier=carrier,
    )

    assert decoded.items[0].trace_context is not None
    assert decoded.items[0].trace_context.carrier == carrier
    assert decoded.items[0].trace_context.traceparent_version == "00"

    result = TelemetryOTLPBoundary(runtime).ingest_http(
        request.SerializeToString(), signal="traces", context=context,
        batch_id="carrier-batch", carrier=carrier,
    )
    reference = result.outcomes[0].telemetry_ref
    assert reference is not None
    stored = runtime.store.get_record(reference)
    assert stored is not None
    assert stored.item.trace_context is not None
    assert stored.item.trace_context.carrier == carrier
    read = runtime.read_reference(
        TelemetryReferenceRead(
            telemetry_id=reference, requested_fields={"trace_context"},
        ),
        context,
    )
    assert read.fields is not None
    assert read.fields["trace_context"]["traceparent"] == carrier["traceparent"]
    assert read.fields["trace_context"]["tracestate"] == carrier["tracestate"]
