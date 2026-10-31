"""Durable handler for explicitly selected named-MCP task steps."""
from __future__ import annotations
from datetime import datetime, timezone

from factory.mcp_utils.interface import (
    is_protected_operation, protected_error_text,
)
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import RunRecord, StepDefinition, WorkflowDefinition
from factory.workflow.runtime.ports import (
    DurableWorkflowStorage, NamedTaskExecutorPort, WorkflowStorage,
)
from factory.workflow.runtime.task_models import AttemptClaim
from factory.workflow.runtime.storage.task_claims import ContinuationLimitError
from factory.workflow.runtime.run_binding import (
    DurableIntegrityError, verify_durable_run_binding,
)
from factory.workflow.runtime.task_inputs import resolve_task_input
from .base import StepResult
from .task_binding import execution_arguments
from .task_completion import success, terminal
from .task_stale import observe_stale
from .task_events import completed as emit_attempt_completed, started as emit_attempt_started


def _resolve_payload(
    workflow: WorkflowDefinition, step: StepDefinition, run: RunRecord,
    durable: DurableWorkflowStorage,
) -> dict:
    verify_durable_run_binding(run)
    return resolve_task_input(
        workflow, step, run,
        lambda step_id: durable.load_verified_step(run=run, step_id=step_id),
    )


def handle_task(
    workflow: WorkflowDefinition, step: StepDefinition, run: RunRecord,
    storage: WorkflowStorage, durable: DurableWorkflowStorage | None,
    envelope: Envelope, executor: NamedTaskExecutorPort | None,
) -> StepResult:
    """Claim, invoke at least once, and fence one deterministic attempt."""
    if durable is None or executor is None:
        return terminal(
            storage, run, step, "failed",
            "durable named MCP execution requires SQLite and a tool invoker",
        )
    if step.tool_target is None:
        return terminal(
            storage, run, step, "failed", "named MCP step lacks frozen target",
        )
    declared = (
        {**run.input, **step.task_payload}
        if workflow.schema_version == "v1" else step.task_payload
    )
    protected = is_protected_operation(f"{step.tool_target.brick_name}.{step.tool_target.tool_name}", declared)
    try:
        payload = _resolve_payload(workflow, step, run, durable)
        claim = durable.claim_task(
            run=run, step=step, inputs=payload, now=datetime.now(timezone.utc),
        )
    except DurableIntegrityError:
        raise
    except ContinuationLimitError:
        error = "continuation limit exhausted"
        durable.record_step_failure(
            run=run, step=step, inputs=declared, error=error, protected=protected)
        return terminal(
            storage, run, step, "failed", error,
            result={"terminal_reason": "continuation_exhausted"},
        )
    except Exception as exc:
        error = protected_error_text(
            f"{type(exc).__name__}: {exc}", protected=protected,
        )
        durable.record_step_failure(
            run=run, step=step, inputs=declared, error=error,
            protected=protected,
        )
        return terminal(storage, run, step, "failed", error)
    transition = {"step": step.id, "attempt_id": claim.attempt_id}
    if claim.status == "busy":
        return StepResult(
            True, None, {**transition, "status": "running"},
            status="running", effect_owned=False,
        )
    if claim.status == "succeeded":
        output = durable.load_verified_step(run=run, step_id=step.id).output
        return success(
            storage, durable, workflow, run, step, claim.attempt_id, output,
            effect_owned=False,
        )
    if claim.status in {"failed", "cancelled"}:
        status = "cancelled" if claim.status == "cancelled" else "failed"
        return terminal(storage, run, step, status, claim.error or f"task {status}")
    if not claim.lease_token:
        return terminal(
            storage, run, step, "failed", "claimed attempt lacks lease token",
        )
    emit_attempt_started(run, step, claim)
    try:
        arguments = execution_arguments(step, run, claim)
        protected = is_protected_operation(f"{step.tool_target.brick_name}.{step.tool_target.tool_name}", arguments)
        executed = executor.execute(
            target=step.tool_target, arguments=arguments,
            attempt_id=claim.attempt_id, revision=claim.revision,
            envelope=envelope, outcome_policy=step.task_outcome,
            bind_service_attempt=step.service_binding in {"attempt", "execution"},
        )
    except Exception as exc:
        error = protected_error_text(
            f"{type(exc).__name__}: {exc}", protected=protected,
        )
        try:
            durable.fail_task(
                attempt_id=claim.attempt_id, revision=claim.revision,
                lease_token=claim.lease_token, error=error, envelope=None,
                retryable=False, max_attempts=step.max_attempts,
                protected=protected,
            )
        except ValueError as stale:
            return observe_stale(
                durable, storage, workflow, run, step, claim.attempt_id,
                stale, "stale task failure",
            )
        emit_attempt_completed(
            run, step, claim, status="failed", error=error,
            protected=protected,
        )
        return terminal(storage, run, step, "failed", error)
    if executed.status == "continued":
        try:
            committed = durable.continue_task(
                attempt_id=claim.attempt_id, revision=claim.revision,
                lease_token=claim.lease_token, output=executed.output,
                envelope=executed.transport_envelope or {},
                evidence=executed.evidence or {}, protected=protected,
            )
        except ValueError as stale:
            return observe_stale(
                durable, storage, workflow, run, step, claim.attempt_id,
                stale, "stale task continuation",
            )
        if committed:
            emit_attempt_completed(run, step, claim, status="continued")
        return StepResult(
            False, step.id, {**transition, "status": "continuing"},
            effect_owned=committed,
        )
    if executed.status == "succeeded":
        try:
            committed = durable.complete_task(
                attempt_id=claim.attempt_id, revision=claim.revision,
                lease_token=claim.lease_token, output=executed.output,
                envelope=executed.transport_envelope or {},
                evidence=executed.evidence or {}, protected=protected,
            )
        except ValueError as stale:
            return observe_stale(
                durable, storage, workflow, run, step, claim.attempt_id,
                stale, "stale task completion",
            )
        if committed:
            emit_attempt_completed(run, step, claim, status="succeeded")
        return success(
            storage, durable, workflow, run, step, claim.attempt_id,
            executed.output, effect_owned=committed,
        )
    failure_error = protected_error_text(
        executed.error or "task failed", protected=protected,
    )
    try:
        approved = durable.fail_task(
            attempt_id=claim.attempt_id, revision=claim.revision,
            lease_token=claim.lease_token, error=failure_error,
            envelope=executed.transport_envelope, retryable=executed.retryable,
            max_attempts=step.max_attempts, protected=protected,
        )
    except ValueError as stale:
        return observe_stale(
            durable, storage, workflow, run, step, claim.attempt_id,
            stale, "stale task failure",
        )
    emit_attempt_completed(
        run, step, claim, status="failed", error=failure_error,
        protected=protected,
    )
    if approved:
        return StepResult(False, step.id, {**transition, "status": "retrying"})
    return terminal(storage, run, step, "failed", failure_error)
