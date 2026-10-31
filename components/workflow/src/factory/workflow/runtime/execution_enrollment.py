"""Provider-neutral enrollment of immutable Workflow execution attempts."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from .authority import execution_envelope
from .bounded import bounded_canonical
from .execution_engines import ExecutionEngineSpec
from .models import StepDefinition, WorkflowDefinition
from .task_inputs import resolve_task_input


def request_material(request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    frozen, encoded = bounded_canonical(request)
    return frozen, hashlib.sha256(encoded.encode()).hexdigest()


def _binding_key(spec: ExecutionEngineSpec) -> str:
    """Return the immutable named-MCP alias for one registered engine."""
    return f"execution_engine:{spec.engine_id}"


def definition(spec: ExecutionEngineSpec, material: dict[str, Any]) -> WorkflowDefinition:
    runtime = {"workflow_run_id", "attempt_id", "revision"}
    payload = {
        target: {"$ref": f"workflow-run:///input#/{source}"}
        for source, target in spec.target_arguments.items() if source not in runtime
    }
    payload["engine_spec"] = {"$ref": "workflow-run:///input#/engine_spec"}
    return WorkflowDefinition(
        schema_version="v2",
        id=f"inhouse-execution:{spec.engine_id}",
        name="InHouse Workflow Execution",
        version=1,
        tags=["inhouse", "execution"],
        steps=[StepDefinition(
            id="execute",
            kind="task",
            task_mode="named_mcp",
            task_type=_binding_key(spec),
            tool_target=spec.invoke_target,
            task_payload=payload,
            idempotency_key_argument=spec.target_arguments["attempt_id"],
            run_id_argument=spec.target_arguments["workflow_run_id"],
            attempt_revision_argument=spec.target_arguments["revision"],
            task_outcome=spec.outcome,
            service_binding="execution",
            max_attempts=spec.max_attempts,
            max_continuations=spec.max_continuations,
        )],
    )


def enroll(ops: Any, *, spec: ExecutionEngineSpec, request: dict[str, Any],
           provider_request_digest: str, run_key: str, envelope: Any,
           execute: bool = True,
           launch_metadata: dict[str, str] | None = None) -> dict[str, Any]:
    frozen, request_digest = request_material(request)
    if not isinstance(provider_request_digest, str) or len(provider_request_digest) != 64:
        raise ValueError("provider_request_digest must be a SHA-256 digest")
    material = {"engine_id": spec.engine_id, "engine_spec": spec.frozen(),
      "registration_digest": spec.registration_digest, "request": frozen,
      "request_digest": request_digest, "provider_request_digest": provider_request_digest,
      "manifest_digest": provider_request_digest, "execution_mode": "managed"}
    if launch_metadata:
        material["launch_metadata"] = dict(launch_metadata)
    workflow = definition(spec, material)
    ops._allowlist.setdefault(_binding_key(spec), spec.invoke_target)
    now = datetime.now(UTC)
    record, created = ops._create_named(workflow, run_key, material, envelope, now)
    if created:
        from .run_events import announce_start
        announce_start(ops.storage, workflow, record, material, envelope, now)
    if execute:
        ops.runner.step_run(
            run_id=record.run_id, envelope=envelope, max_transitions=25,
            execution_envelope=execution_envelope(record, envelope),
        )
    else:
        step = workflow.get_step(workflow.first_step_id())
        payload = resolve_task_input(
            workflow, step, record,
            lambda step_id: ops._durable.load_verified_step(
                run=record, step_id=step_id,
            ),
        )
        ops._durable.admit_task(run=record, step=step, inputs=payload)
    authoritative = ops.storage.get_run(run_id=record.run_id)
    if authoritative is None:
        raise RuntimeError("execution enrollment invariant violated: missing authoritative run")
    attempts = ops._durable.list_task_attempts(run_id=record.run_id)
    attempt = attempts[-1] if attempts else None
    if attempt is None and authoritative.status not in {"failed", "cancelled"}:
        raise RuntimeError(
            "execution enrollment invariant violated: non-terminal run has no task attempt"
        )
    return {"run_id": authoritative.run_id, "run_key": authoritative.run_key,
      "status": authoritative.status, "result": authoritative.result, "error": authoritative.error,
      "attempt_id": attempt["attempt_id"] if attempt else None,
      "attempt_revision": attempt["revision"] if attempt else None,
      "engine_id": spec.engine_id, "registration_digest": spec.registration_digest,
      "request_digest": request_digest, "provider_request_digest": provider_request_digest,
      "manifest_digest": provider_request_digest, "execution_mode": "managed",
      "started_at": authoritative.started_at.isoformat()}
