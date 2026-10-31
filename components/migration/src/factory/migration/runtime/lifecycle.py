"""Workflow enrollment and progress projection for immutable Migration plans."""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from factory.mcp_utils.interface import protected_canonical_json

from ..mcp.execution_contracts import ApplyPageRequest
from ..mcp.lifecycle_contracts import KindProgress, MigrationGetOutput, MigrationStartOutput
from .ports import ReceiptStore
from .receipt_models import ImportOutcome, PlanIdentity
from .source_models import SourceKind

_ENGINE = "migration_import"


def _native_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("ok") is not True:
        raise ValueError("migration workflow transport unavailable")
    native = value.get("result")
    structured = native.get("structured_content") if isinstance(native, dict) else None
    if not isinstance(structured, dict) or structured.get("schema_version") != "v1" \
            or structured.get("ok") is not True:
        raise ValueError("migration workflow result unavailable")
    data = structured.get("data")
    if not isinstance(data, dict):
        raise ValueError("migration workflow data unavailable")
    return data


def stable_run_key(plan: PlanIdentity) -> str:
    material = {
        "tenant_id": plan.tenant_id, "owner_id": plan.owner_id,
        "adapter": plan.adapter, "source_fingerprint": plan.source_fingerprint,
        "plan_digest": plan.plan_digest, "kinds": list(plan.kinds),
    }
    return "migration-import:" + hashlib.sha256(
        protected_canonical_json(material)).hexdigest()


def start_plan(
    plan: PlanIdentity, invoker: Callable[..., dict[str, Any]],
    envelope: dict[str, Any],
) -> MigrationStartOutput:
    request = ApplyPageRequest(
        tenant_id=plan.tenant_id, owner_id=plan.owner_id,
        source_adapter=plan.adapter, source_fingerprint=plan.source_fingerprint,
        plan_digest=plan.plan_digest, kinds=list(plan.kinds), page_size=50,
    ).model_dump(mode="json")
    digest = plan.plan_digest.removeprefix("sha256:")
    run_key = stable_run_key(plan)
    response = invoker(
        {"brick_name": "workflow", "tool_name": "enroll_execution"},
        arguments={
            "engine_id": _ENGINE, "request": request,
            "provider_request_digest": digest, "manifest_digest": digest,
            "run_key": run_key, "launch_metadata": {"kind": "migration"},
            "execute": True, "envelope": envelope,
        },
        idempotency_key=run_key, envelope=envelope,
        enrollment={"run_key": run_key, "manifest_digest": digest},
    )
    data = _native_data(response)
    if data.get("run_key") != run_key or data.get("manifest_digest") != digest \
            or data.get("engine_id") != _ENGINE:
        raise ValueError("migration workflow binding mismatch")
    return MigrationStartOutput(run_id=data["run_id"], status=data["status"])


def _reason(status: str, result: Any) -> str:
    if status == "succeeded":
        return "completed"
    if status == "cancelled":
        return "cancelled"
    if isinstance(result, dict) and result.get("terminal_reason") == "continuation_exhausted":
        return "continuation_exhausted"
    return "workflow_failed" if status == "failed" else ""


def project_progress(
    receipts: ReceiptStore, invoker: Callable[..., dict[str, Any]],
    envelope: dict[str, Any], run_id: str,
) -> MigrationGetOutput:
    data = _native_data(invoker(
        {"brick_name": "workflow", "tool_name": "get_run"},
        arguments={"run_id": run_id, "envelope": envelope},
        idempotency_key=f"migration-get:{run_id}", envelope=envelope,
    ))
    if (
        data.get("run_id") != run_id
        or data.get("workflow_id") != "inhouse-execution:migration_import"
    ):
        raise ValueError("migration workflow identity mismatch")
    material = data.get("input")
    if not isinstance(material, dict) or material.get("engine_id") != _ENGINE:
        raise ValueError("migration workflow engine mismatch")
    request = ApplyPageRequest.model_validate(material.get("request"))
    if request.tenant_id != envelope.get("tenant_id") \
            or request.owner_id != envelope.get("principal_id"):
        raise ValueError("migration workflow authority mismatch")
    plan = receipts.get_plan(
        request.tenant_id, request.owner_id, request.source_adapter,
        request.source_fingerprint, request.plan_digest)
    if plan is None or plan.kinds != tuple(request.kinds):
        raise ValueError("migration workflow plan mismatch")
    progress = []
    for kind in request.source_kinds:
        rows = receipts.list_receipts(
            request.tenant_id, request.owner_id, request.source_adapter,
            request.source_fingerprint, kind=kind.value)
        counts = {outcome: 0 for outcome in ImportOutcome}
        for row in rows:
            counts[row.outcome] += 1
        cursor = receipts.load_cursor(
            request.tenant_id, request.owner_id, request.source_adapter,
            request.source_fingerprint, request.plan_digest, kind.value)
        progress.append(KindProgress(
            kind=kind, imported=counts[ImportOutcome.IMPORTED],
            skipped=counts[ImportOutcome.SKIPPED], failed=counts[ImportOutcome.FAILED],
            cursor=cursor.page_index if cursor else 0,
        ))
    status = str(data.get("status") or "unknown")
    return MigrationGetOutput(
        run_id=run_id, status=status, progress=tuple(progress),
        terminal_reason=_reason(status, data.get("result")),
    )


__all__ = ["project_progress", "stable_run_key", "start_plan"]
