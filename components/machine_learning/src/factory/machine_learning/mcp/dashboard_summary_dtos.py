"""Strict Pydantic DTOs for ML training dashboard read tools."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_DTO):
    pass


class RunIdInput(_DTO):
    run_id: str


class TrainingRunsOutput(_DTO):
    runs: list[dict[str, Any]]
    count: int


class TrainingRunOutput(_DTO):
    found: bool
    run: dict[str, Any] | None = None


class RunRegressionOutput(_DTO):
    found: bool
    regressed: bool | None = None
    regression_state: str | None = None
    metric: str | None = None
    metric_delta: float | None = None
    previous_run_id: str | None = None


class DashboardSummaryOutput(_DTO):
    overview: dict[str, Any]
    series: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
