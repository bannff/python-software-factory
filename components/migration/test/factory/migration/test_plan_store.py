"""Immutable owner-scoped Migration plan-material persistence tests."""
from __future__ import annotations

import json

import pytest
from hypothesis import given, strategies as st

from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.receipt_models import CommitStatus, PlanIdentity
from factory.migration.runtime.source_models import SafeMemory, SourceKind, identity_of
from factory.storage.interface import StorageRuntime


def _plan(owner: str = "owner") -> PlanIdentity:
    return PlanIdentity(
        tenant_id="tenant", owner_id=owner, adapter="kirocrew-v1",
        source_fingerprint="sha256:" + "a" * 32,
        plan_digest="sha256:" + "b" * 32, kinds=("memory",),
    )


def _record(plan: PlanIdentity, content: str = "remember this") -> PlanRecord:
    payload = SafeMemory(
        kind="semantic", identity=identity_of("semantic", "key"),
        key="key", content=content,
    )
    return PlanRecord.from_source(plan, SourceKind.MEMORY, payload)


@pytest.fixture
def store(tmp_path):
    yield SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "plans.db")))


def test_plan_records_commit_replay_conflict_and_page(store) -> None:
    plan = _plan()
    first = _record(plan)
    assert store.save_plan_records(plan, (first,))[0].status is CommitStatus.COMMITTED
    assert store.save_plan_records(plan, (first,))[0].status is CommitStatus.REPLAYED
    changed = _record(plan, "changed")
    conflict = store.save_plan_records(plan, (changed,))[0]
    assert conflict.status is CommitStatus.CONFLICT
    assert conflict.record.payload.content == "remember this"
    assert store.list_plan_records(
        **plan.model_dump(exclude={"kinds"}), kind=SourceKind.MEMORY,
        offset=0, limit=100,
    ) == [first]


def test_plan_records_are_owner_scoped(store) -> None:
    mine = _plan("owner-a")
    theirs = _plan("owner-b")
    store.save_plan_records(mine, (_record(mine),))
    assert store.list_plan_records(
        **theirs.model_dump(exclude={"kinds"}), kind=SourceKind.MEMORY,
        offset=0, limit=100,
    ) == []


def test_plan_material_survives_restart(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    plan = _plan()
    first = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    first.save_plan_records(plan, (_record(plan),))
    first.bind_plan(plan)
    reopened = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    assert reopened.get_plan(**plan.model_dump(exclude={"kinds"})) == plan
    records = reopened.list_plan_records(
        **plan.model_dump(exclude={"kinds"}), kind=SourceKind.MEMORY,
        offset=0, limit=100,
    )
    assert records == [_record(plan)]


@given(st.text(min_size=1, max_size=200).filter(lambda value: value.strip()))
def test_payload_json_round_trip_is_canonical(content: str) -> None:
    record = _record(_plan(), content)
    raw = json.loads(record.payload_json)
    assert raw["content"] == content
    assert PlanRecord.model_validate(record.model_dump()) == record


def test_unselected_record_kind_is_refused(store) -> None:
    plan = _plan().model_copy(update={"kinds": ("lessons",)})
    with pytest.raises(ValueError, match="kind not selected"):
        store.save_plan_records(plan, (_record(plan),))


def test_mismatched_plan_authority_is_refused(store) -> None:
    mine = _plan("owner-a")
    forged = _record(_plan("owner-b"))
    with pytest.raises(ValueError, match="authority mismatch"):
        store.save_plan_records(mine, (forged,))
