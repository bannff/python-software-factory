"""Seed tool for default portfolio metric definitions."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.operational import (
    SeedDefaultsInput, SeedDefaultsOutput, SeedSampleDataInput, SeedSampleDataOutput,
)

from ..core import MetricType
from ..runtime.models import MetricDefinition

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime

_DEFAULT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "platform-coverage-score", "name": "Coverage Score",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "coverage", "source_brick": "graph",
        "input_tool": "graph_query",
        "format": "percent", "bounds": (0, 100),
        "thresholds": {"warning": 70, "critical": 50},
        "tags": ["platform", "coverage"],
    },
    {
        "id": "platform-risk-score-avg", "name": "Risk Score Average",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "risk", "source_brick": "graph",
        "input_tool": "graph_get_stats",
        "format": "score", "bounds": (0, 100),
        "thresholds": {"warning": 70, "critical": 50},
        "tags": ["platform", "risk"],
    },
    {
        "id": "platform-finding-count", "name": "Finding Count",
        "metric_type": MetricType.COUNTER, "domain": "platform",
        "category": "risk", "source_brick": "graph",
        "input_tool": "graph_get_recent_findings",
        "format": "number", "tags": ["platform", "risk"],
    },
    {
        "id": "platform-mttr", "name": "Mean Time to Remediate",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "performance", "source_brick": "graph",
        "input_tool": "graph_get_findings_for_run",
        "format": "duration", "tags": ["platform", "performance"],
    },
    {
        "id": "platform-drift-rate", "name": "Drift Rate",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "coverage", "source_brick": "metrics",
        "input_tool": "metrics_detect_drift",
        "format": "percent", "bounds": (0, 100),
        "thresholds": {"warning": 70, "critical": 50},
        "tags": ["platform", "coverage"],
    },
    {
        "id": "platform-eval-pass-rate", "name": "Eval Pass Rate",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "quality", "source_brick": "evals",
        "input_tool": "evals_run_suite",
        "format": "percent", "bounds": (0, 100),
        "thresholds": {"warning": 70, "critical": 50},
        "tags": ["platform", "quality"],
    },
    {
        "id": "platform-resource-count", "name": "Resource Count",
        "metric_type": MetricType.GAUGE, "domain": "platform",
        "category": "coverage", "source_brick": "graph",
        "input_tool": "graph_count_entities_by_run",
        "format": "number", "tags": ["platform", "coverage"],
    },
    {
        "id": "platform-portfolio-health", "name": "Portfolio Health",
        "metric_type": MetricType.COMPOSITE, "domain": "platform",
        "category": "risk", "source_brick": "metrics",
        "input_tool": "metrics_compute_aggregation",
        "format": "score", "bounds": (0, 100),
        "thresholds": {"warning": 70, "critical": 50},
        "composite_formula": (
            "avg(platform-coverage-score, platform-risk-score-avg,"
            " platform-eval-pass-rate)"
        ),
        "tags": ["platform", "risk", "composite"],
    },
]


def register(mcp: Any, runtime: "MetricsRuntime") -> None:
    """Register seed tools."""

    @typed_tool(mcp)
    @operational(input_model=SeedDefaultsInput, output_model=SeedDefaultsOutput)
    def metrics_seed_defaults() -> ToolResult[SeedDefaultsOutput]:
        """Seed default portfolio metric definitions (idempotent)."""
        created, skipped = [], []
        for raw in _DEFAULT_DEFINITIONS:
            mid = raw["id"]
            if runtime.get_definition(mid) is not None:
                skipped.append(mid)
                continue
            defn = MetricDefinition(**raw)
            runtime.register_definition(defn)
            created.append(mid)
        return ok(SeedDefaultsOutput(ok=True, created=created, skipped=skipped, total=len(_DEFAULT_DEFINITIONS)))

    @typed_tool(mcp)
    @operational(input_model=SeedSampleDataInput, output_model=SeedSampleDataOutput)
    def metrics_seed_sample_data(
        hours: int = 48, points_per_metric: int = 24,
    ) -> ToolResult[SeedSampleDataOutput]:
        """Seed time-spread sample data points for all registered metrics.

        Generates data points spread evenly across the last `hours` window
        so snapshots and trend charts show meaningful values.
        """
        definitions = runtime.list_definitions()
        if not definitions:
            return ok(SeedSampleDataOutput(ok=False, error="No metrics registered. Run metrics_seed_defaults first."))

        _FORMAT_RANGES: dict[str, tuple[float, float, float]] = {
            # (low, high, trend_range)
            "percent": (60.0, 95.0, 10.0),
            "score": (50.0, 90.0, 8.0),
            "number": (10.0, 500.0, 50.0),
            "duration": (1.0, 72.0, 5.0),
        }
        default_range = (0.0, 100.0, 10.0)

        now = datetime.now(timezone.utc).timestamp()
        span = hours * 3600
        total = 0

        for defn in definitions:
            mid = defn["id"]
            low, high, trend = _FORMAT_RANGES.get(defn.get("format", ""), default_range)
            for i in range(points_per_metric):
                ts = now - span + i * (span / points_per_metric)
                base = random.uniform(low, high)
                value = round(base + (i / points_per_metric) * trend, 2)
                runtime.store.record(mid, value, None, ts)
            total += points_per_metric

        return ok(SeedSampleDataOutput(ok=True, metrics_seeded=len(definitions),
            points_per_metric=points_per_metric, total_points=total))
