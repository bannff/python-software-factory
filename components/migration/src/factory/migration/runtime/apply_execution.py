"""Apply one immutable Migration plan page through protected target MCP."""
from __future__ import annotations

from typing import Any, Callable

from ..mcp.execution_contracts import ApplyExecutionOutput, ApplyPageRequest
from .ports import ReceiptStore
from .receipt_models import (
    CommitStatus, CursorConflictError, ImportOutcome, ImportReceipt, PageCursor,
)
from .target_prepare import TargetPreparationError, prepare_target_call

_TARGET_FAILED = "target_failed"
_UNSUPPORTED = "unsupported_record"


def _receipt(record, target_digest: str, outcome: ImportOutcome, reason: str = ""):
    return ImportReceipt(
        tenant_id=record.tenant_id, owner_id=record.owner_id,
        adapter=record.adapter, source_fingerprint=record.source_fingerprint,
        kind=record.kind.value, source_record_id=record.source_record_id,
        target_digest=target_digest, outcome=outcome, reason_code=reason,
    )


def _typed_terminal(transport: Any) -> tuple[bool, dict[str, Any] | None] | None:
    if not isinstance(transport, dict) or transport.get("ok") is not True:
        return None
    native = transport.get("result")
    if not isinstance(native, dict):
        return None
    structured = native.get("structured_content")
    if not isinstance(structured, dict) or structured.get("schema_version") != "v1":
        return None
    if structured.get("ok") is False:
        return False, None
    data = structured.get("data")
    return (True, data) if isinstance(data, dict) else None


def _is_replay(data: dict[str, Any]) -> bool:
    return data.get("replayed") is True or data.get("outcome") in {
        "replayed", "unchanged", "deduped",
    }


def _domain_success(data: dict[str, Any] | None) -> bool:
    if not data or data.get("error"):
        return False
    return _is_replay(data) or data.get("imported") is True or data.get("outcome") in {
        "inserted", "enriched",
    }


def _failure(request: ApplyPageRequest, kind: SourceKind, offset: int, error: str,
             failed: int = 0, retryable: bool = False) -> ApplyExecutionOutput:
    return ApplyExecutionOutput(
        status="failed", kind=kind, processed=0,
        imported=0, skipped=0, failed=failed, next_offset=offset,
        retryable=retryable, error=error,
    )


def _next_page(receipts: ReceiptStore, request: ApplyPageRequest):
    last = (request.source_kinds[-1], None, 0)
    for index, kind in enumerate(request.source_kinds):
        cursor = receipts.load_cursor(
            request.tenant_id, request.owner_id, request.source_adapter,
            request.source_fingerprint, request.plan_digest, kind.value)
        offset = cursor.page_index if cursor else 0
        last = (kind, cursor, offset)
        page = receipts.list_plan_records(
            request.tenant_id, request.owner_id, request.source_adapter,
            request.source_fingerprint, request.plan_digest, kind,
            offset, request.page_size + 1)
        if page:
            more = len(page) > request.page_size or index < len(request.kinds) - 1
            return kind, cursor, offset, page[:request.page_size], more
    return last[0], last[1], last[2], [], False


def apply_plan_page(
    receipts: ReceiptStore, invoker: Callable[..., dict[str, Any]],
    envelope: dict[str, Any], request: ApplyPageRequest,
) -> ApplyExecutionOutput:
    """Apply the current cursor page; advance only after all calls settle."""
    plan = receipts.get_plan(
        request.tenant_id, request.owner_id, request.source_adapter,
        request.source_fingerprint, request.plan_digest)
    if plan is None or tuple(request.kinds) != plan.kinds:
        return _failure(
            request, request.source_kinds[0], 0, "migration_plan_unavailable")
    kind, cursor, offset, records, has_more = _next_page(receipts, request)
    if not records:
        return ApplyExecutionOutput(
            status="completed", kind=kind, processed=0,
            imported=0, skipped=0, failed=0, next_offset=offset,
            retryable=False, error="",
        )
    imported = skipped = failed = 0
    for record in records:
        try:
            call = prepare_target_call(record)
        except TargetPreparationError:
            commit = receipts.record_receipt(_receipt(
                record, record.payload_digest, ImportOutcome.SKIPPED, _UNSUPPORTED))
            if commit.status is CommitStatus.CONFLICT:
                return _failure(request, kind, offset, "migration_receipt_conflict")
            skipped += 1
            continue
        digest = f"sha256:{call.arguments.target_digest}"
        prior = receipts.find_receipt(
            record.tenant_id, record.owner_id, record.adapter,
            record.source_fingerprint, record.kind.value, record.source_record_id)
        if prior is not None and prior.outcome.is_settled:
            if prior.target_digest != digest:
                return _failure(request, kind, offset, "migration_receipt_conflict")
            skipped += 1
            continue
        try:
            transport = invoker(
                {"brick_name": call.brick, "tool_name": call.tool},
                arguments=call.invocation_arguments(),
                idempotency_key=f"migration:{record.source_record_id}",
                envelope=envelope, migration_import=call.migration_binding(),
            )
        except Exception:  # noqa: BLE001 — fixed safe transport failure
            return _failure(
                request, kind, offset, "migration_target_unavailable", retryable=True)
        terminal = _typed_terminal(transport)
        if terminal is None:
            return _failure(
                request, kind, offset, "migration_target_unavailable", retryable=True)
        typed_ok, data = terminal
        success = typed_ok and _domain_success(data)
        outcome = (ImportOutcome.SKIPPED if success and _is_replay(data or {})
                   else ImportOutcome.IMPORTED if success else ImportOutcome.FAILED)
        commit = receipts.record_receipt(_receipt(
            record, digest, outcome, "" if success else _TARGET_FAILED))
        if commit.status is CommitStatus.CONFLICT:
            return _failure(request, kind, offset, "migration_receipt_conflict")
        if success:
            skipped += outcome is ImportOutcome.SKIPPED
            imported += outcome is ImportOutcome.IMPORTED
        else:
            failed += 1
    if failed:
        return _failure(
            request, kind, offset, "migration_target_failed", failed=failed, retryable=True)
    next_offset = offset + len(records)
    next_cursor = PageCursor(
        tenant_id=request.tenant_id, owner_id=request.owner_id,
        adapter=request.source_adapter, source_fingerprint=request.source_fingerprint,
        plan_digest=request.plan_digest, kind=kind.value,
        page_index=next_offset, revision=cursor.revision if cursor else 1)
    try:
        receipts.save_cursor(
            next_cursor, expected_revision=cursor.revision if cursor else None)
    except CursorConflictError:
        return _failure(
            request, kind, offset, "migration_cursor_conflict", retryable=True)
    return ApplyExecutionOutput(
        status="partial" if has_more else "completed", kind=kind,
        processed=len(records), imported=imported, skipped=skipped, failed=0,
        next_offset=next_offset, retryable=has_more, error="",
    )


__all__ = ["apply_plan_page"]
