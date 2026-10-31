"""Ingress and egress DTOs for the Evals SOP lifecycle tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SopPlanInput(_Input):
    model_config = ConfigDict(extra="forbid")
    agent_description: str
    agent_tools: list[str] | None = None
    evaluation_goals: str = ""


class SopGenerateDataInput(_Input):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    num_cases: int = 10
    evaluator_name: str = "output"


class SopRunInput(_Input):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    system_prompt: str = ""
    evaluator_names: list[str] | None = None
    rubric: str = ""


class SopSessionIdInput(_Input):
    model_config = ConfigDict(extra="forbid")
    session_id: str


class SopPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    phase: str
    next_phase: str
    plan: dict[str, Any]


class SopGenerateDataOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = None
    phase: str | None = None
    next_phase: str | None = None
    cases: list[dict[str, Any]] | None = None
    case_count: int | None = None
    error: str | None = None


class SopRunOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = None
    phase: str | None = None
    next_phase: str | None = None
    results: dict[str, Any] | None = None
    error: str | None = None


class SopReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = None
    phase: str | None = None
    status: str | None = None
    report: str | None = None
    error: str | None = None


class SopStatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    phase: str
    has_plan: bool
    case_count: int
    has_results: bool
    has_report: bool


class SopListOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessions: list[dict[str, Any]]
    count: int
