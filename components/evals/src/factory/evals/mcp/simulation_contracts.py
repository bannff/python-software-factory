"""Typed ingress and egress DTOs for simulation and tool-chaos MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersistenceOutput(_Output):
    requested: bool
    persisted: bool
    reason: str | None = None
    status: str | None = None
    doc_id: str | None = None
    run_id: str | None = None
    content_hash: str | None = None
    existing_content_hash: str | None = None
    timestamp: str | None = None
    pointer: dict[str, Any] | None = None
    projection_key: str | None = None


class SimulationInput(_Input):
    cases: list[dict[str, Any]]
    evaluator_names: list[str] | None = None
    rubric: str = ""
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    system_prompt: str = "You are a helpful assistant."
    temperature: float = 0.1
    max_turns: int = 10
    experiment_name: str = "simulation"
    agent_id: str | None = None
    persist: bool = False
    run_id: str | None = None
    persist_only: bool = False
    record_run_request: dict[str, Any] | None = None


class SimulationOutput(_Output):
    run_id: str
    name: str | None = None
    case_results: list[dict[str, Any]] | None = None
    summary: dict[str, Any] | None = None
    evaluators_used: list[str] | None = None
    target: dict[str, Any] | None = None
    record_run_request: dict[str, Any] | None = None
    persistence: PersistenceOutput | None = None


class ToolChaosInput(_Input):
    cases: list[dict[str, Any]]
    tool_names: list[str]
    faults: list[dict[str, Any]]
    evaluator_names: list[str] | None = None
    rubric: str = ""
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    system_prompt: str = "You are a helpful assistant."
    agent_id: str | None = None
    experiment_name: str = "tool-chaos"
    run_id: str | None = None
    persist_only: bool = False
    record_run_request: dict[str, Any] | None = None


class ToolChaosOutput(_Output):
    run_id: str
    case_results: list[dict[str, Any]] | None = None
    summary: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    record_run_request: dict[str, Any] | None = None
    persistence: PersistenceOutput | None = None
