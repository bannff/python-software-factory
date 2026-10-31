"""Strict public DTOs for Metrics deterministic tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_Strict): pass
class MetricIdInput(_Strict): metric_id: str
class SnapshotInput(MetricIdInput): period: str = "24h"
class TrendInput(MetricIdInput):
    window: str = "7d"
    granularity: str = "1d"
class AllSnapshotsInput(_Strict): period: str = "24h"
class TaxonomyInput(_Strict):
    domain: str | None = None
    category: str | None = None
    source_brick: str | None = None
    input_tool: str | None = None
    tags: list[str] | None = None
class CompareBaselineInput(MetricIdInput):
    current_values: dict[str, float]
    baseline_tag: str
    threshold_block: float = 0.05
    threshold_warn: float = 0.02
class ListBaselinesInput(_Strict): metric_id: str | None = None
class PrecisionInput(_Strict):
    reviewed: int
    true_positives: int
    prior_a: float = 1.0
    prior_b: float = 1.0
    target_precision: float = 0.10
class SampleSizeInput(_Strict):
    estimated_precision: float = 0.0196
    confidence: float = 0.95
    min_true_positives: int = 1
class IterationEfficiencyInput(_Strict):
    initial_ratio: float = 50.0
    budget: int = 5000
    sample_size: int = 200
    improvement_rate: float = 0.95


class MetricDefinitionDTO(_Strict):
    """Public wire representation of a metric definition."""
    id: str
    name: str
    description: str = ""
    metric_type: str = "gauge"
    unit: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    composite_formula: str | None = None
    domain: str = "general"
    category: str = "uncategorized"
    source_brick: str | None = None
    input_tool: str | None = None
    format: str = "number"
    bounds: tuple[float, float] | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)


class SnapshotDTO(_Strict):
    metric_id: str
    current_value: float
    previous_value: float | None = None
    trend: str = "stable"
    change_pct: float | None = None
    period: str = "24h"
    data_points: int = 0


class CapabilitiesOutput(_Strict):
    name: str
    version: str
    features: list[str]
    tools: dict[str, list[str]]
class HealthStoreOutput(_Strict):
    ok: bool
    backend: str | None = None
class HealthOutput(_Strict):
    ok: bool
    store: HealthStoreOutput
    definitions: int
class ConfigSchemaOutput(_Strict): schemas: dict[str, JsonValue]
class RegistryOutput(_Strict): definitions: list[MetricDefinitionDTO]
class DefinitionOutput(_Strict):
    ok: bool
    definition: MetricDefinitionDTO | None = None
    error: str | None = None
class SnapshotOutput(SnapshotDTO): pass
class TrendInfoOutput(_Strict):
    direction: str
    slope: float | None = None
class TrendBucketOutput(_Strict):
    start: float
    end: float
    value: float | None = None
    count: int
class TrendOutput(_Strict):
    metric_id: str
    window: str
    granularity: str
    trend: TrendInfoOutput
    buckets: list[TrendBucketOutput]
    total_points: int
class SnapshotEntryOutput(MetricDefinitionDTO): snapshot: SnapshotDTO
class AllSnapshotsOutput(_Strict): snapshots: list[SnapshotEntryOutput]
class TaxonomyOutput(_Strict):
    ok: bool
    count: int
    definitions: list[MetricDefinitionDTO]
class BaselineComparisonOutput(_Strict):
    ok: bool
    metric_id: str | None = None
    baseline_tag: str | None = None
    overall_signal: str | None = None
    comparisons: dict[str, JsonValue] = Field(default_factory=dict)
    error: str | None = None
class BaselineOutput(_Strict):
    metric_id: str
    tag: str
    values: dict[str, float]
    created_at: str
class BaselinesOutput(_Strict): baselines: list[BaselineOutput]
class PrecisionOutput(_Strict):
    posterior_mean: float
    credible_interval: list[float]
    probability_target: float
    reviewed: int
    true_positives: int
class SampleSizeOutput(_Strict):
    required_reviews: int
    expected_true_positives: int
    estimated_precision: float
    confidence: float
class IterationEfficiencyOutput(_Strict):
    initial_ratio: float
    final_ratio: float
    reviews_saved: float
    iterations: int
class ViewOutput(_Strict):
    id: str
    name: str
    brick: str
    icon: str
    layout: dict[str, JsonValue]
    components: list[dict[str, JsonValue]]
    metadata: dict[str, JsonValue]
class ViewsOutput(_Strict): views: list[ViewOutput]
