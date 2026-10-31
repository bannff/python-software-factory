"""Ingress and egress DTOs for selected Evals deterministic tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, field_validator

from factory.mcp_utils.interface import is_bounded_json

_MAX_SCORE_EVIDENCE_ITEMS = 256


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_Input):
    model_config = ConfigDict(extra="forbid")
    pass


class SuiteIdInput(_Input):
    model_config = ConfigDict(extra="forbid")
    suite_id: str


class RunIdInput(_Input):
    model_config = ConfigDict(extra="forbid")
    run_id: str


class ListRunsInput(_Input):
    model_config = ConfigDict(extra="forbid")
    suite_id: str | None = None


class ScoreGtInput(_Input):
    model_config = ConfigDict(extra="forbid")
    findings: list[dict[str, Any]]
    gt_entries: list[dict[str, Any]]
    match_on: list[str] | None = None


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilitiesOutput(_Output):
    name: str
    version: str
    backends: list[str]
    features: list[str]
    mcp_resources: list[str]
    mcp_prompts: list[str]


class HealthRunnerOutput(_Output):
    healthy: bool
    backend: str


class HealthOutput(_Output):
    healthy: bool
    runners: dict[str, HealthRunnerOutput]


class ConfigSchemaOutput(_Output):
    type: str
    properties: dict[str, Any]


class SuiteOutput(_Output):
    found: bool
    id: str | None = None
    name: str | None = None
    description: str | None = None
    case_count: int | None = None


class SuitesOutput(_Output):
    suites: list[dict[str, Any]]
    count: int


class RunOutput(_Output):
    found: bool
    id: str | None = None
    suite_id: str | None = None
    status: str | None = None
    summary: dict[str, Any] | None = None
    result_count: int | None = None


class RunsOutput(_Output):
    runs: list[dict[str, Any]]
    count: int


class ScoreGtOutput(_Output):
    precision: FiniteFloat = Field(default=0.0, ge=0.0, le=1.0)
    recall: FiniteFloat = Field(default=0.0, ge=0.0, le=1.0)
    f1: FiniteFloat = Field(default=0.0, ge=0.0, le=1.0)
    true_positives: int = 0
    false_positives_count: int = 0
    false_negatives: int = 0
    matched: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=_MAX_SCORE_EVIDENCE_ITEMS,
    )
    missed: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=_MAX_SCORE_EVIDENCE_ITEMS,
    )
    false_positives: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=_MAX_SCORE_EVIDENCE_ITEMS,
    )

    @field_validator("matched", "missed", "false_positives")
    @classmethod
    def _validate_evidence(cls, value: list[dict[str, JsonValue]]) -> list[dict[str, JsonValue]]:
        if not is_bounded_json(value):
            raise ValueError("score evidence must be bounded JSON")
        return value
