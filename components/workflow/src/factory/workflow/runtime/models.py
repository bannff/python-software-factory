from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .run_models import EventRecord, RunRecord, RunStatus
from .task_models import TaskOutcomePolicy

SchemaVersion = Literal["v1", "v2"]
StepKind = Literal["noop", "wait_for_event", "task"]
TaskMode = Literal["executor", "named_mcp"]
ExecutorBackend = Literal["local", "celery", "dagster"]


class ToolTarget(BaseModel):
    """Immutable gateway address for one named MCP tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    brick_name: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)


class ServiceSettings(BaseModel):
    name: str = "workflow-module"


from .execution_engines import ExecutionEngineSpec


class ExecutionEngineSettings(BaseModel):
    """Trusted provider-neutral engine registrations for host composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    engines: list["ExecutionEngineSpec"] = Field(default_factory=list)


class SQLiteSettings(BaseModel):
    filename: str = "workflow_state.sqlite"


class AWSStorageSettings(BaseModel):
    table_name: str = "factory-workflow-runs"
    state_machine_arn: str = ""
    region: str = "us-east-1"


class StorageSettings(BaseModel):
    backend: Literal["sqlite", "aws"] = "sqlite"
    sqlite: SQLiteSettings = Field(default_factory=SQLiteSettings)
    aws: AWSStorageSettings = Field(default_factory=AWSStorageSettings)


class CelerySettings(BaseModel):
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str | None = None
    app_name: str = "factory-workflow"


class DagsterSettings(BaseModel):
    host: str | None = None
    port: int = 4266
    instance_config: dict[str, Any] | None = None


class ExecutorSettings(BaseModel):
    backend: ExecutorBackend = "local"
    celery: CelerySettings = Field(default_factory=CelerySettings)
    dagster: DagsterSettings = Field(default_factory=DagsterSettings)


class AuthoringSettings(BaseModel):
    enabled: bool = False


class DurableTaskSettings(BaseModel):
    """SQLite-only named MCP task configuration."""

    allowlist: dict[str, ToolTarget] = Field(default_factory=dict)


class Settings(BaseModel):
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    executor: ExecutorSettings = Field(default_factory=ExecutorSettings)
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)
    durable_tasks: DurableTaskSettings = Field(default_factory=DurableTaskSettings)
    execution_engines: ExecutionEngineSettings = Field(
        default_factory=ExecutionEngineSettings
    )


class StepDefinition(BaseModel):
    id: str
    kind: StepKind
    next: str | None = None
    event_type: str | None = None
    task_mode: TaskMode = "executor"
    task_type: str | None = None
    tool_target: ToolTarget | None = None
    task_payload: dict[str, Any] = Field(default_factory=dict)
    task_options: dict[str, Any] = Field(default_factory=dict)
    task_outcome: TaskOutcomePolicy | None = None
    service_binding: Literal["attempt", "execution"] | None = None
    idempotency_key_argument: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    run_id_argument: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    attempt_revision_argument: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    max_attempts: int = Field(default=1, ge=1, le=100)
    max_continuations: int = Field(default=0, ge=0, le=10_000)
    lease_seconds: int = Field(default=30, ge=1, le=86400)

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> "StepDefinition":
        if self.kind == "wait_for_event" and not self.event_type:
            raise ValueError("wait_for_event steps require event_type")
        if self.kind == "task" and (
            not self.task_type or not self.task_type.strip()
        ):
            raise ValueError("task steps require a non-empty task_type")
        if self.kind != "task" and (self.tool_target or self.task_mode != "executor"):
            raise ValueError("task execution fields require kind=task")
        runtime_arguments = (
            self.idempotency_key_argument,
            self.run_id_argument,
            self.attempt_revision_argument,
        )
        if self.task_mode == "executor" and (
            self.tool_target is not None or self.task_outcome is not None
            or self.service_binding is not None or any(runtime_arguments)
        ):
            raise ValueError("named MCP fields require task_mode=named_mcp")
        names = [name for name in runtime_arguments if name]
        if len(names) != len(set(names)):
            raise ValueError("named MCP runtime arguments must be distinct")
        continued = self.task_outcome and self.task_outcome.continuation is not None
        if bool(continued) != (self.max_continuations > 0):
            raise ValueError("continuation policy requires a positive continuation cap")
        return self


class WorkflowDefinition(BaseModel):
    schema_version: SchemaVersion = "v2"
    id: str
    name: str
    version: int = 1
    steps: list[StepDefinition]
    tags: list[str] = Field(default_factory=list)
    result_projection: dict[str, Any] | None = None

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, steps: list[StepDefinition]) -> list[StepDefinition]:
        if not steps:
            raise ValueError("workflow must have at least one step")
        ids = [step.id for step in steps]
        if len(set(ids)) != len(ids):
            raise ValueError("step ids must be unique")
        return steps

    @model_validator(mode="after")
    def _validate_schema_fields(self) -> "WorkflowDefinition":
        if self.schema_version == "v1" and (
            self.result_projection is not None or any(
                step.task_outcome is not None
                or step.service_binding is not None
                or step.idempotency_key_argument is not None
                or step.run_id_argument is not None
                or step.attempt_revision_argument is not None
                for step in self.steps
            )
        ):
            raise ValueError("projected named-MCP fields require schema_version=v2")
        if self.result_projection is not None:
            terminals = [step for step in self.steps if step.next is None]
            if not terminals or any(
                step.kind != "task" or step.task_mode != "named_mcp"
                for step in terminals
            ):
                raise ValueError("result_projection requires named_mcp terminal steps")
        return self

    def first_step_id(self) -> str:
        return self.steps[0].id

    def get_step(self, step_id: str) -> StepDefinition:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"Unknown step: {step_id}")

    def has_named_mcp(self) -> bool:
        return any(step.kind == "task" and step.task_mode == "named_mcp" for step in self.steps)
