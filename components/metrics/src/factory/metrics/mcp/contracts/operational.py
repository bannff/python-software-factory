"""Strict concrete DTOs for Metrics operational tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel): model_config = ConfigDict(extra="forbid", strict=True)
class RecordInput(_Strict):
    metric_id: str
    value: float
    labels: dict[str, str] | None = None
class RecordItem(RecordInput): timestamp: float | None = None
class RecordBatchInput(_Strict): records: list[RecordItem]
class AggregationInput(_Strict):
    metric_id: str
    method: str = "mean"
    period: str = "24h"
class DriftInput(_Strict):
    metric_id: str
    baseline_period: str = "7d"
    current_period: str = "24h"
    threshold: float = 0.1
class SeedDefaultsInput(_Strict): pass
class SeedSampleDataInput(_Strict):
    hours: int = 48
    points_per_metric: int = 24

class RecordOutput(_Strict):
    ok: bool
    metric_id: str
    value: float
    timestamp: float
class RecordBatchOutput(_Strict):
    ok: bool
    recorded: int
class AggregationOutput(_Strict):
    ok: bool
    metric_id: str
    method: str
    value: float | None = None
    points: int
class DriftOutput(_Strict):
    metric_id: str
    drifted: bool
    drift_score: float | None = None
    baseline_mean: float | None = None
    current_mean: float | None = None
    regression_signal: str | None = None
    baseline_tag: str | None = None
    comparisons: dict[str, dict[str, float | str]] | None = None
    reason: str | None = None
class SeedDefaultsOutput(_Strict):
    ok: bool
    created: list[str]
    skipped: list[str]
    total: int
class SeedSampleDataOutput(_Strict):
    ok: bool
    metrics_seeded: int | None = None
    points_per_metric: int | None = None
    total_points: int | None = None
    error: str | None = None
