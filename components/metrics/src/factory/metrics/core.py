"""Shared types, constants, and enums for the metrics brick."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MetricType(Enum):
    """Supported metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    COMPOSITE = "composite"


class MetricFormat(str, Enum):
    """Display format for metric values."""
    NUMBER = "number"
    PERCENT = "percent"
    DURATION = "duration"
    SCORE = "score"


@dataclass
class DataPoint:
    """A single metric data point — framework-agnostic representation."""
    metric_id: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(
        default_factory=lambda: datetime.now(timezone.utc).timestamp()
    )


# Version and feature constants
VERSION = "0.1.0"
BRICK_NAME = "metrics"

FEATURES = [
    "metric_definitions",
    "time_series_recording",
    "aggregation_snapshots",
    "drift_detection",
    "trend_analysis",
    "portfolio_coverage",
    "risk_scoring",
    "taxonomy",
    "regression_gating",
    "bayesian_estimation",
]

TOOL_CATEGORIES: dict[str, list[str]] = {
    "deterministic": [
        "metrics_get_capabilities",
        "metrics_health_check",
        "metrics_describe_config_schema",
        "metrics_get_registry",
        "metrics_get_definition",
        "metrics_get_snapshot",
        "metrics_get_trend",
        "metrics_get_all_snapshots",
        "metrics_get_views",
        "metrics_get_by_taxonomy",
        "metrics_compare_baseline",
        "metrics_list_baselines",
        "metrics_precision_estimate",
        "metrics_sample_size",
        "metrics_iteration_efficiency",
        "metrics_measure",
    ],
    "operational": [
        "metrics_record",
        "metrics_record_batch",
        "metrics_compute_aggregation",
        "metrics_detect_drift",
        "metrics_seed_defaults",
        "metrics_seed_sample_data",
    ],
    "authoring": [
        "metrics_authoring_status",
        "metrics_define_metric",
        "metrics_update_definition",
        "metrics_delete_definition",
        "metrics_set_baseline",
    ],
}


def parse_duration(duration: str) -> float:
    """Parse a duration string (e.g. '24h', '7d', '30m') to seconds."""
    units: dict[str, float] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    suffix = duration[-1]
    if suffix not in units:
        raise ValueError(f"Unknown duration unit: {suffix}")
    return float(duration[:-1]) * units[suffix]
