"""Ingress and egress DTOs for Evals experiment and serialization tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListEvaluatorsInput(_StrictModel):
    pass


class RunExperimentInput(_StrictModel):
    cases: list[dict[str, Any]]
    evaluator_names: list[str] | None = None
    rubric: str = ""
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    system_prompt: str = "You are a helpful assistant."
    temperature: float = 0.1
    experiment_name: str = "experiment"
    run_id: str | None = None
    persist_only: bool = False
    record_run_request: dict[str, Any] | None = None


class ListRunResultsInput(_StrictModel):
    pass


class GetRunResultInput(_StrictModel):
    run_id: str


class GenerateExperimentInput(_StrictModel):
    context: str
    task_description: str
    num_cases: int = 5
    evaluator_name: str = "output"


class SaveExperimentInput(_StrictModel):
    cases: list[dict[str, Any]]
    evaluator_names: list[str]
    filename: str
    rubric: str = ""
    experiment_name: str = ""


class LoadExperimentInput(_StrictModel):
    filename: str


class ListSavedExperimentsInput(_StrictModel):
    pass


class EvaluatorsOutput(_StrictModel):
    evaluators: list[dict[str, Any]]
    count: int


class PersistenceOutput(_StrictModel):
    persisted: bool
    status: str | None = None
    reason: str | None = None
    doc_id: str | None = None
    run_id: str | None = None
    content_hash: str | None = None
    existing_content_hash: str | None = None
    timestamp: str | None = None
    pointer: dict[str, Any] | None = None
    projection_key: str | None = None


class RunExperimentOutput(_StrictModel):
    run_id: str
    name: str | None = None
    case_results: list[dict[str, Any]] | None = None
    summary: dict[str, Any] | None = None
    evaluators_used: list[str] | None = None
    record_run_request: dict[str, Any]
    persistence: PersistenceOutput


class RunSummaryOutput(_StrictModel):
    run_id: str
    experiment_name: str
    timestamp: str
    completion_status: str
    verdict: str
    source: str
    pass_rate: float
    avg_score: float
    total_cases: int
    passed_cases: int
    failed_cases: int
    duration_ms: float
    evaluators_used: list[Any]
    case_scores: list[Any]
    agent: dict[str, Any]
    previous_run_id: str | None
    pass_rate_delta: float
    avg_score_delta: float
    trend_direction: str
    regression_state: str


class RunResultsOutput(_StrictModel):
    runs: list[RunSummaryOutput]
    count: int
    latest: RunSummaryOutput | None = None


class RunResultOutput(_StrictModel):
    found: bool
    result: dict[str, Any] | None = None


class GeneratedExperimentOutput(_StrictModel):
    name: str
    cases: list[dict[str, Any]]
    evaluator_names: list[str]
    case_count: int


class SaveExperimentOutput(_StrictModel):
    path: str
    cases: int
    evaluators: list[str]


class LoadExperimentOutput(_StrictModel):
    name: str
    cases: list[dict[str, Any]]
    evaluator_names: list[str]
    case_count: int


class SavedExperimentOutput(_StrictModel):
    filename: str
    path: str
    cases: int
    size_bytes: int


class SavedExperimentsOutput(_StrictModel):
    experiments: list[SavedExperimentOutput]
    count: int
