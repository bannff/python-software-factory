"""Proves the design consult's central claim: the EXISTING apply/target
engine (`apply_execution.py`, `target_prepare.py`) needs zero changes to
accept companion-x-v1-sourced records — it dispatches purely on payload
TYPE (SafeMemory/SafeLesson/SafeSchedule), never on the adapter string.
Row 54 Portability import half."""
from __future__ import annotations

from factory.migration.mcp.execution_contracts import ApplyPageRequest
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.apply_execution import apply_plan_page
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.receipt_models import ImportOutcome, PlanIdentity
from factory.migration.runtime.source_models import SafeMemory, SourceKind, identity_of


def _plan() -> PlanIdentity:
    return PlanIdentity(
        tenant_id="tenant", owner_id="owner", adapter="companion-x-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory",),
    )


def _record(plan: PlanIdentity) -> PlanRecord:
    payload = SafeMemory(
        kind="semantic", identity=identity_of("bundle-memory", "hello"),
        key="hello", content="hello from a companion-x-v1 bundle",
    )
    return PlanRecord.from_source(plan, SourceKind.MEMORY, payload)


def _success(*_args, **_kwargs):
    return {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": True,
        "data": {"imported": True, "outcome": "imported"},
    }}}


def test_a_companion_x_v1_record_applies_through_the_unmodified_engine(tmp_path):
    store = SqlReceiptStore(db_path=str(tmp_path / "apply.db"))
    plan = _plan()
    record = _record(plan)
    store.save_plan_records(plan, (record,))
    store.bind_plan(plan)

    calls: list[dict] = []

    def invoker(target, *, arguments, idempotency_key, envelope, migration_import=None):
        calls.append({"target": target, "arguments": arguments})
        return _success()

    request = ApplyPageRequest(
        tenant_id=plan.tenant_id, owner_id=plan.owner_id,
        source_adapter=plan.adapter, source_fingerprint=plan.source_fingerprint,
        plan_digest=plan.plan_digest, kinds=["memory"], page_size=10,
    )
    result = apply_plan_page(store, invoker, {}, request)

    assert result.status == "completed"
    assert result.imported == 1
    assert result.failed == 0
    # the SAME memory_import_record target tool was called — no new engine
    assert calls[0]["target"] == {"brick_name": "memory", "tool_name": "memory_import_record"}
    assert calls[0]["arguments"]["content"] == "hello from a companion-x-v1 bundle"

    # a real receipt was recorded with the correct adapter string threaded through
    receipt = store.find_receipt(
        plan.tenant_id, plan.owner_id, plan.adapter, plan.source_fingerprint,
        "memory", record.source_record_id,
    )
    assert receipt is not None
    assert receipt.outcome is ImportOutcome.IMPORTED
    assert receipt.adapter == "companion-x-v1"
