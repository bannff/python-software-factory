"""Typed MCP adapters for authenticated Telemetry provenance operations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts.provenance import (
    TelemetryIngestBatch, TelemetryIngestResult, TelemetryMaterialize,
    TelemetryMaterializeResult, TelemetryReferenceRead, TelemetryReferenceResult,
)
from ..runtime.provenance_runtime import ProvenanceAuthenticationError

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime") -> None:
    """Register provenance tools; context is resolved only on the server."""

    @typed_tool(mcp)
    @operational(input_model=TelemetryIngestBatch, output_model=TelemetryIngestResult)
    def telemetry_ingest_batch(batch_id: str, items: list[dict]) -> ToolResult[TelemetryIngestResult]:
        try:
            return runtime.ingest_provenance(TelemetryIngestBatch(batch_id=batch_id, items=items))
        except ProvenanceAuthenticationError:
            return ToolResult(ok=False, error="unauthenticated_context")

    @typed_tool(mcp)
    @operational(input_model=TelemetryReferenceRead, output_model=TelemetryReferenceResult)
    def telemetry_read_reference(telemetry_id: str, requested_fields: set[str]) -> ToolResult[TelemetryReferenceResult]:
        try:
            return runtime.read_provenance_reference(TelemetryReferenceRead(telemetry_id=telemetry_id, requested_fields=requested_fields))
        except ProvenanceAuthenticationError:
            return ToolResult(ok=False, error="unauthenticated_context")

    @typed_tool(mcp)
    @operational(input_model=TelemetryMaterialize, output_model=TelemetryMaterializeResult)
    def telemetry_materialize(telemetry_ids: list[str], mappings: list[tuple[str, str]]) -> ToolResult[TelemetryMaterializeResult]:
        try:
            return runtime.materialize_provenance(TelemetryMaterialize(telemetry_ids=telemetry_ids, mappings=mappings))
        except ProvenanceAuthenticationError:
            return ToolResult(ok=False, error="unauthenticated_context")
