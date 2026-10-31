"""Documentation content for metrics MCP resources."""

from __future__ import annotations

OVERVIEW_DOC = """# Metrics Brick

Portfolio-level metrics, risk scoring, drift detection, and time-series tracking.

## Key Concepts

### Metric Definitions
Named metrics with types (counter, gauge, histogram, composite), dimensions,
and computation rules. Stored as YAML configs via the authoring system.

### Data Points
Time-series values recorded against a metric ID with optional label dimensions.

### Snapshots
Current state of a metric: latest value, trend direction, change percentage.

### Drift Detection
Compares baseline and current periods to detect statistically significant changes.

All 28 public FastMCP tools accept strict, flat Pydantic v2 inputs and return
`ToolResult[OutputDTO]` envelopes. Successful calls carry typed payloads under
`data`; ordinary negative outcomes such as disabled authoring remain
successful envelopes with their outcome in `data`.

### Deterministic
- `metrics_get_capabilities`, `metrics_health_check`, `metrics_describe_config_schema`
- `metrics_get_registry`, `metrics_get_definition`, `metrics_get_all_snapshots`
- `metrics_get_snapshot`, `metrics_get_trend`, `metrics_get_by_taxonomy`
- `metrics_compare_baseline`, `metrics_list_baselines`, `metrics_measure`, `metrics_precision_estimate`
- `metrics_sample_size`, `metrics_iteration_efficiency`, `metrics_get_views`

### Operational
- `metrics_record`, `metrics_record_batch`, `metrics_compute_aggregation`
- `metrics_detect_drift`, `metrics_seed_defaults`, `metrics_seed_sample_data`

### Authoring
- `metrics_authoring_status`
- `metrics_define_metric`, `metrics_update_definition`, `metrics_delete_definition`
- `metrics_set_baseline`
"""

METRIC_TYPES_DOC = """# Metric Types

## Counter
Monotonically increasing value. Use for totals (requests, errors, tokens).
Only increments; resets on restart.

## Gauge
Point-in-time value that can go up or down. Use for current state
(CPU usage, queue depth, active connections).

## Histogram
Distribution of values. Use for latencies, sizes, durations.
Supports percentile queries (p50, p95, p99).

## Composite
Derived from other metrics via a formula. Use for ratios, rates,
and computed KPIs (error_rate = errors / requests).
"""

DOCS = {
    "overview": OVERVIEW_DOC,
    "metric-types": METRIC_TYPES_DOC,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
