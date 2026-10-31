"""MCP resources for telemetry module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import DOCS, get_doc, list_docs
from ..runtime.config import ExporterConfig, MetricDefinition, Settings

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime") -> None:
    """Register MCP resources for telemetry."""

    # Schema resources
    @mcp.resource("telemetry://schemas/settings")
    def get_settings_schema() -> str:
        """JSON schema for telemetry settings."""
        return json.dumps(Settings.model_json_schema(), indent=2)

    @mcp.resource("telemetry://schemas/exporter")
    def get_exporter_schema() -> str:
        """JSON schema for OTLP exporter configuration."""
        return json.dumps(ExporterConfig.model_json_schema(), indent=2)

    @mcp.resource("telemetry://schemas/metric")
    def get_metric_schema() -> str:
        """JSON schema for metric definition."""
        return json.dumps(MetricDefinition.model_json_schema(), indent=2)

    # Documentation resources
    @mcp.resource("telemetry://docs")
    def list_documentation() -> str:
        """List available documentation."""
        return json.dumps({
            "available_docs": list_docs(),
            "access_pattern": "telemetry://docs/{doc_name}",
        }, indent=2)

    @mcp.resource("telemetry://docs/overview")
    def get_overview_doc() -> str:
        """Overview documentation."""
        return get_doc("overview") or "Documentation not found"

    @mcp.resource("telemetry://docs/otel")
    def get_otel_doc() -> str:
        """OpenTelemetry documentation."""
        return get_doc("otel") or "Documentation not found"

    @mcp.resource("telemetry://docs/metrics")
    def get_metrics_doc() -> str:
        """Metrics documentation."""
        return get_doc("metrics") or "Documentation not found"

    @mcp.resource("telemetry://docs/tracing")
    def get_tracing_doc() -> str:
        """Tracing documentation."""
        return get_doc("tracing") or "Documentation not found"

    @mcp.resource("telemetry://docs/when-to-use")
    def get_when_to_use_doc() -> str:
        """When to use telemetry vs logger."""
        return get_doc("when_to_use") or "Documentation not found"

    # Live data resources
    @mcp.resource("telemetry://metrics")
    def get_metrics_list() -> str:
        """List registered metrics."""
        metrics = runtime.registries.metrics.as_list()
        return json.dumps({
            "metrics": metrics,
            "count": len(metrics),
        }, indent=2)

    @mcp.resource("telemetry://exporters")
    def get_exporters_list() -> str:
        """List configured exporters."""
        exporters = runtime.registries.exporters.as_list()
        return json.dumps({
            "exporters": exporters,
            "count": len(exporters),
        }, indent=2)

    @mcp.resource("telemetry://summary")
    def get_telemetry_summary() -> str:
        """Get current telemetry summary."""
        return json.dumps(runtime.metrics_snapshot(), indent=2, default=str)

    # Factory cross-reference
    @mcp.resource("telemetry://factory")
    def get_factory_reference() -> str:
        """Cross-reference to factory foreman."""
        return json.dumps({
            "brick": "telemetry",
            "namespace": "factory.telemetry",
            "foreman_tools": [
                "foreman_info",
                "foreman_check",
                "foreman_guardian_check",
            ],
            "related_bricks": [
                {"name": "agent", "purpose": "Agent execution tracing"},
                {"name": "workflow", "purpose": "Workflow execution metrics"},
                {"name": "llm_gateway", "purpose": "LLM token/cost tracking"},
                {"name": "logger", "purpose": "Structured logging (complementary — see telemetry://docs/when-to-use)"},
            ],
        }, indent=2)
