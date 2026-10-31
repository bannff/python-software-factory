"""Migration preview runtime tests over trusted fixtures and durable plans."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.preview import PreviewRuntime, PreviewUnavailable
from factory.migration.runtime.receipt_models import CommitStatus
from factory.migration.runtime.source_models import SourceKind
from factory.storage.interface import StorageRuntime


def _source(root: Path) -> None:
    root.mkdir()
    (root / "lessons.jsonl").write_text(json.dumps({
        "rule": "Use typed tools token=super-secret-value", "category": "tool",
    }) + "\n")
    (root / "crons.json").write_text(json.dumps({
        "version": 2, "jobs": [{
            "name": "daily", "message": "review", "approval_mode": "auto",
            "schedule": {"kind": "every", "every_secs": 300},
        }],
    }))
    memory = root / "workspace" / "memory"
    memory.mkdir(parents=True)
    (memory / "preferences.md").write_text("Prefer concise reports.\n")


def _runtime(tmp_path: Path) -> PreviewRuntime:
    root = tmp_path / "crew"
    _source(root)
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "migration.db")))
    return PreviewRuntime(root, store)


def test_preview_is_redacted_bounded_and_replayable(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    kinds = (SourceKind.LESSONS, SourceKind.SCHEDULES, SourceKind.MARKDOWN)
    first = runtime.preview("tenant", "owner", kinds)
    assert first.status is CommitStatus.COMMITTED
    assert first.plan.kinds == ("lessons", "schedules", "markdown")
    assert {report.kind for report in first.reports} == set(kinds)
    assert all("super-secret-value" not in sample.sample for sample in first.samples)
    assert any("[redacted]" in sample.sample for sample in first.samples)
    for kind in kinds:
        records = runtime.receipts.list_plan_records(
            tenant_id="tenant", owner_id="owner", adapter=first.plan.adapter,
            source_fingerprint=first.plan.source_fingerprint,
            plan_digest=first.plan.plan_digest, kind=kind, offset=0, limit=100)
        assert len(records) == 1
    assert runtime.preview("tenant", "owner", kinds).status is CommitStatus.REPLAYED


def test_different_kind_selections_create_distinct_plans(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    lessons = runtime.preview("tenant", "owner", (SourceKind.LESSONS,))
    schedules = runtime.preview("tenant", "owner", (SourceKind.SCHEDULES,))
    assert lessons.plan.plan_digest != schedules.plan.plan_digest
    assert lessons.status is schedules.status is CommitStatus.COMMITTED


def test_source_change_creates_new_plan_without_mutating_old_material(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    first = runtime.preview("tenant", "owner", (SourceKind.LESSONS,))
    before = runtime.receipts.list_plan_records(
        tenant_id="tenant", owner_id="owner", adapter=first.plan.adapter,
        source_fingerprint=first.plan.source_fingerprint,
        plan_digest=first.plan.plan_digest, kind=SourceKind.LESSONS,
        offset=0, limit=100)
    (runtime.root / "lessons.jsonl").write_text(json.dumps({
        "rule": "Use the changed source", "category": "tool",
    }) + "\n")
    second = runtime.preview("tenant", "owner", (SourceKind.LESSONS,))
    after = runtime.receipts.list_plan_records(
        tenant_id="tenant", owner_id="owner", adapter=first.plan.adapter,
        source_fingerprint=first.plan.source_fingerprint,
        plan_digest=first.plan.plan_digest, kind=SourceKind.LESSONS,
        offset=0, limit=100)
    assert second.plan.plan_digest != first.plan.plan_digest
    assert after == before
    assert after[0].payload.rule.startswith("Use typed tools")


def test_preview_plan_is_owner_scoped(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    one = runtime.preview("tenant", "owner-1", (SourceKind.LESSONS,))
    two = runtime.preview("tenant", "owner-2", (SourceKind.LESSONS,))
    assert one.plan.owner_id == "owner-1" and two.plan.owner_id == "owner-2"
    assert one.status is two.status is CommitStatus.COMMITTED


def test_disabled_or_relative_source_fails_closed(tmp_path: Path) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "disabled.db")))
    for root in (None, Path("relative")):
        with pytest.raises(PreviewUnavailable, match="source unavailable"):
            PreviewRuntime(root, store).preview(
                "tenant", "owner", (SourceKind.MEMORY,))
