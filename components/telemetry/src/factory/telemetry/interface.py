"""Polylith Interface for telemetry module."""

from .server import (
    create_mcp_server as create_server, get_runtime, health_check,
)
from .runtime.runtime import TelemetryRuntime as Runtime
from .runtime.otlp_boundary import OTLPBatchAdapter, TelemetryOTLPBoundary
from .runtime.adapters.storage import (
    StorageLogExporter, StorageMetricExporter, StorageSpanExporter,
)
from .runtime.provenance_models import (
    AuthenticatedTelemetryContext, TelemetryIngestBatch, TelemetryMaterialize,
    TelemetryReferenceRead,
)
from .runtime.trace_context import (
    TraceContextModel, TraceContextOutput, validate_w3c_carrier,
)

__all__ = [
    "Runtime",
    "create_server",
    "get_runtime",
    "health_check",
    "StorageSpanExporter",
    "StorageMetricExporter",
    "StorageLogExporter",
    "AuthenticatedTelemetryContext", "TelemetryIngestBatch", "TelemetryMaterialize",
    "TelemetryReferenceRead", "OTLPBatchAdapter", "TelemetryOTLPBoundary",
    "TraceContextModel", "TraceContextOutput", "validate_w3c_carrier",
]
