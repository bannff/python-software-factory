"""Ingress and egress DTOs for immutable Evals record tools."""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, StrictInt, model_serializer

from factory.mcp_utils.interface import JsonArray, JsonObject


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RecordRunInput(_Input):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    attempt_id: str = ""
    experiment_name: str
    verdict: str
    pass_rate: float
    avg_score: float
    total_cases: int
    passed: int
    case_results: JsonArray | None = None
    evaluators_used: JsonArray | None = None
    agent: JsonObject | None = None
    timestamp: str = ""
    source: str = "experiment"
    failed_cases: int | None = None
    duration_ms: float = 0.0
    case_scores: JsonArray | None = None
    summary: JsonObject | None = None
    artifacts: JsonObject | None = None
    record_kind: str = "evaluation_run"
    terminal_state: str = "completed"
    score_projection: JsonObject | None = None


    policy_ref: JsonObject | None = None
    reviewer_tool_scope: JsonArray | None = None
    rubric_digest: str | None = None
class _DomainVersionedInput(_Input):
    preserve_domain_schema_version: ClassVar[bool] = True


class VerifyRecordPointerInput(_DomainVersionedInput):
    model_config = ConfigDict(extra="forbid")
    collection: str
    doc_id: str
    record_kind: str
    schema_version: StrictInt = 2
    revision: str
    content_hash: str


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_serializer(mode="wrap")
    def _omit_none(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}


class RecordRunOutput(_Output):
    persisted: bool
    status: str = ""
    doc_id: str = ""
    run_id: str
    content_hash: str = ""
    existing_content_hash: str = ""
    timestamp: str = ""
    reason: str | None = None
    pointer: dict[str, Any] | None = None
    projection_key: str | None = None


class VerifyRecordPointerOutput(_Output):
    verified: bool
    pointer: dict[str, Any]
    reason: str | None = None
    run_id: str | None = None
    summary: dict[str, Any] | None = None
    case_results: list[dict[str, Any]] | None = None
    case_scores: list[float] | None = None
    verdict: str | None = None
    pass_rate: float | None = None
    avg_score: float | None = None
    total_cases: int | None = None
    policy_ref: dict[str, Any] | None = None
    reviewer_tool_scope: list[str] | None = None
    rubric_digest: str | None = None
    passed_cases: int | None = None
    failed_cases: int | None = None
    evaluators_used: list[str] | None = None
    artifact_refs: list[str] | None = None
    artifacts: dict[str, Any] | None = None
    edge_model_evidence: dict[str, Any] | None = None
