"""Documentation content for telemetry MCP resources."""

from __future__ import annotations

OVERVIEW_DOC = """# Telemetry Brick

Observability and distributed tracing via OpenTelemetry (OTLP).

## Key Concepts

### Traces
Distributed tracing with W3C TraceContext propagation.
- `start_span` / `end_span` for manual instrumentation
- `inject_context` / `extract_context` for cross-service propagation

### Metrics
Custom metrics with OTLP export.
- Counters: Monotonic values (requests, tokens)
- Histograms: Distributions (latency, sizes)

### Logs
Structured logging via OTLP with severity levels.

## MCP Tools

### Deterministic
- `get_capabilities`, `health_check`, `describe_config_schema`
- `get_metric_registry`, `get_exporter_registry`
- `get_metrics_summary`, `inject_context`, `extract_context`, `telemetry_get_views`

### Operational
- `flush_telemetry` - Force flush all providers
- `record_log` - Log entry with severity
- `record_llm_interaction` - LLM token/cost tracking
- `record_agent_execution` - Agent execution events
- `record_tool_invocation` - Tool invocation events
- `start_span`, `end_span` - Manual tracing
- `telemetry_ingest_batch`, `telemetry_read_reference`, `telemetry_materialize` - Durable provenance

### Authoring
- `list_configs`, `read_config`, `write_config`, `delete_config`
- `write_metric_file` - Custom metric definitions
"""

OTEL_DOC = """# OpenTelemetry Configuration

## Exporter Configuration

```yaml
id: otlp
kind: otlp
endpoint: http://localhost:4318
protocol: http/protobuf  # or grpc
headers:
  Authorization: Bearer token
timeout_seconds: 10
```

## Signals
- Traces: `{endpoint}/v1/traces`
- Metrics: `{endpoint}/v1/metrics`
- Logs: `{endpoint}/v1/logs`

## Environment Variables
```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=my-service
OTEL_SERVICE_VERSION=1.0.0
```

## Backends
- Jaeger, Zipkin (traces)
- Prometheus (metrics)
- Grafana Loki (logs)
- AWS X-Ray, Datadog, New Relic (all-in-one)
"""

METRICS_DOC = """# Custom Metrics

## Metric Definition

```yaml
id: llm_tokens
type: counter
name: llm.tokens.total
description: Total LLM tokens processed
unit: tokens
allowed_attributes:
  - model
  - agent_id
```

## Built-in Metrics
- `llm.tokens.input` - Input tokens per model
- `llm.tokens.output` - Output tokens per model
- `llm.cost.usd` - Estimated cost in USD
- `agent.executions` - Agent execution count
- `tool.invocations` - Tool invocation count

## Recording
```python
record_llm_interaction(
    model="claude-3",
    input_tokens=100,
    output_tokens=500,
    latency_ms=1200,
    cost_usd=0.01
)
```
"""

TRACING_DOC = """# Distributed Tracing

## Manual Spans
```python
# Start span
result = start_span(name="process_request", attributes={"user_id": "123"})
span_id = result["span_id"]

# ... do work ...

# End span
end_span(span_id=span_id)
```

## Context Propagation
```python
# Inject into outgoing request
headers = inject_context()
# headers = {"traceparent": "00-...", "tracestate": "..."}

# Extract from incoming request
extract_context(carrier=request.headers)
```

## W3C TraceContext
- `traceparent`: version-trace_id-span_id-flags
- `tracestate`: vendor-specific key-value pairs
"""

WHEN_TO_USE_DOC = """# Telemetry vs Logger — When to Use Which

## Use telemetry when you need:
- Distributed tracing across services (W3C TraceContext)
- OTLP export to Jaeger, Prometheus, Grafana, Datadog, etc.
- Custom metrics (counters, histograms) for dashboards
- LLM token/cost tracking across models
- Agent execution and tool invocation metrics
- Cross-service context propagation

## Use logger when you need:
- Structured log messages with search/tail
- Local log files for debugging
- Error investigation with source/run_id filtering
- Human-readable or JSON-formatted log output

## They complement each other:
- telemetry = metrics + traces + OTLP export (observability)
- logger = structured log records + search + tail (debugging)
- Both support run_id correlation
- logger's future `otel` sink will forward logs to telemetry's OTLP pipeline

## Related brick: logger (factory.logger)
"""

DOCS = {
    "overview": OVERVIEW_DOC,
    "otel": OTEL_DOC,
    "metrics": METRICS_DOC,
    "tracing": TRACING_DOC,
    "when_to_use": WHEN_TO_USE_DOC,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
