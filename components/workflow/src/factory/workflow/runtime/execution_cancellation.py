"""Frozen provider-neutral cancellation after Workflow's durable fence."""
from __future__ import annotations

from typing import Any

from .canonical import canonical_loads
from .envelope import Envelope
from .models import RunRecord, ToolTarget
from .ports import DurableWorkflowStorage, ToolInvokerPort
from .task_models import CancelledAttempt


def _binding(attempt: CancelledAttempt) -> tuple[ToolTarget | None, dict[str, Any]]:
    material = canonical_loads(attempt.canonical_input)
    if not isinstance(material, dict): raise ValueError("execution attempt lacks canonical input")
    fields = ("engine_id", "registration_digest", "request_digest", "provider_request_digest")
    if not all(isinstance(material.get(field), str) for field in fields):
        raise ValueError("execution attempt lacks complete owner tuple")
    spec = material.get("engine_spec")
    cancel = spec.get("cancel_target") if isinstance(spec, dict) else None
    target = ToolTarget.model_validate(cancel) if isinstance(cancel, dict) else None
    return target, {"workflow_run_id": attempt.workflow_run_id, "attempt_id": attempt.attempt_id,
        "revision": attempt.revision, **{field: material[field] for field in fields}}


def signal_execution_cancellation(*, durable: DurableWorkflowStorage, invoker: ToolInvokerPort | None,
                                  record: RunRecord, attempts: list[CancelledAttempt], envelope: Envelope) -> dict[str, Any]:
    """Resolve only frozen snapshot data; never inspect a live engine registry."""
    del durable, record
    if not attempts: return {"outcome": "not_found", "attempt_id": None}
    if len(attempts) != 1: return {"outcome": "ambiguous_attempts", "attempt_id": None}
    try:
        target, binding = _binding(attempts[0])
    except ValueError:
        return {"outcome": "no_provider_cancel", "attempt_id": attempts[0].attempt_id}
    if target is None: return {"outcome": "no_provider_cancel", "attempt_id": attempts[0].attempt_id}
    if invoker is None: return {"outcome": "transport_error", "attempt_id": attempts[0].attempt_id, "error": "tool invoker unavailable"}
    try:
        transport = invoker.invoke(target=target, arguments=binding,
            idempotency_key=f"cancel:{attempts[0].attempt_id}:r{attempts[0].revision}", envelope=envelope, attempt=binding)
        native = transport.get("result", {}) if isinstance(transport, dict) and transport.get("ok") else {}
        data = native.get("structured_content", {}) if isinstance(native, dict) else {}
        data = data.get("data", data) if isinstance(data, dict) else {}
        outcome = data.get("outcome") if isinstance(data, dict) else None
        if outcome not in {"cancel_requested", "already_requested", "not_owner", "not_found"}: raise ValueError("unknown provider cancellation outcome")
        return {"outcome": outcome, "attempt_id": attempts[0].attempt_id, "revision": attempts[0].revision}
    except Exception as exc:
        return {"outcome": "transport_error", "attempt_id": attempts[0].attempt_id, "revision": attempts[0].revision, "error": f"{type(exc).__name__}: {exc}"}


__all__ = ["signal_execution_cancellation"]
