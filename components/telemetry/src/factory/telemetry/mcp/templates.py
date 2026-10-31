"""Prompt templates for telemetry MCP prompts."""

from __future__ import annotations

CONFIGURE_OTEL_TEMPLATE = """# Configure OpenTelemetry Exporter

## Exporter: {exporter_id}
Endpoint: {endpoint}
Protocol: {protocol}

## Steps

1. **Create Exporter Config**
   ```
   write_config(
       kind="exporters",
       config={{
           "id": "{exporter_id}",
           "kind": "otlp",
           "endpoint": "{endpoint}",
           "protocol": "{protocol}",
           "timeout_seconds": 10
       }}
   )
   ```

2. **Verify Configuration**
   ```
   get_exporter_registry()
   ```

3. **Test Export**
   ```
   record_log(severity="INFO", body="Test log entry")
   flush_telemetry()
   ```

## Backend-Specific Notes
{backend_notes}
"""

DEBUG_TELEMETRY_TEMPLATE = """# Debug Telemetry Issue

## Issue Type: {issue_type}

## Diagnostic Steps

1. **Check Health**
   ```
   health_check()
   ```

2. **Check Exporters**
   ```
   get_exporter_registry()
   ```

3. **Check Metrics**
   ```
   get_metrics_summary()
   ```

4. **Force Flush**
   ```
   flush_telemetry(timeout_ms=10000)
   ```

## Common Issues

- **No data in backend**: Check endpoint URL and network connectivity
- **Missing traces**: Verify tracing_enabled in settings
- **Missing metrics**: Check metric definitions and allowed_attributes
- **High latency**: Increase timeout_seconds or use async export

## Next: {next_steps}
"""

CREATE_METRIC_TEMPLATE = """# Create Custom Metric

## Metric: {metric_id}
Type: {metric_type}
Name: {metric_name}

## Steps

1. **Define Metric**
   ```
   write_metric_file(
       file_id="{metric_id}",
       definitions=[{{
           "id": "{metric_id}",
           "type": "{metric_type}",
           "name": "{metric_name}",
           "description": "{description}",
           "unit": "{unit}",
           "allowed_attributes": {attributes}
       }}]
   )
   ```

2. **Verify Registration**
   ```
   get_metric_registry()
   ```

3. **Record Data**
   ```
   # Use appropriate recording tool based on metric type
   record_llm_interaction(...)  # for LLM metrics
   record_agent_execution(...)  # for agent metrics
   ```

## Metric Types
- `counter`: Monotonic increasing value
- `histogram`: Distribution of values
"""


def get_configure_otel_prompt(
    exporter_id: str = "otlp",
    endpoint: str = "http://localhost:4318",
    protocol: str = "http/protobuf",
) -> str:
    """Generate OTEL configuration prompt."""
    backend_notes = {
        "http://localhost:4318": "Local OTLP collector. Ensure collector is running.",
        "http://localhost:14268": "Jaeger direct. Use for traces only.",
    }.get(endpoint, "Verify endpoint accepts OTLP protocol.")

    return CONFIGURE_OTEL_TEMPLATE.format(
        exporter_id=exporter_id,
        endpoint=endpoint,
        protocol=protocol,
        backend_notes=backend_notes,
    )


def get_debug_telemetry_prompt(issue_type: str = "missing_data") -> str:
    """Generate telemetry debugging prompt."""
    next_steps = {
        "missing_data": "Check exporter endpoint and flush telemetry",
        "high_latency": "Increase timeout or switch to async export",
        "missing_traces": "Verify tracing_enabled and span lifecycle",
        "missing_metrics": "Check metric definitions and recording calls",
    }.get(issue_type, "Review health check output")

    return DEBUG_TELEMETRY_TEMPLATE.format(
        issue_type=issue_type,
        next_steps=next_steps,
    )


def get_create_metric_prompt(
    metric_id: str = "custom_metric",
    metric_type: str = "counter",
    metric_name: str = "custom.metric.total",
) -> str:
    """Generate metric creation prompt."""
    return CREATE_METRIC_TEMPLATE.format(
        metric_id=metric_id,
        metric_type=metric_type,
        metric_name=metric_name,
        description="Custom metric description",
        unit="1",
        attributes='["service", "operation"]',
    )
