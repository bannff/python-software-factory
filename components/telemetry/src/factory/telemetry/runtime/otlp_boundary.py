"""Authenticated OTLP HTTP/gRPC adapter boundary for Telemetry.

This module deliberately adapts transport payloads; it is not an HTTP listener
and it does not expose an MCP tool as one. API composition may mount the two
methods when the host supplies authentication and a network server context.
"""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import reset_envelope, set_envelope

from .otlp_conversion import OTLPSignal, decode_otlp
from .provenance_models import (
    AuthenticatedTelemetryContext,
    TelemetryIngestBatch,
    TelemetryIngestResult,
)
from .trace_context import TraceContextModel


class OTLPBatchAdapter:
    """Decode either OTLP transport encoding into a typed ingest batch."""

    def from_http(
        self,
        payload: bytes,
        *,
        signal: OTLPSignal,
        context: AuthenticatedTelemetryContext,
        batch_id: str | None = None,
        carrier: dict[str, str] | TraceContextModel | None = None,
    ) -> TelemetryIngestBatch:
        return decode_otlp(signal, payload, context, batch_id, carrier)

    def from_grpc(
        self,
        payload: bytes,
        *,
        signal: OTLPSignal,
        context: AuthenticatedTelemetryContext,
        batch_id: str | None = None,
        carrier: dict[str, str] | TraceContextModel | None = None,
    ) -> TelemetryIngestBatch:
        return decode_otlp(signal, payload, context, batch_id, carrier)


class TelemetryOTLPBoundary:
    """Run decoded HTTP/gRPC batches through authenticated Telemetry ingress."""

    def __init__(self, runtime: Any, adapter: OTLPBatchAdapter | None = None) -> None:
        self._runtime = getattr(runtime, "provenance", runtime)
        self._adapter = adapter or OTLPBatchAdapter()

    def ingest_http(
        self,
        payload: bytes,
        *,
        signal: OTLPSignal,
        context: AuthenticatedTelemetryContext,
        batch_id: str | None = None,
        carrier: dict[str, str] | TraceContextModel | None = None,
    ) -> TelemetryIngestResult:
        batch = self._adapter.from_http(
            payload, signal=signal, context=context, batch_id=batch_id,
            carrier=carrier,
        )
        return self._ingest(batch, context)

    def ingest_grpc(
        self,
        payload: bytes,
        *,
        signal: OTLPSignal,
        context: AuthenticatedTelemetryContext,
        batch_id: str | None = None,
        carrier: dict[str, str] | TraceContextModel | None = None,
    ) -> TelemetryIngestResult:
        batch = self._adapter.from_grpc(
            payload, signal=signal, context=context, batch_id=batch_id,
            carrier=carrier,
        )
        return self._ingest(batch, context)

    def _ingest(
        self,
        batch: TelemetryIngestBatch,
        context: AuthenticatedTelemetryContext,
    ) -> TelemetryIngestResult:
        context = AuthenticatedTelemetryContext.model_validate(context)
        token = set_envelope(context.model_dump(mode="json"))
        try:
            return self._runtime.ingest(batch, context)
        finally:
            reset_envelope(token)


__all__ = ["OTLPBatchAdapter", "TelemetryOTLPBoundary"]
