"""Pydantic models for the metrics brick."""

from __future__ import annotations

from pydantic import BaseModel, Field

from factory.metrics.core import MetricType


class MetricDefinition(BaseModel):
    """A named metric with type, dimensions, and computation rules."""

    id: str
    name: str
    description: str = ""
    metric_type: MetricType = MetricType.GAUGE
    unit: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    composite_formula: str | None = None

    # Taxonomy — where does this metric live?
    domain: str = "general"
    category: str = "uncategorized"
    source_brick: str | None = None
    input_tool: str | None = Field(
        default=None,
        description="MCP tool name that yields the raw value for this metric.",
    )

    # Semantic metadata — what do the numbers mean?
    format: str = "number"
    bounds: tuple[float, float] | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)


class DataPointModel(BaseModel):
    """Pydantic representation of a recorded data point."""

    metric_id: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: float


class Snapshot(BaseModel):
    """Current state of a metric with trend indicator."""

    metric_id: str
    current_value: float
    previous_value: float | None = None
    trend: str = "stable"  # up, down, stable
    change_pct: float | None = None
    period: str = "24h"
    data_points: int = 0


class Baseline(BaseModel):
    """A named baseline snapshot for regression gating."""

    metric_id: str
    tag: str  # e.g. "v1.0"
    values: dict[str, float]
    created_at: str  # ISO 8601
