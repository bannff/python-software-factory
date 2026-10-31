"""Native span ingest and duplicate-materialization crash replay."""
from __future__ import annotations

from datetime import UTC, datetime

from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from factory.mcp_utils.interface import get_service, set_service
from factory.telemetry.runtime.provenance_exporter import ProvenanceSpanExporter
from factory.telemetry.runtime.provenance_mapping_models import MappingActivationRecord
from factory.telemetry.runtime.provenance_runtime import TelemetryProvenanceRuntime
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore
from factory.telemetry.runtime.suppression_processor import (
    SuppressionAwareSpanProcessor,
)


def activation() -> dict:
    return MappingActivationRecord(
        registry_version="1",
        mappings=({
            "mapping_id": "lineage", "version": "1",
            "accepted_signals": ("span",),
            "target_brick": "graph",
            "target_capability": "graph_write_relationship",
            "target_version": "1", "max_fan_out": 1,
        },),
        edges=(), activated_at=datetime.now(UTC),
    ).model_dump(mode="json")


def finished_span():
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    with provider.get_tracer("test").start_as_current_span(
        "tool", attributes={"run_id": "wfr:v1:test"},
    ):
        pass
    return memory.get_finished_spans()[0]


def test_duplicate_ingest_replays_materialization_after_crash(tmp_path) -> None:
    previous_resolver = get_service("provenance_target_resolver")
    previous_invoker = get_service("tool_invoker_envelope")
    calls = []

    def invoke(target, *, arguments, idempotency_key, envelope):
        calls.append(idempotency_key)
        if len(calls) == 1:
            raise RuntimeError("crash after durable ingest")
        return {"ok": True, "result": {"structured_content": {"accepted": True}}}

    set_service("provenance_target_resolver", lambda target: target.version)
    set_service("tool_invoker_envelope", invoke)
    try:
        runtime = TelemetryProvenanceRuntime(
            JsonProvenanceStore(tmp_path / "provenance.sqlite3")
        )
        exporter = ProvenanceSpanExporter(
            runtime,
            context={
                "tenant_id": "tenant", "producer_id": "runtime",
                "principal_id": "control-plane", "visibility": "internal",
                "source_namespace": "test.native",
            },
            mappings=[("lineage", "1")],
            activation=activation(),
        )
        span = finished_span()
        assert exporter.export((span,)) is SpanExportResult.FAILURE
        second = exporter.export((span,))
        assert second is SpanExportResult.SUCCESS, exporter.health_check()
        assert len(calls) == 2
        with runtime.store._connection() as connection:
            row = connection.execute(
                "SELECT materialized FROM records"
            ).fetchone()
        assert row is not None and row[0] == 1
    finally:
        set_service("provenance_target_resolver", previous_resolver)
        set_service("tool_invoker_envelope", previous_invoker)


def test_suppression_processor_drops_explicit_callback_spans() -> None:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        SuppressionAwareSpanProcessor(SimpleSpanProcessor(memory))
    )
    tracer = provider.get_tracer("test")

    with suppress_instrumentation():
        with tracer.start_as_current_span("explicit-callback-span"):
            pass
    with tracer.start_as_current_span("source-span"):
        pass

    assert [span.name for span in memory.get_finished_spans()] == ["source-span"]
    provider.shutdown()
