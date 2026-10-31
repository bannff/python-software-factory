"""OpenTelemetry SpanExporter backed by authenticated provenance ingress."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .otlp_boundary import OTLPBatchAdapter, TelemetryOTLPBoundary
from .provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    MappingEdge,
    MaterializationMapping,
    TelemetryMaterialize,
)
from .provenance_support import telemetry_ref


def _activation(value: dict[str, Any] | None) -> MappingActivationRecord | None:
    if value is None:
        return None
    timestamp = value["activated_at"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    mappings = tuple(
        MaterializationMapping(**{
            **item, "accepted_signals": tuple(item["accepted_signals"]),
        }) for item in value.get("mappings", [])
    )
    edges = tuple(MappingEdge(**item) for item in value.get("edges", []))
    return MappingActivationRecord(
        registry_version=value["registry_version"], mappings=mappings,
        edges=edges, graph_digest=value.get("graph_digest", ""),
        activated_at=timestamp,
    )


class ProvenanceSpanExporter(SpanExporter):
    """Encode native spans and replay-safe materialize their deterministic refs."""

    def __init__(
        self, runtime: Any, *, context: dict[str, Any],
        mappings: list[tuple[str, str]], activation: dict[str, Any] | None = None,
    ) -> None:
        self._runtime = getattr(runtime, "provenance", runtime)
        self._context = AuthenticatedTelemetryContext.model_validate(context)
        self._mappings = [tuple(item) for item in mappings]
        self._activation = _activation(activation)
        self._activated = False
        self._last_error: str | None = None
        self._adapter = OTLPBatchAdapter()
        self._boundary = TelemetryOTLPBoundary(self._runtime, self._adapter)

    def _activate(self) -> None:
        if self._activation is not None and not self._activated:
            self._runtime.activate_mapping(self._activation)
            self._activated = True

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not spans:
            return SpanExportResult.SUCCESS
        try:
            # BatchSpanProcessor suppresses instrumentors around export, and
            # this also protects direct exporter use. The configured
            # SuppressionAwareSpanProcessor drops explicit library spans (such
            # as FastMCP server spans) started by the materialization callback.
            with suppress_instrumentation():
                self._activate()
                payload = encode_spans(spans).SerializeToString()
                batch = self._adapter.from_http(
                    payload, signal="traces", context=self._context,
                )
                result = self._boundary.ingest_http(
                    payload, signal="traces", context=self._context,
                    batch_id=batch.batch_id,
                )
                if result.status not in {"accepted", "duplicate"}:
                    return SpanExportResult.FAILURE
                refs = [
                    telemetry_ref(self._context, item.source_id)
                    for item in batch.items
                ]
                materialized = self._runtime.materialize(
                    TelemetryMaterialize(
                        telemetry_ids=refs,
                        mappings=self._mappings,
                    ),
                    self._context,
                )
                self._last_error = None
                return (
                    SpanExportResult.SUCCESS
                    if not materialized.retryable_telemetry_ids
                    else SpanExportResult.FAILURE
                )
        except Exception as exc:  # noqa: BLE001 - exporters must fail closed
            self._last_error = f"{type(exc).__name__}: {exc}"
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    def health_check(self) -> dict[str, Any]:
        return {
            "ok": bool(self._mappings),
            "kind": "provenance",
            "source_namespace": self._context.source_namespace,
            "mappings": [list(item) for item in self._mappings],
            "last_error": self._last_error,
        }
