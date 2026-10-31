"""DTOs for operational Workflow MCP tools."""
from __future__ import annotations

from pydantic import Field, field_validator

from .base import DTO, JsonObject


class EnvelopeInput(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    timestamp: str | None = None
    attributes: JsonObject = {}


class StartRunInput(DTO):
    workflow_name_or_id: str
    input: JsonObject | None = None
    run_key: str | None = None
    envelope: EnvelopeInput | None = None


class RunIdInput(DTO):
    run_id: str
    envelope: EnvelopeInput | None = None


class CancelRunInput(RunIdInput):
    reason: str | None = None


class ListRunsInput(DTO):
    filter: JsonObject | None = None
    pagination: JsonObject | None = None
    envelope: EnvelopeInput | None = None


class EmitEventInput(RunIdInput):
    event_type: str
    payload: JsonObject | None = None


class ListTasksInput(DTO):
    status: str | None = None
    task_type: str | None = None
    limit: int = 100


class StartRunOutput(DTO):
    run_id: str
    run_key: str | None = None
    status: str


class RunOutput(DTO):
    run_id: str
    run_key: str | None = None
    workflow_id: str
    workflow_version: int
    workflow_version_id: str | None = None
    run_execution_id: str | None = None
    revision: int
    status: str
    current_step_id: str | None = None
    waiting_for_event_type: str | None = None
    last_event_id: int
    started_at: str
    updated_at: str
    input: JsonObject
    result: JsonObject | None = None
    error: str | None = None
    tenant_id: str | None = None
    initiation_envelope: JsonObject


class ListRunsOutput(DTO):
    runs: list[RunOutput]
    next_cursor: str | None = None


class OperationOutput(DTO):
    ok: bool
    status: str | None = None
    cancellation: JsonObject | None = None


class StepOutput(DTO):
    status: str
    state_delta: JsonObject


class TaskOutput(DTO):
    task_id: str
    status: str
    result: JsonObject | None = None
    error: str | None = None
    metadata: JsonObject


class TasksOutput(DTO):
    tasks: list[TaskOutput]


class EnrollExecutionInput(DTO):
    engine_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    request: JsonObject
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_key: str
    launch_metadata: dict[str, str] = Field(default_factory=dict, max_length=16)
    execute: bool = True
    envelope: EnvelopeInput | None = None

    @field_validator("launch_metadata")
    @classmethod
    def _bounded_launch_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or len(key) > 64 or len(item) > 512
               for key, item in value.items()):
            raise ValueError("launch_metadata exceeds key/value limits")
        return value


class ExecutionRunOutput(DTO):
    run_id: str
    run_key: str
    status: str
    attempt_id: str | None
    attempt_revision: int | None
    engine_id: str
    registration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: str
    started_at: str
    result: JsonObject | None = None
    error: str | None = None


class AppendExecutionEventInput(DTO):
    workflow_run_id: str
    attempt_id: str
    revision: int = Field(ge=1)
    engine_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    registration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence: int = Field(ge=0)
    terminal: bool
    raw_evidence: JsonObject
    safe_metadata: dict[str, str] = Field(default_factory=dict, max_length=16)

    @field_validator("raw_evidence")
    @classmethod
    def _validate_execution_evidence(cls, value: JsonObject) -> JsonObject:
        return value


    @field_validator("safe_metadata")
    @classmethod
    def _validate_safe_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 16 or any(len(key) > 32 or len(item) > 256 for key, item in value.items()):
            raise ValueError("safe_metadata exceeds bounded key/count/value limits")
        return value


class AppendExecutionEventOutput(DTO):
    appended: bool
    sequence: int
    raw_digest: str
