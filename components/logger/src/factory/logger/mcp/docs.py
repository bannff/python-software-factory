"""Documentation content for logger MCP resources."""

LOGGER_DOCS = {
    "overview": {
        "title": "Logger Brick Overview",
        "content": """# Logger Brick

Structured logging with pluggable sinks and formatters.

## Core Concepts

- **LogRecord**: Framework-agnostic log entry with level, message, context
- **LogSink**: Where logs go (file, CloudWatch, stdout)
- **LogFormatter**: How logs look (JSON, text)
- **LogQuery**: Search and tail logs

## Quick Start

```python
# Log a message
logger.info(message="User logged in", source="auth", run_id="abc123")

# Tail recent logs
logger.tail(lines=20)

# Search logs
logger.search(level="error", source="workflow", limit=50)
```

## MCP Tools

- `logger.info` / `logger.error` / `logger.warning` - Log messages
- `logger.tail` - Get recent log entries
- `logger.search` - Search logs with filters
- `logger.clear` - Clear log file (admin)

## Resources

- `logger://schemas/config` - Configuration schema
- `logger://schemas/record` - LogRecord schema
- `logger://docs/overview` - This document
- `logger://docs/sinks` - Available sinks
""",
    },
    "sinks": {
        "title": "Logger Sinks",
        "content": """# Logger Sinks

Sinks determine where logs are written.

## Available Sinks

### file (default)
Write logs to local files.

```yaml
logger:
  sink: file
  log_dir: ./logs
  filename: factory.log
```

### Future Sinks

- **cloudwatch**: AWS CloudWatch Logs
- **datadog**: Datadog log aggregation
- **otel**: OpenTelemetry collector
- **stdout**: Console output

## Sink Protocol

All sinks implement:
- `write(record)` - Write a log entry
- `flush()` - Flush buffered logs
- `close()` - Release resources
- `health_check()` - Check sink status
""",
    },
    "formatters": {
        "title": "Logger Formatters",
        "content": """# Logger Formatters

Formatters control how logs are serialized.

## Available Formatters

### json (default)
Agent-friendly structured output.

```json
{"timestamp": "2024-01-15T10:30:00", "level": "info", "message": "...", "source": "auth"}
```

### text
Human-readable output.

```
2024-01-15 10:30:00 - factory - INFO     - User logged in [source=auth]
```

## Formatter Protocol

All formatters implement:
- `format(record) -> str` - Convert LogRecord to string
""",
    },
    "context": {
        "title": "Logging Context",
        "content": """# Logging Context

Add structured context to log entries for better traceability.

## Context Fields

- **source**: Which brick/component (auth, workflow, agent)
- **run_id**: Correlation ID for tracing across operations
- **tenant_id**: Multi-tenant isolation
- **context**: Arbitrary key-value pairs

## Example

```python
logger.info(
    message="Payment processed",
    source="payments",
    run_id="run-abc123",
    tenant_id="tenant-xyz",
    context={"amount": 99.99, "currency": "USD"}
)
```

## Searching by Context

```python
# Find all logs for a specific run
logger.search(run_id="run-abc123")

# Find errors from a specific source
logger.search(level="error", source="workflow")
```
""",
    },
    "when_to_use": {
        "title": "Logger vs Telemetry",
        "content": """# Logger vs Telemetry — When to Use Which

## Use logger when you need:
- Structured log messages with search/tail
- Local log files for debugging
- Error investigation with source/run_id filtering
- Human-readable or JSON-formatted log output

## Use telemetry when you need:
- Distributed tracing across services (W3C TraceContext)
- OTLP export to Jaeger, Prometheus, Grafana, Datadog, etc.
- Custom metrics (counters, histograms) for dashboards
- LLM token/cost tracking across models

## They complement each other:
- logger = structured log records + search + tail (debugging)
- telemetry = metrics + traces + OTLP export (observability)
- Both support run_id correlation
- logger's future `otel` sink will forward logs to telemetry's OTLP pipeline

## Related brick: telemetry (factory.telemetry)
""",
    },
}
