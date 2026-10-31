"""Workflow step runner and transition coordinator."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.event_emitter import emit as emit_workflow_event
from factory.workflow.runtime.graph_sync import sync_run, workflow_entity_id
from factory.workflow.runtime.models import WorkflowDefinition
from factory.workflow.runtime.ports import (
    DurableWorkflowStorage, NamedTaskExecutorPort, WorkflowStorage,
)
from factory.workflow.runtime.run_binding import DurableIntegrityError
from factory.workflow.runtime.run_cas import (
    ACTIVE_STATUSES, TERMINAL_STATUSES, observe_or_transition,
)
from .adapters import LocalExecutor, TaskExecutor
from .live_events import emit_terminal
from .steps import handle_legacy_task, handle_noop, handle_task, handle_wait_for_event


class Runner:
    def __init__(
        self, *, storage: WorkflowStorage, workflows: dict[str, WorkflowDefinition],
        executor: TaskExecutor | None = None,
        durable_storage: DurableWorkflowStorage | None = None,
        named_executor: NamedTaskExecutorPort | None = None,
    ):
        self.storage = storage
        self.workflows = workflows
        self.executor = executor or LocalExecutor()
        self.durable_storage = durable_storage
        self.named_executor = named_executor

    def _definition(self, record: Any) -> WorkflowDefinition | None:
        if record.workflow_version_id:
            if self.durable_storage is None:
                raise ValueError("durable workflow storage capability unavailable")
            return self.durable_storage.load_workflow_version(record.workflow_version_id)
        return self.workflows.get(record.workflow_id)

    def _dispatch(
        self, workflow: WorkflowDefinition, step: Any, record: Any,
        action_envelope: Envelope, execution_envelope: Envelope,
        last_event_id: int,
    ) -> Any:
        if step.kind == "noop":
            return handle_noop(step, record, self.storage, action_envelope)
        if step.kind == "wait_for_event":
            return handle_wait_for_event(
                step, record, self.storage, action_envelope, last_event_id,
            )
        if step.kind == "task" and step.task_mode == "executor":
            return handle_legacy_task(
                step, record, self.storage, action_envelope, self.executor,
            )
        if step.kind == "task" and step.task_mode == "named_mcp":
            from factory.mcp_utils.interface import reset_envelope, set_envelope

            envelope_token = set_envelope(execution_envelope.model_dump(mode="json"))
            try:
                return handle_task(
                    workflow, step, record, self.storage, self.durable_storage,
                    execution_envelope, self.named_executor,
                )
            finally:
                reset_envelope(envelope_token)
        raise ValueError(f"Unsupported step kind: {step.kind}")

    def step_run(
        self, *, run_id: str, envelope: Envelope, max_transitions: int,
        execution_envelope: Envelope | None = None,
    ) -> dict[str, Any]:
        record = self.storage.get_run(run_id=run_id)
        if record is None:
            raise ValueError("Run not found")
        if record.status in {"succeeded", "failed", "cancelled"}:
            return {"status": record.status, "state_delta": {"transitions": []}}
        try:
            workflow = self._definition(record)
        except Exception as exc:
            failed, _ = self._fail_run(run_id, record, f"{type(exc).__name__}: {exc}")
            return {"status": failed.status, "state_delta": {"transitions": []}}
        if workflow is None:
            failed, _ = self._fail_run(run_id, record, "Workflow definition missing")
            return {"status": failed.status, "state_delta": {"transitions": []}}

        transitions: list[dict[str, Any]] = []
        current_step_id = record.current_step_id or workflow.first_step_id()
        last_event_id = record.last_event_id
        base_envelope = execution_envelope or envelope
        task_envelope = base_envelope.model_copy(update={
            "workflow_id": record.workflow_id, "run_id": record.run_id,
        })
        exhausted = True
        effect_owned = False
        for _ in range(max_transitions):
            step = workflow.get_step(current_step_id)
            try:
                dispatched = self._dispatch(
                    workflow, step, record, envelope, task_envelope,
                    last_event_id,
                )
                if step.kind == "wait_for_event":
                    result, last_event_id = dispatched
                else:
                    result = dispatched
            except DurableIntegrityError:
                raise
            except Exception as exc:
                exhausted = False
                failed, won = self._fail_run(
                    run_id, record, f"{type(exc).__name__}: {exc}",
                )
                if won:
                    transitions.append({"step": current_step_id, "status": failed.status})
                break
            if result.effect_owned:
                effect_owned = True
                transitions.append(result.transition)
                emit_workflow_event(
                    "workflow.step_transition",
                    {"run_id": run_id, "entity_id": workflow_entity_id(run_id),
                     "workflow_id": record.workflow_id, "workflow_type": workflow.name,
                     "current_step_id": current_step_id, **result.transition},
                    envelope.model_dump(mode="json"), record.model_dump(mode="json"),
                )
                emit_terminal(result, record, workflow)
            if result.done:
                exhausted = False
                break
            current_step_id = result.next_step_id or current_step_id
            record = self.storage.get_run(run_id=run_id) or record

        current = self.storage.get_run(run_id=run_id)
        if exhausted and current and current.status in {"pending", "running"}:
            try:
                current = self.storage.update_run(
                    run_id=run_id, status="running", current_step_id=current_step_id,
                    waiting_for_event_type=None, last_event_id=last_event_id,
                    result=current.result, error=current.error,
                    now=datetime.now(timezone.utc), expected_statuses=set(ACTIVE_STATUSES),
                    expected_revision=current.revision,
                )
                effect_owned = True
            except ValueError:
                current = self.storage.get_run(run_id=run_id)
                if current is None or current.status not in TERMINAL_STATUSES:
                    raise
        final = current or self.storage.get_run(run_id=run_id)
        if final is not None and effect_owned:
            sync_run(
                final.model_dump(mode="json"), envelope.model_dump(mode="json"),
                {"workflow_type": workflow.name, "workflow_name": workflow.name},
            )
        return {"status": final.status if final else "failed",
                "state_delta": {"transitions": transitions}}

    def _fail_run(self, run_id: str, record: Any, error: str) -> tuple[Any, bool]:
        updated, won = observe_or_transition(
            self.storage, record, status="failed",
            fields=lambda current: {
                "current_step_id": current.current_step_id,
                "waiting_for_event_type": None, "last_event_id": None,
                "result": current.result, "error": error,
            },
        )
        if not won:
            return updated, False
        sync_run(updated.model_dump(mode="json"))
        emit_workflow_event(
            "workflow.run_failed",
            {"run_id": run_id, "entity_id": workflow_entity_id(run_id),
             "workflow_id": record.workflow_id,
             "current_step_id": record.current_step_id,
             "status": updated.status, "error": error},
            record.model_dump(mode="json") if hasattr(record, "model_dump") else record,
        )
        return updated, True
