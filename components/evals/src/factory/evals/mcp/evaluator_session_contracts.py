"""Strict DTOs for the Evals evaluator, session, and CAN tool family."""
from __future__ import annotations

from typing import Any, Literal

from factory.mcp_utils.interface import JsonArray
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvalOptions(_Input):
    """Typed rail options for trajectory-match evaluators (agentevals).

    Members are pinned to the agentevals ``create_trajectory_match_evaluator``
    accepted vocabulary so a typo is rejected at the MCP edge instead of
    silently defaulting. Providers that take no options ignore this.
    """

    match_mode: Literal["strict", "unordered", "subset", "superset"] = "strict"
    tool_args_mode: Literal["exact", "ignore", "subset", "superset"] = "exact"


class EvaluateInput(_Input):
    input_text: str
    output_text: str
    evaluator_name: str = "non_empty"
    rubric: str = ""
    expected_output: str | None = None
    framework: str = "deterministic"


class EvaluateMultiInput(_Input):
    input_text: str
    output_text: str
    evaluator_names: list[str]
    rubric: str = ""
    expected_output: str | None = None
    framework: str = "deterministic"
    actual_trajectory: JsonArray | None = None
    expected_trajectory: JsonArray | None = None
    options: EvalOptions | None = None


class ComputationalInput(_Input):
    evaluator_name: str
    y_true: list[Any]
    y_pred: list[Any]
    scores: list[Any]


class CanModelInput(_Input):
    y_true: list[Any]
    y_pred: list[Any]
    y_score: list[Any] | None = None


class EvaluateSessionInput(_Input):
    input_text: str
    output_text: str
    evaluator_names: list[str]
    session_data: dict[str, Any] | None = None
    otel_spans_json: list[str] | None = None
    session: Any | None = None
    rubric: str = ""
    expected_output: str | None = None
    actual_interactions: list[dict[str, Any]] | None = None


class EvaluationRowOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluator: str
    score: FiniteFloat = Field(ge=0.0, le=1.0)
    test_pass: bool
    reason: str
    label: str = ""
    detailed_results: list[Any] = Field(default_factory=list)


class EvaluationSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avg_score: FiniteFloat = Field(ge=0.0, le=1.0)
    pass_rate: FiniteFloat = Field(ge=0.0, le=1.0)
    total_evaluators: int
    error_count: int
    aggregation_policy: str


class EvaluateOutput(EvaluationRowOutput):
    model_config = ConfigDict(extra="forbid")


class EvaluateMultiOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[EvaluationRowOutput]
    summary: EvaluationSummaryOutput


class ComputationalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluator: str
    score: FiniteFloat = Field(ge=0.0, le=1.0)


class CanMetricsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accuracy: FiniteFloat = Field(ge=0.0, le=1.0)
    precision: FiniteFloat = Field(ge=0.0, le=1.0)
    recall: FiniteFloat = Field(ge=0.0, le=1.0)
    f1: FiniteFloat = Field(ge=0.0, le=1.0)
    auroc: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
    auprc: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
    brier: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
    lead_time: FiniteFloat | None = Field(default=None, ge=0.0)
    false_alarm: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
    episode_recall: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)


class CanModelEvidenceOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", serialize_by_alias=True, validate_by_name=True,
    )
    schema_: str = Field(alias="schema")
    version: str
    evaluator_identity: str
    input_digest: str
    metrics: CanMetricsOutput
