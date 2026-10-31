"""Ingress and egress DTOs for selected Evals operational tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateSuiteInput(_Input):
    model_config = ConfigDict(extra="forbid")
    suite_id: str
    name: str
    description: str = ""
    cases: list[dict[str, Any]] | None = None


class DeleteSuiteInput(_Input):
    model_config = ConfigDict(extra="forbid")
    suite_id: str


class AddCaseInput(_Input):
    model_config = ConfigDict(extra="forbid")
    suite_id: str
    case_id: str
    name: str
    input_data: dict[str, Any]
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class PersistScoreInput(_Input):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    workflow_type: str
    target_app: str
    vuln_class: str
    scoring: dict[str, Any]
    domain_class: str = ""
    source: str = "experiment"


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSuiteOutput(_Output):
    id: str
    name: str
    case_count: int


class DeleteSuiteOutput(_Output):
    deleted: bool
    error: str
    suite_id: str | None = None


class AddCaseOutput(_Output):
    added: bool
    suite_id: str | None = None
    case_id: str | None = None
    total_cases: int | None = None
    error: str | None = None


class PersistScoreOutput(_Output):
    persisted: bool
    doc_id: str = ""
    reason: str | None = None
