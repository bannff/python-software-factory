from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .envelope import Envelope
from .models import EventRecord, RunRecord, StepDefinition, ToolTarget, WorkflowDefinition
from .task_models import (
    AttemptClaim, CancelledAttempt, TaskExecutionResult, TaskOutcomePolicy,
    VerifiedStepResult,
)


class ToolInvokerPort(Protocol):
    """Authenticated gateway boundary.

    Calls are at-least-once. Implementations must use ``idempotency_key`` to
    deduplicate externally committed effects when a lease is reclaimed.
    """

    def invoke(
        self, *, target: ToolTarget, arguments: dict[str, Any],
        idempotency_key: str, envelope: Envelope,
        attempt: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class NamedTaskExecutorPort(Protocol):
    def execute(
        self, *, target: ToolTarget, arguments: dict[str, Any],
        attempt_id: str, envelope: Envelope, revision: int = 1,
        outcome_policy: TaskOutcomePolicy | None = None,
        bind_service_attempt: bool = False,
    ) -> TaskExecutionResult: ...


class WorkflowStorage(Protocol):
    def init_schema(self) -> None: ...
    def health_check(self) -> dict[str, Any]: ...

    def create_run(
        self, *, run_id: str, workflow_id: str,
        workflow_version: int, tenant_id: str | None, input: dict[str, Any],
        envelope: Envelope, now: datetime, run_key: str | None = None,
        workflow_version_id: str | None = None,
        run_execution_id: str | None = None,
    ) -> RunRecord: ...

    def get_run(self, *, run_id: str) -> RunRecord | None: ...

    def update_run(
        self, *, run_id: str, status: str, current_step_id: str | None,
        waiting_for_event_type: str | None, last_event_id: int | None,
        result: dict[str, Any] | None, error: str | None, now: datetime,
        expected_statuses: set[str] | None = None,
        expected_revision: int | None = None,
    ) -> RunRecord: ...

    def list_runs(
        self, *, tenant_id: str | None, workflow_id: str | None,
        status: str | None, limit: int, cursor: str | None,
    ) -> tuple[list[RunRecord], str | None]: ...

    def append_event(
        self, *, run_id: str, event_type: str, payload: dict[str, Any],
        envelope: Envelope, now: datetime,
    ) -> EventRecord: ...

    def get_events_since(
        self, *, run_id: str, after_event_id: int,
    ) -> list[EventRecord]: ...

    def get_last_event_id(self, *, run_id: str) -> int: ...


@runtime_checkable
class DurableWorkflowStorage(Protocol):
    """Snapshot, journal, and output-reference capabilities for named MCP."""

    def persist_workflow_version(self, workflow: WorkflowDefinition) -> str: ...
    def load_workflow_version(self, version_id: str) -> WorkflowDefinition: ...
    def get_run_by_key(self, *, run_key: str) -> RunRecord | None: ...

    def admit_task(
        self, *, run: RunRecord, step: StepDefinition,
        inputs: dict[str, Any],
    ) -> AttemptClaim: ...

    def claim_task(
        self, *, run: RunRecord, step: StepDefinition,
        inputs: dict[str, Any], now: datetime,
    ) -> AttemptClaim: ...

    def complete_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
        protected: bool = False,
    ) -> bool: ...

    def continue_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
        protected: bool = False,
    ) -> bool: ...

    def fail_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        error: str, envelope: dict[str, Any] | None,
        retryable: bool, max_attempts: int, protected: bool = False,
    ) -> bool: ...

    def record_step_failure(
        self, *, run: RunRecord, step: StepDefinition,
        inputs: dict[str, Any], error: str, protected: bool = False,
    ) -> None: ...

    def load_verified_step(
        self, *, run: RunRecord, step_id: str,
    ) -> VerifiedStepResult: ...
    def load_step_output(self, *, run: RunRecord, step_id: str) -> Any: ...
    def list_task_attempts(self, *, run_id: str) -> list[dict[str, Any]]: ...
    def cancel_task_attempts(
        self, *, run_id: str, reason: str,
    ) -> list[CancelledAttempt]: ...
    def append_execution_event(
        self, *, workflow_run_id: str, attempt_id: str, revision: int,
        engine_id: str, registration_digest: str, request_digest: str,
        provider_request_digest: str, sequence: int, terminal: bool,
        raw_evidence: dict[str, Any], safe_metadata: dict[str, str], now: datetime,
    ) -> dict[str, Any]: ...
    def get_execution_events(
        self, *, workflow_run_id: str, attempt_id: str | None = None,
        revision: int | None = None,
    ) -> list[dict[str, Any]]: ...
