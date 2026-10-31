"""MCP prompts for telemetry module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import (
    get_configure_otel_prompt,
    get_debug_telemetry_prompt,
    get_create_metric_prompt,
)

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime") -> None:
    """Register MCP prompts for telemetry."""

    @mcp.prompt()
    def configure_otel(
        exporter_id: str = "otlp",
        endpoint: str = "http://localhost:4318",
        protocol: str = "http/protobuf",
    ) -> str:
        """Guide for configuring an OpenTelemetry exporter.

        Args:
            exporter_id: Unique exporter identifier
            endpoint: OTLP endpoint URL
            protocol: Protocol (http/protobuf or grpc)
        """
        return get_configure_otel_prompt(exporter_id, endpoint, protocol)

    @mcp.prompt()
    def debug_telemetry(issue_type: str = "missing_data") -> str:
        """Guide for debugging telemetry issues.

        Args:
            issue_type: Type of issue (missing_data, high_latency, missing_traces)
        """
        return get_debug_telemetry_prompt(issue_type)

    @mcp.prompt()
    def create_metric(
        metric_id: str = "custom_metric",
        metric_type: str = "counter",
        metric_name: str = "custom.metric.total",
    ) -> str:
        """Guide for creating a custom metric definition.

        Args:
            metric_id: Unique metric identifier
            metric_type: Type of metric (counter, histogram)
            metric_name: OTEL metric name
        """
        return get_create_metric_prompt(metric_id, metric_type, metric_name)
