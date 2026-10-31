"""migration.runtime.bundle_preview — companion-x-v1 bundle preview,
same receipt/plan engine as the kirocrew-v1 PreviewRuntime. Row 54
Portability import half."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.bundle_preview import BundlePreviewRuntime, BundlePreviewUnavailable
from factory.migration.runtime.receipt_models import CommitStatus


def _digest(payload) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"


def _write_bundle(path: Path, extra_kinds: dict | None = None) -> None:
    memory_records = [{"identity": "m1", "content": "hello world", "kind": "semantic", "tags": []}]
    kinds = {"memory": {"records": memory_records, "digest": _digest(memory_records)}}
    if extra_kinds:
        kinds.update(extra_kinds)
    bundle = {
        "bundle_version": 1, "adapter": "companion-x-v1",
        "producer": {"app": "companion-x", "kinds": list(kinds)},
        "content_digest": _digest(kinds), "kinds": kinds,
    }
    path.write_text(json.dumps(bundle))


def _resolver(tmp_path: Path):
    def resolve(bundle_ref: str) -> Path:
        return tmp_path / bundle_ref
    return resolve


def _runtime(tmp_path: Path) -> BundlePreviewRuntime:
    store = SqlReceiptStore(db_path=str(tmp_path / "migration.db"))
    return BundlePreviewRuntime(_resolver(tmp_path), store)


def test_previews_a_valid_bundle_and_binds_a_plan(tmp_path: Path):
    _write_bundle(tmp_path / "backup.cxbundle.json")
    runtime = _runtime(tmp_path)
    result = runtime.preview("tenant", "owner", "backup.cxbundle.json", None)
    assert result.status is CommitStatus.COMMITTED
    assert len(result.reports) == 1
    assert result.reports[0].eligible == 1
    assert result.unsupported_kinds == ()


def test_replaying_the_same_bundle_is_idempotent(tmp_path: Path):
    _write_bundle(tmp_path / "backup.cxbundle.json")
    runtime = _runtime(tmp_path)
    first = runtime.preview("tenant", "owner", "backup.cxbundle.json", None)
    second = runtime.preview("tenant", "owner", "backup.cxbundle.json", None)
    assert first.status is CommitStatus.COMMITTED
    assert first.plan.plan_digest == second.plan.plan_digest
    # the second identical preview replays the existing commit rather than
    # re-committing — this IS the idempotency guarantee, not a failure mode
    assert second.status is CommitStatus.REPLAYED


def test_disclosed_unsupported_kinds_are_reported_not_silently_dropped(tmp_path: Path):
    _write_bundle(tmp_path / "backup.cxbundle.json", extra_kinds={
        "kb": {"records": [{"identity": "d1", "content": "notes"}], "digest": _digest([{"identity": "d1", "content": "notes"}])},
    })
    runtime = _runtime(tmp_path)
    result = runtime.preview("tenant", "owner", "backup.cxbundle.json", None)
    assert result.unsupported_kinds == ("kb",)
    assert len(result.reports) == 1  # only memory was actually parsed


def test_selecting_specific_kinds_only_previews_those(tmp_path: Path):
    lesson_records = [{"identity": "l1", "rule": "always ask"}]
    _write_bundle(tmp_path / "backup.cxbundle.json", extra_kinds={
        "lessons": {"records": lesson_records, "digest": _digest(lesson_records)},
    })
    runtime = _runtime(tmp_path)
    result = runtime.preview("tenant", "owner", "backup.cxbundle.json", ("lessons",))
    assert [r.kind.value for r in result.reports] == ["lessons"]


def test_a_tampered_bundle_fails_before_any_plan_is_bound(tmp_path: Path):
    path = tmp_path / "backup.cxbundle.json"
    _write_bundle(path)
    raw = json.loads(path.read_text())
    raw["kinds"]["memory"]["records"][0]["content"] = "tampered"
    path.write_text(json.dumps(raw))
    runtime = _runtime(tmp_path)
    with pytest.raises(BundlePreviewUnavailable, match="migration_bundle_content_digest_mismatch"):
        runtime.preview("tenant", "owner", "backup.cxbundle.json", None)


def test_a_missing_bundle_raises_a_typed_error(tmp_path: Path):
    runtime = _runtime(tmp_path)
    # the test resolver returns any path unconditionally (real resolve_bundle_ref
    # separately checks existence and raises bundle_not_found before this point);
    # stage_bundle's own open-failure path is what's exercised here.
    with pytest.raises(BundlePreviewUnavailable, match="migration_bundle_unreadable"):
        runtime.preview("tenant", "owner", "missing.cxbundle.json", None)


def test_samples_are_redacted(tmp_path: Path):
    memory_records = [{"identity": "m1", "content": "token: super-secret-value-here", "kind": "semantic", "tags": []}]
    kinds = {"memory": {"records": memory_records, "digest": _digest(memory_records)}}
    bundle = {
        "bundle_version": 1, "adapter": "companion-x-v1",
        "producer": {"app": "companion-x", "kinds": ["memory"]},
        "content_digest": _digest(kinds), "kinds": kinds,
    }
    path = tmp_path / "backup.cxbundle.json"
    path.write_text(json.dumps(bundle))
    runtime = _runtime(tmp_path)
    result = runtime.preview("tenant", "owner", "backup.cxbundle.json", None)
    assert "super-secret-value-here" not in result.samples[0].sample
