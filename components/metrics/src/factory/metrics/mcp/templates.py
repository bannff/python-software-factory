"""Prompt templates for metrics MCP prompts."""

from __future__ import annotations

DEFINE_METRIC_TEMPLATE = """# Define a New Metric

## Metric: {metric_id}
Type: {metric_type}

## Steps

1. **Create Definition**
   ```
   metrics_define_metric(definition={{
       "id": "{metric_id}",
       "name": "{name}",
       "description": "{description}",
       "metric_type": "{metric_type}",
       "unit": "{unit}",
       "dimensions": {dimensions},
       "tags": {tags}
   }})
   ```

2. **Verify Registration**
   ```
   metrics_get_registry()
   ```

3. **Record Initial Data**
   ```
   metrics_record(metric_id="{metric_id}", value=0.0)
   ```

## Metric Types
- `counter`: Monotonic increasing (requests, errors)
- `gauge`: Point-in-time value (CPU, queue depth)
- `histogram`: Distribution (latency, sizes)
- `composite`: Derived from formula
"""

ANALYZE_TREND_TEMPLATE = """# Analyze Metric Trend

## Metric: {metric_id}
Window: {window} | Granularity: {granularity}

## Steps

1. **Get Current Snapshot**
   ```
   metrics_get_snapshot(metric_id="{metric_id}", period="{window}")
   ```

2. **Get Trend Data**
   ```
   metrics_get_trend(
       metric_id="{metric_id}",
       window="{window}",
       granularity="{granularity}"
   )
   ```

3. **Check for Drift**
   ```
   metrics_detect_drift(
       metric_id="{metric_id}",
       baseline_period="{window}",
       current_period="24h"
   )
   ```

## Interpreting Results
- **slope > 0**: Metric is increasing over time
- **slope < 0**: Metric is decreasing over time
- **drifted: true**: Significant change from baseline detected
"""

CONFIGURE_DASHBOARD_TEMPLATE = """# Configure Metrics Dashboard

## Dashboard Focus: {focus}

## Steps

1. **Review Available Metrics**
   ```
   metrics_get_registry()
   ```

2. **Check Key Snapshots**
   ```
   metrics_get_snapshot(metric_id="<metric>", period="24h")
   ```

3. **Set Up Trend Monitoring**
   ```
   metrics_get_trend(metric_id="<metric>", window="7d", granularity="1d")
   ```

4. **Configure Drift Alerts**
   ```
   metrics_detect_drift(
       metric_id="<metric>",
       baseline_period="7d",
       current_period="24h",
       threshold=0.1
   )
   ```

## Recommended Metrics for {focus}
{recommendations}
"""


def get_define_metric_prompt(
    metric_id: str = "custom_metric",
    metric_type: str = "gauge",
    name: str = "Custom Metric",
) -> str:
    """Generate metric definition prompt."""
    return DEFINE_METRIC_TEMPLATE.format(
        metric_id=metric_id, metric_type=metric_type, name=name,
        description="Custom metric description", unit="1",
        dimensions='["service", "environment"]',
        tags='["custom"]',
    )


def get_analyze_trend_prompt(
    metric_id: str = "custom_metric",
    window: str = "7d",
    granularity: str = "1d",
) -> str:
    """Generate trend analysis prompt."""
    return ANALYZE_TREND_TEMPLATE.format(
        metric_id=metric_id, window=window, granularity=granularity,
    )


def get_configure_dashboard_prompt(focus: str = "portfolio") -> str:
    """Generate dashboard configuration prompt."""
    recs = {
        "portfolio": "- coverage_score\n- risk_score\n- finding_count",
        "risk": "- risk_score\n- vulnerability_count\n- exposure_window",
        "performance": "- response_time\n- throughput\n- error_rate",
    }.get(focus, "- Review metrics_get_registry() for available metrics")
    return CONFIGURE_DASHBOARD_TEMPLATE.format(
        focus=focus, recommendations=recs,
    )
