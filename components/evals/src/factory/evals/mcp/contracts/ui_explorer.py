"""Ingress and egress DTOs for Evals UI Explorer tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class UIExplorerCapabilitiesInput(_StrictModel):
    pass


class CreateUIScenarioInput(_StrictModel):
    name: str
    route: str
    description: str = ""
    tags: list[str] | None = None


class ListUIScenariosInput(_StrictModel):
    pass


class UIScenarioIdInput(_StrictModel):
    scenario_id: str


class UIExplorationRunIdInput(_StrictModel):
    run_id: str


class AddScenarioActionInput(_StrictModel):
    scenario_id: str
    action_type: str
    target: str | None = None
    value: str | None = None
    timeout_ms: int = 5000


class AddScenarioAssertionInput(_StrictModel):
    scenario_id: str
    assertion_type: str
    max_errors: int = 0
    ignore_patterns: list[str] | None = None
    allowed_failures: list[str] | None = None
    required_landmarks: list[str] | None = None
    lcp_ms: int = 2500
    fid_ms: int = 100
    cls: float = 0.1


class RunUIExplorationInput(_StrictModel):
    scenario_id: str
    context: dict[str, Any]


class UIExplorerCapabilitiesOutput(_StrictModel):
    name: str
    description: str
    actions: list[str]
    assertions: list[str]
    reporters: list[str]
    requires: str


class CreateUIScenarioOutput(_StrictModel):
    id: str
    name: str
    route: str
    message: str


class UIScenarioOutput(_StrictModel):
    id: str
    name: str
    route: str
    description: str
    actions: list[dict[str, Any]]
    assertions: list[dict[str, Any]]
    tags: list[str]
    metadata: dict[str, Any]


class ListUIScenariosOutput(_StrictModel):
    scenarios: list[UIScenarioOutput]
    count: int


class AddScenarioActionOutput(_StrictModel):
    scenario_id: str
    action_added: dict[str, Any]


class AddScenarioAssertionOutput(_StrictModel):
    scenario_id: str
    assertion_added: dict[str, Any]


class RunUIExplorationOutput(_StrictModel):
    run_id: str
    status: str
    summary: dict[str, Any]
    findings: list[dict[str, Any]]


class ListUIFindingsOutput(_StrictModel):
    run_id: str
    findings: list[dict[str, Any]]
    count: int
