"""Contracts for Agent execution and asynchronous workflow MCP tools."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .discovery import StrictDTO


class CancelWorkflowInput(StrictDTO):
    workflow_id: str


class CancelWorkflowOutput(StrictDTO):
    success: bool
    workflow_id: str


class InvokeSwarmInput(StrictDTO):
    swarm_id: str
    task: str
    context: dict[str, Any] | None = None


class InvokeGraphInput(StrictDTO):
    graph_id: str
    task: str
    context: dict[str, Any] | None = None


class ReasonInput(StrictDTO):
    task: str
    context: dict[str, Any] | None = None
    agent_id: str | None = None


class ExecutionOutput(StrictDTO):
    result: dict[str, Any]


class AsyncLaunchOutput(StrictDTO):
    success: bool
    workflow_id: str
    status: str
    error: str | None = None
    validation_errors: list[str] | None = None


class LaunchSwarmInput(StrictDTO):
    prompt: str
    agents: list[dict[str, Any]]
    model: str = "us.amazon.nova-lite-v1:0"
    max_handoffs: int = 20
    max_iterations: int = 20
    execution_timeout: float = 900.0
    node_timeout: float = 300.0


class LaunchSwarmOutput(StrictDTO):
    success: bool
    result: dict[str, Any]


class ExecuteLangGraphAttemptInput(StrictDTO):
    request: dict[str, Any]
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_run_id: str = Field(min_length=1, max_length=512)
    attempt_id: str = Field(min_length=1, max_length=512)
    revision: int = Field(ge=1)
    engine_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    registration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecuteLangGraphAttemptOutput(StrictDTO):
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str
    provider_request_digest: str
    manifest_digest: str
    execution_mode: Literal["managed"]
    status: Literal["completed", "failed"]
    result: dict[str, Any]
    error: str | None = None
    retryable: bool = False


class CancelLangGraphAttemptInput(StrictDTO):
    workflow_run_id: str = Field(min_length=1, max_length=512)
    attempt_id: str = Field(min_length=1, max_length=512)
    revision: int = Field(ge=1)
    engine_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    registration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CancelLangGraphAttemptOutput(StrictDTO):
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str
    provider_request_digest: str
    manifest_digest: str
    outcome: Literal[
        "cancel_requested", "already_requested", "not_owner", "not_found",
    ]
