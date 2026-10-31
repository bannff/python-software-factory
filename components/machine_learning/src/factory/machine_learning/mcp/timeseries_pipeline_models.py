"""Typed Pydantic v2 boundaries for time-series and CAN pipeline MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.can_model_configs import CanModelConfigs
from ..runtime.time_series_ports import TimeSeriesModelConfig


class _BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(*args, by_alias=True, **kwargs)


class TrainTimeSeriesInput(_BoundaryModel):
    model_type: str
    X_uri: str
    y_uri: str
    experiment_name: str = ""
    config: dict[str, Any] | None = None
    model_config_: TimeSeriesModelConfig | None = Field(default=None, alias="model_config")


class TrainTimeSeriesOutput(_BoundaryModel):
    job_id: str
    model_type: str
    status: str
    experiment_id: str | None = None
    run_id: str | None = None
    metrics: dict[str, Any]
    model_path: str | None = None


class PredictTimeSeriesInput(_BoundaryModel):
    model_id: str
    X_uri: str


class PredictTimeSeriesOutput(_BoundaryModel):
    model_id: str
    predictions_uri: str


class CompareTimeSeriesInput(_BoundaryModel):
    model_ids: list[str]
    metric: str = "auroc"


class CompareTimeSeriesOutput(_BoundaryModel):
    metric: str
    models: list[dict[str, Any]]
    best_model_id: str | None = None
    count: int


class ListTimeSeriesModelsInput(_BoundaryModel):
    pass


class ListTimeSeriesModelsOutput(_BoundaryModel):
    models: list[dict[str, Any]]
    count: int


class SampleTimeSeriesInput(_BoundaryModel):
    model_id: str
    n_samples: int = 1000
    seed: int = 42


class SampleTimeSeriesOutput(_BoundaryModel):
    model_id: str
    samples_uri: str
    n_samples: int
    seed: int


class ContinueTimeSeriesInput(_BoundaryModel):
    model_id: str
    X_uri: str
    experiment_name: str = ""
    config: dict[str, Any] | None = None
    classifier_feedback: dict[str, float] | None = None


class ContinueTimeSeriesOutput(_BoundaryModel):
    job_id: str
    parent_model_id: str
    model_type: str
    status: str
    metrics: dict[str, Any]
    model_path: str | None = None


class CanPipelineInput(_BoundaryModel):
    mf4_dir: str
    dbc_path: str
    vehicle_id: str = "unknown"
    storage_root: str | None = None
    max_samples: int = 20_000
    top_n_can_ids: int = 5
    config_overrides: dict[str, Any] | None = None
    use_context: bool = False
    context_sources: list[str] | None = None
    model_types: list[str] | None = None
    model_configs: CanModelConfigs | None = None


class CanPipelineOutput(_BoundaryModel):
    vehicle_id: str
    ingest: dict[str, Any]
    profile: dict[str, Any]
    contract_artifacts: dict[str, dict[str, Any]]
    synthesize: dict[str, Any]
    window: dict[str, Any]
    augment: dict[str, Any]
    top_can_ids: list[int | str]
    comparison_table: list[dict[str, Any]]
    model_ids: list[str]
    warm_model_ids: list[str]
    inference_gate: dict[str, Any]
    context: dict[str, Any] | None = None
    context_artifacts: dict[str, Any] | None = None


__all__ = [name for name in globals() if name.endswith(("Input", "Output"))]
