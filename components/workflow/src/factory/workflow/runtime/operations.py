"""Workflow run lifecycle operations."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from .authority import execution_envelope
from .canonical import canonical_json
from .envelope import Envelope
from .execution.runner import Runner
from .execution_operations import ExecutionOperations
from .models import ToolTarget, WorkflowDefinition
from .ports import DurableWorkflowStorage, ToolInvokerPort, WorkflowStorage
from .run_cas import ACTIVE_STATUSES
from .run_cancellation import cancel_run as cancel_workflow_run
from .run_events import announce_start
from .task_bindings import bind_named_targets
from .task_ids import workflow_run_id

class WorkflowError(ValueError): pass
def _now() -> datetime: return datetime.now(timezone.utc)


def _run_visible(record: Any, envelope: Envelope) -> bool:
    """Owner-scoped read fence: tenant parity + initiating-principal parity.

    Parity is enforced only where both sides are set, so tenant-only and
    legacy (principal-less) callers keep working; a same-tenant foreign-owner
    read collapses to the uniform opaque ``WorkflowError("Run not found")``.
    """
    if (envelope.tenant_id and record.tenant_id
            and envelope.tenant_id != record.tenant_id):
        return False
    principal = record.initiation_envelope.principal_id
    if (envelope.principal_id and principal
            and envelope.principal_id != principal):
        return False
    return True


class WorkflowOperations(ExecutionOperations):
    def __init__(
        self, storage: WorkflowStorage, runner: Runner,
        workflow_by_id: dict[str, WorkflowDefinition],
        workflow_by_name: dict[str, WorkflowDefinition],
        durable_storage: DurableWorkflowStorage | None = None,
        task_allowlist: dict[str, ToolTarget] | None = None,
        tool_invoker: ToolInvokerPort | None = None,
    ):
        self.storage = storage
        self.runner = runner
        self._workflow_by_id = workflow_by_id
        self._workflow_by_name = workflow_by_name
        self._durable = durable_storage
        self._allowlist = dict(task_allowlist or {})
        self._tool_invoker = tool_invoker

    def _resolve_workflow(self, value: str) -> WorkflowDefinition:
        if value in self._workflow_by_id:
            return self._workflow_by_id[value]
        workflow = self._workflow_by_name.get(value.strip().lower())
        if workflow is None:
            raise WorkflowError("Unknown workflow")
        return workflow

    def _create_named(
        self, workflow: WorkflowDefinition, run_key: str | None,
        input: dict[str, Any], envelope: Envelope, now: datetime,
    ) -> tuple[Any, bool]:
        if self._durable is None:
            raise WorkflowError("durable named MCP execution requires SQLite")
        if not isinstance(run_key, str) or not run_key.strip():
            raise WorkflowError("named MCP workflows require a non-empty run_key")
        existing = self._durable.get_run_by_key(run_key=run_key)
        if existing is not None:
            execution_envelope(existing, envelope)
            same = (
                existing.workflow_id == workflow.id
                and existing.workflow_version == workflow.version
                and existing.tenant_id == envelope.tenant_id
                and canonical_json(existing.input) == canonical_json(input)
                and existing.workflow_version_id is not None
                and existing.run_id == workflow_run_id(
                    existing.workflow_version_id, run_key, input,
                )
            )
            if not same:
                raise WorkflowError("run-key conflict")
            return existing, False
        try:
            bound = bind_named_targets(workflow, self._allowlist)
            version_id = self._durable.persist_workflow_version(bound)
        except ValueError as exc:
            raise WorkflowError(str(exc)) from exc
        run_id = workflow_run_id(version_id, run_key, input)
        try:
            record = self.storage.create_run(
                run_id=run_id, run_key=run_key, workflow_id=workflow.id,
                workflow_version=workflow.version, tenant_id=envelope.tenant_id,
                input=input, envelope=envelope, now=now,
                workflow_version_id=version_id, run_execution_id=run_id,
            )
        except ValueError as exc:
            raise WorkflowError(str(exc)) from exc
        return record, existing is None

    def _create_legacy(
        self, workflow: WorkflowDefinition, input: dict[str, Any],
        envelope: Envelope, now: datetime,
    ) -> tuple[Any, bool]:
        run_id = envelope.run_id or str(uuid.uuid4())
        existing = self.storage.get_run(run_id=run_id)
        record = self.storage.create_run(
            run_id=run_id, run_key=None, workflow_id=workflow.id,
            workflow_version=workflow.version, tenant_id=envelope.tenant_id,
            input=input, envelope=envelope, now=now,
        )
        return record, existing is None

    def start_run(
        self, *, workflow_name_or_id: str, input: dict[str, Any],
        envelope: Envelope, run_key: str | None = None,
    ) -> dict[str, Any]:
        workflow = self._resolve_workflow(workflow_name_or_id)
        canonical_json(input)
        now = _now()
        if workflow.has_named_mcp():
            record, created = self._create_named(workflow, run_key, input, envelope, now)
        else:
            record, created = self._create_legacy(workflow, input, envelope, now)
        if created:
            announce_start(self.storage, workflow, record, input, envelope, now)
        stepped = self.runner.step_run(
            run_id=record.run_id, envelope=envelope, max_transitions=25,
            execution_envelope=execution_envelope(record, envelope))
        return {"run_id": record.run_id, "run_key": record.run_key,
                "status": stepped["status"]}

    def get_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        record = self.storage.get_run(run_id=run_id)
        if record is None or not _run_visible(record, envelope):
            raise WorkflowError("Run not found")
        return record.model_dump()

    def list_runs(
        self, *, filter: dict[str, Any], pagination: dict[str, Any], envelope: Envelope,
    ) -> dict[str, Any]:
        records, cursor = self.storage.list_runs(
            tenant_id=envelope.tenant_id or filter.get("tenant_id"),
            workflow_id=filter.get("workflow_id"), status=filter.get("status"),
            limit=max(1, min(int(pagination.get("limit", 50)), 200)),
            cursor=pagination.get("cursor"),
        )
        return {"runs": [record.model_dump() for record in records], "next_cursor": cursor}

    def cancel_run(
        self, *, run_id: str, reason: str | None, envelope: Envelope,
    ) -> dict[str, Any]:
        return cancel_workflow_run(
            storage=self.storage, durable=self._durable,
            invoker=self._tool_invoker, run_id=run_id,
            reason=reason, envelope=envelope,
        )

    def resume_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        record = self.storage.get_run(run_id=run_id)
        if record is None:
            raise WorkflowError("Run not found")
        task_envelope = execution_envelope(record, envelope)
        if record.status not in ACTIVE_STATUSES:
            return {"ok": True, "status": record.status}
        stepped = self.runner.step_run(
            run_id=run_id, envelope=envelope, max_transitions=25,
            execution_envelope=task_envelope)
        return {"ok": True, "status": stepped["status"]}

    def step_run(self, *, run_id: str, envelope: Envelope) -> dict[str, Any]:
        record = self.storage.get_run(run_id=run_id)
        if record is None:
            raise WorkflowError("Run not found")
        task_envelope = execution_envelope(record, envelope)
        return self.runner.step_run(
            run_id=run_id, envelope=envelope, max_transitions=25,
            execution_envelope=task_envelope)

    def emit_event(
        self, *, run_id: str, event_type: str, payload: dict[str, Any], envelope: Envelope,
    ) -> dict[str, Any]:
        record = self.storage.get_run(run_id=run_id)
        if record is None:
            raise WorkflowError("Run not found")
        execution_envelope(record, envelope)
        self.storage.append_event(
            run_id=run_id, event_type=event_type, payload=payload,
            envelope=envelope, now=_now(),
        )
        return {"ok": True}
