"""Deterministic (read-only) MCP tools for telemetry module."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput, CollectionStatusOutput, ConfigSchemaOutput, ContextOutput,
    ExporterRegistryOutput, ExtractContextInput, HealthOutput, MetricRegistryOutput,
    MetricsSummaryOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime") -> None:
    """Register deterministic tools."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get module capabilities and available tools."""
        return runtime.get_capabilities()

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Check service health and configuration status."""
        return runtime.health_check()

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CollectionStatusOutput)
    def telemetry_get_collection_status() -> ToolResult[CollectionStatusOutput]:
        """What telemetry collection actually does today: sampling, redaction, retention."""
        return runtime.get_collection_status()

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=MetricRegistryOutput)
    def get_metric_registry() -> ToolResult[MetricRegistryOutput]:
        """List all registered metric definitions."""
        return {"metrics": runtime.registries.metrics.as_list()}

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ExporterRegistryOutput)
    def get_exporter_registry() -> ToolResult[ExporterRegistryOutput]:
        """List all registered OTLP exporters."""
        return {"exporters": runtime.registries.exporters.as_list()}

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=MetricsSummaryOutput)
    def get_metrics_summary() -> ToolResult[MetricsSummaryOutput]:
        """Get current metrics snapshot (LLM tokens, agent executions, etc)."""
        return runtime.metrics_snapshot()

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Get JSON schemas for all configuration types."""
        return runtime.describe_config_schema()

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ContextOutput)
    def inject_context() -> ToolResult[ContextOutput]:
        """Inject current trace context into carrier headers (W3C TraceContext)."""
        return runtime.inject_context()

    @typed_tool(mcp)
    @deterministic(input_model=ExtractContextInput, output_model=ContextOutput)
    def extract_context(carrier: dict[str, str]) -> ToolResult[ContextOutput]:
        """Extract trace context from carrier headers (W3C TraceContext)."""
        return runtime.extract_context(carrier)
