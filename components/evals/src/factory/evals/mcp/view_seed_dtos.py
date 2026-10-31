"""Concrete DTOs for the Evals view and default-seed MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ViewSeedEmptyInput(_StrictDTO):
    pass


class ViewRunIdInput(_StrictDTO):
    run_id: str


class ViewFilenameInput(_StrictDTO):
    filename: str = ""


class DashboardOverviewOutput(_StrictDTO):
    runs: int
    experiments: int
    saved_configs: int
    failing_runs: int
    regressions: int
    avg_pass_rate: float


class DashboardSeriesOutput(_StrictDTO):
    label: str
    value: float
    avg_score: float
    timestamp: str


class DashboardExperimentOutput(_StrictDTO):
    experiment_name: str
    runs: int
    latest_verdict: str
    latest_pass_rate: float
    avg_pass_rate: float
    latest_avg_score: float
    latest_timestamp: str
    latest_status: str
    latest_run_id: str
    latest_failed_cases: int
    evaluators_used: list[str]
    agent: dict[str, Any]
    trend_direction: str
    pass_rate_delta: float
    regression_state: str
    recent_pass_rates: list[float]
    saved_filename: str
    saved_cases: int
    saved_path: str
    config_status: str


class DashboardSummaryOutput(_StrictDTO):
    overview: DashboardOverviewOutput
    series: list[DashboardSeriesOutput]
    experiments: list[DashboardExperimentOutput]


class RunRegressionOutput(_StrictDTO):
    regressed: bool
    regression_state: str
    pass_rate_delta: float
    avg_score_delta: float
    previous_run_id: str | None = None


class ExperimentConfigCaseOutput(_StrictDTO):
    id: str
    name: str
    input: dict[str, Any]
    expected: Any = None


class ExperimentConfigCasesOutput(_StrictDTO):
    cases: list[ExperimentConfigCaseOutput] = Field(default_factory=list)
    case_count: int = 0
    status: str
    message: str | None = None


class FailureClusterOutput(_StrictDTO):
    name: str
    status: str
    failures: int
    runs: list[str]
    latest_reason: str
    avg_score: float
    examples: list[str]
    reason: str
    input_snippet: str


class FailureClustersOutput(_StrictDTO):
    experiment_name: str
    clusters: list[FailureClusterOutput]
    count: int


class UIViewOutput(_StrictDTO):
    id: str
    name: str
    brick: str
    icon: str
    layout: dict[str, str]
    components: list[dict[str, Any]]
    metadata: dict[str, str | int]


class ViewsOutput(_StrictDTO):
    views: list[UIViewOutput]


class SeedDefaultsOutput(_StrictDTO):
    created: list[str]
    skipped: list[str]
    total: int
