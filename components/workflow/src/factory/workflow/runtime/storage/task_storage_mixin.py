"""SQLite durable-workflow methods mixed into the storage adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.models import RunRecord, StepDefinition, WorkflowDefinition
from factory.workflow.runtime.task_inputs import resolve_task_input
from factory.workflow.runtime.task_models import (
    AttemptClaim, CancelledAttempt, VerifiedStepResult,
)
from . import (
    execution_events, task_claims, task_continuation, task_failures,
    task_integrity, task_journal,
    workflow_versions,
)


class DurableTaskStorageMixin:
    _connect: Any

    def persist_workflow_version(self, workflow: WorkflowDefinition) -> str:
        return workflow_versions.persist(self._connect, workflow)

    def load_workflow_version(self, version_id: str) -> WorkflowDefinition:
        return workflow_versions.load(self._connect, version_id)

    def get_run_by_key(self, *, run_key: str) -> RunRecord | None:
        from .runs import get_run_by_key
        return get_run_by_key(self._connect, run_key=run_key)

    def admit_task(
        self, *, run: RunRecord, step: StepDefinition, inputs: dict[str, Any],
    ) -> AttemptClaim:
        if not run.workflow_version_id or not run.run_execution_id:
            raise ValueError("run is not bound to a durable workflow snapshot")
        return task_claims.admit(
            self._connect, run_id=run.run_id, run_execution_id=run.run_execution_id,
            workflow_version_id=run.workflow_version_id, step_id=step.id,
            inputs=inputs, idempotency_argument=step.idempotency_key_argument,
        )

    def claim_task(
        self, *, run: RunRecord, step: StepDefinition,
        inputs: dict[str, Any], now: datetime,
    ) -> AttemptClaim:
        if not run.workflow_version_id or not run.run_execution_id:
            raise ValueError("run is not bound to a durable workflow snapshot")
        return task_claims.claim(
            self._connect, run_id=run.run_id, run_execution_id=run.run_execution_id,
            workflow_version_id=run.workflow_version_id, step_id=step.id,
            inputs=inputs, max_attempts=step.max_attempts,
            max_continuations=step.max_continuations,
            lease_seconds=step.lease_seconds, now=now,
            idempotency_argument=step.idempotency_key_argument,
        )

    def complete_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
        protected: bool = False,
    ) -> bool:
        return task_journal.complete(
            self._connect, attempt_id=attempt_id, revision=revision,
            lease_token=lease_token, output=output,
            envelope=envelope, evidence=evidence, protected=protected,
        )

    def continue_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
        protected: bool = False,
    ) -> bool:
        return task_continuation.record(
            self._connect, attempt_id=attempt_id, revision=revision,
            lease_token=lease_token, output=output, envelope=envelope,
            evidence=evidence, protected=protected,
        )

    def fail_task(
        self, *, attempt_id: str, revision: int, lease_token: str,
        error: str, envelope: dict[str, Any] | None,
        retryable: bool, max_attempts: int, protected: bool = False,
    ) -> bool:
        return task_journal.fail(
            self._connect, attempt_id=attempt_id, revision=revision,
            lease_token=lease_token, error=error, envelope=envelope,
            retryable=retryable, max_attempts=max_attempts, protected=protected,
        )

    def record_step_failure(
        self, *, run: RunRecord, step: StepDefinition,
        inputs: dict[str, Any], error: str, protected: bool = False,
    ) -> None:
        task_failures.record(
            self._connect, run=run, step=step, inputs=inputs, error=error,
            protected=protected,
        )

    def _load_verified_step(
        self, *, run: RunRecord, step_id: str, resolving: frozenset[str],
    ) -> VerifiedStepResult:
        if not run.workflow_version_id:
            raise ValueError("run is not bound to a durable workflow snapshot")
        if step_id in resolving:
            raise ValueError(f"cyclic workflow step input reference: {step_id}")
        workflow = self.load_workflow_version(run.workflow_version_id)
        step = workflow.get_step(step_id)
        if step.tool_target is None:
            raise ValueError(f"producer step is not a bound named MCP task: {step_id}")
        chain = resolving | {step_id}
        expected_input = resolve_task_input(
            workflow, step, run,
            lambda producer: self._load_verified_step(
                run=run, step_id=producer, resolving=chain,
            ),
        )
        return task_integrity.load_verified(
            self._connect, run=run, step_id=step_id,
            expected_target=step.tool_target,
            expected_step_input=canonical_json(expected_input),
            idempotency_argument=step.idempotency_key_argument,
        )

    def load_verified_step(
        self, *, run: RunRecord, step_id: str,
    ) -> VerifiedStepResult:
        return self._load_verified_step(
            run=run, step_id=step_id, resolving=frozenset(),
        )

    def load_step_output(self, *, run: RunRecord, step_id: str) -> Any:
        return self.load_verified_step(run=run, step_id=step_id).output

    def list_task_attempts(self, *, run_id: str) -> list[dict[str, Any]]:
        return task_journal.list_attempts(self._connect, run_id=run_id)

    def cancel_task_attempts(
        self, *, run_id: str, reason: str,
    ) -> list[CancelledAttempt]:
        return task_journal.cancel_attempts(
            self._connect, run_id=run_id, reason=reason,
        )

    def append_execution_event(
        self, *, workflow_run_id: str, attempt_id: str, revision: int,
        engine_id: str, registration_digest: str, request_digest: str,
        provider_request_digest: str, sequence: int, terminal: bool,
        raw_evidence: dict[str, Any], safe_metadata: dict[str, str], now: datetime,
    ) -> dict[str, Any]:
        return execution_events.append(
            self._connect, workflow_run_id=workflow_run_id, attempt_id=attempt_id,
            revision=revision, engine_id=engine_id, registration_digest=registration_digest,
            request_digest=request_digest, provider_request_digest=provider_request_digest,
            sequence=sequence, terminal=terminal, raw_evidence=raw_evidence,
            safe_metadata=safe_metadata, now=now,
        )

    def get_execution_events(
        self, *, workflow_run_id: str, attempt_id: str | None = None,
        revision: int | None = None,
    ) -> list[dict[str, Any]]:
        return execution_events.get(self._connect, workflow_run_id=workflow_run_id,
                                    attempt_id=attempt_id, revision=revision)
