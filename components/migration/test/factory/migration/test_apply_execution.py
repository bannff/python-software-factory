"""Workflow-driven Migration page application tests."""
from __future__ import annotations

import pytest

from factory.migration.mcp.execution_contracts import ApplyPageRequest
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.apply_execution import apply_plan_page
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.receipt_models import ImportOutcome, PlanIdentity
from factory.migration.runtime.source_models import SafeLesson, SafeMemory, SourceKind, identity_of
from factory.storage.interface import StorageRuntime


def _plan() -> PlanIdentity:
    return PlanIdentity(
        tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory",),
    )


def _request(page_size: int = 1) -> ApplyPageRequest:
    plan = _plan()
    return ApplyPageRequest(
        tenant_id=plan.tenant_id, owner_id=plan.owner_id,
        source_adapter=plan.adapter, source_fingerprint=plan.source_fingerprint,
        plan_digest=plan.plan_digest, kinds=["memory"],
        page_size=page_size,
    )


def _record(plan: PlanIdentity, key: str) -> PlanRecord:
    payload = SafeMemory(
        kind="semantic", identity=identity_of("semantic", key),
        key=key, content=f"content {key}",
    )
    return PlanRecord.from_source(plan, SourceKind.MEMORY, payload)


def _store(tmp_path, count: int = 2) -> SqlReceiptStore:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "apply.db")))
    plan = _plan()
    records = tuple(_record(plan, f"key-{index}") for index in range(count))
    store.save_plan_records(plan, records)
    store.bind_plan(plan)
    return store


def _success(*_args, **_kwargs):
    return {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": True,
        "data": {"imported": True, "outcome": "imported"},
    }}}


def test_pages_advance_only_after_typed_target_terminal(tmp_path) -> None:
    store = _store(tmp_path)
    calls = []

    def invoke(target, **kwargs):
        calls.append((target, kwargs))
        return _success()

    first = apply_plan_page(store, invoke, {}, _request())
    second = apply_plan_page(store, invoke, {}, _request())
    third = apply_plan_page(store, invoke, {}, _request())
    assert (first.status, first.next_offset, first.retryable) == ("partial", 1, True)
    assert (second.status, second.next_offset) == ("completed", 2)
    assert (third.status, third.processed, third.next_offset) == ("completed", 0, 2)
    assert len(calls) == 2
    assert all(set(call[1]["migration_import"]) == {
        "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
        "plan_digest", "kind", "source_record_id", "target_digest",
    } for call in calls)
    assert len(store.list_receipts("tenant", "owner", "kirocrew-v1", "a" * 64)) == 2


def test_one_request_progresses_across_ordered_plan_kinds(tmp_path) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "multi.db")))
    plan = _plan().model_copy(update={"kinds": ("memory", "lessons")})
    memory = _record(plan, "memory")
    lesson_payload = SafeLesson(
        identity=identity_of("lesson", "rule"), rule="Keep exact evidence",
        origin="jsonl",
    )
    lesson = PlanRecord.from_source(plan, SourceKind.LESSONS, lesson_payload)
    store.save_plan_records(plan, (memory, lesson))
    store.bind_plan(plan)
    request = _request(page_size=10).model_copy(
        update={"kinds": ["memory", "lessons"]})
    routes = []

    def invoke(target, **_kwargs):
        routes.append(target["brick_name"])
        return _success()

    first = apply_plan_page(store, invoke, {}, request)
    second = apply_plan_page(store, invoke, {}, request)
    assert (first.status, first.kind) == ("partial", SourceKind.MEMORY)
    assert (second.status, second.kind) == ("completed", SourceKind.LESSONS)
    assert routes == ["memory", "lessons"]


def test_transport_failure_writes_no_receipt_or_cursor(tmp_path) -> None:
    store = _store(tmp_path, count=1)
    result = apply_plan_page(store, lambda *_a, **_k: {"ok": False}, {}, _request())
    assert result.status == "failed" and result.retryable is True
    assert result.error == "migration_target_unavailable"
    assert store.list_receipts("tenant", "owner", "kirocrew-v1", "a" * 64) == []
    assert store.load_cursor(
        "tenant", "owner", "kirocrew-v1", "a" * 64,
        _plan().plan_digest, "memory") is None


def test_typed_failure_receipt_retries_then_supersedes(tmp_path) -> None:
    store = _store(tmp_path, count=1)
    failed = {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": False, "error": "safe",
    }}}
    first = apply_plan_page(store, lambda *_a, **_k: failed, {}, _request())
    assert first.status == "failed" and first.error == "migration_target_failed"
    receipt = store.list_receipts("tenant", "owner", "kirocrew-v1", "a" * 64)[0]
    assert receipt.outcome is ImportOutcome.FAILED and receipt.revision == 1
    second = apply_plan_page(store, _success, {}, _request())
    receipt = store.list_receipts("tenant", "owner", "kirocrew-v1", "a" * 64)[0]
    assert second.status == "completed"
    assert receipt.outcome is ImportOutcome.IMPORTED and receipt.revision == 2


def test_typed_data_level_refusal_is_failed_and_retryable(tmp_path) -> None:
    store = _store(tmp_path, count=1)
    refused = {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": True,
        "data": {"imported": False, "error": "fixed safe error"},
    }}}
    result = apply_plan_page(store, lambda *_a, **_k: refused, {}, _request())
    receipt = store.list_receipts("tenant", "owner", "kirocrew-v1", "a" * 64)[0]
    assert result.status == "failed" and result.retryable is True
    assert receipt.outcome is ImportOutcome.FAILED


def test_missing_or_wrong_kind_plan_fails_without_invocation(tmp_path) -> None:
    store = _store(tmp_path, count=0)
    request = _request().model_copy(update={"kinds": ["lessons"]})
    result = apply_plan_page(store, _success, {}, request)
    assert result.status == "failed" and result.retryable is False
    assert result.error == "migration_plan_unavailable"


def test_request_is_strict_and_page_size_is_bounded() -> None:
    with pytest.raises(Exception):
        ApplyPageRequest.model_validate({**_request().model_dump(), "extra": True})
    with pytest.raises(Exception):
        _request(page_size=100)
    with pytest.raises(Exception):
        ApplyPageRequest.model_validate({
            **_request().model_dump(), "kinds": ["memory", "memory"],
        })
