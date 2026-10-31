"""Intent/receipt recovery behavior for lifecycle-owned native effects."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext
from factory.machine_learning.runtime.can_lifecycle_canonical import effect_identity


def _context(root: Path) -> CanLifecycleContext:
    return CanLifecycleContext("train@v1", "a" * 64, LocalCanLifecycleStore(root))


def test_reconcile_hit_persists_receipt_and_replays_across_restart(tmp_path: Path):
    calls = []
    first = _context(tmp_path).effect(
        "model@v1", {"ref": "exact"},
        lambda effect_id: calls.append(("reconcile", effect_id)) or {"model@v1": "adopted"},
        lambda _effect_id: pytest.fail("reconcile hit must not execute"),
    )
    replay = _context(tmp_path).effect(
        "model@v1", {"ref": "exact"},
        lambda _effect_id: pytest.fail("receipt replay must not reconcile"),
        lambda _effect_id: pytest.fail("receipt replay must not execute"),
    )
    assert first == replay == {"model@v1": "adopted"}
    assert [item[0] for item in calls] == ["reconcile"]


def test_reconcile_miss_executes_once_then_receipt_replays(tmp_path: Path):
    calls = []
    context = _context(tmp_path)
    first = context.effect(
        "model@v1", {"ref": "exact"},
        lambda _effect_id: calls.append("miss") or None,
        lambda _effect_id: calls.append("execute") or {"model@v1": "trained"},
    )
    replay = context.effect(
        "model@v1", {"ref": "exact"},
        lambda _effect_id: pytest.fail("receipt replay must not reconcile"),
        lambda _effect_id: pytest.fail("receipt replay must not execute"),
    )
    assert first == replay == {"model@v1": "trained"}
    assert calls == ["miss", "execute"]


def test_same_effect_unit_rejects_divergent_intent(tmp_path: Path):
    context = _context(tmp_path)
    context.effect("model@v1", {"ref": "one"}, lambda _id: {"ok": True}, lambda _id: {})
    with pytest.raises(ValueError, match="immutable lifecycle object already differs"):
        context.effect("model@v1", {"ref": "two"}, lambda _id: {}, lambda _id: {})


@pytest.mark.parametrize("kind", ["intent", "receipt"])
def test_tampered_effect_journal_is_rejected_on_restart(tmp_path: Path, kind: str):
    context = _context(tmp_path)
    context.effect("model@v1", {"ref": "exact"}, lambda _id: {"ok": True}, lambda _id: {})
    effect_id = effect_identity("train@v1", "a" * 64, "model@v1")
    path = tmp_path / "can_lifecycle" / "effects" / f"{effect_id}.{kind}.json"
    path.chmod(0o644)
    value = json.loads(path.read_bytes())
    digest_key = f"{kind}_sha256"
    value[digest_key] = "0" * 64
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ValueError, match="already differs|digest mismatch|writable"):
        _context(tmp_path).effect(
            "model@v1", {"ref": "exact"}, lambda _id: {}, lambda _id: {},
        )


def test_atomic_replace_and_immutable_creation_fsync_parent_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    import os
    import stat

    original = os.fsync
    synced_modes = []

    def observe(descriptor):
        synced_modes.append(os.fstat(descriptor).st_mode)
        original(descriptor)

    monkeypatch.setattr(os, "fsync", observe)
    _context(tmp_path).effect(
        "model@v1", {"ref": "exact"}, lambda _id: {"ok": True}, lambda _id: {},
    )
    assert any(stat.S_ISDIR(mode) for mode in synced_modes)
    assert any(stat.S_ISREG(mode) for mode in synced_modes)


def test_store_rejects_symlinked_lifecycle_root(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "can_lifecycle").symlink_to(outside, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        LocalCanLifecycleStore(tmp_path)
    assert list(outside.iterdir()) == []


def test_store_rejects_hardlinked_immutable_journal(tmp_path: Path):
    context = _context(tmp_path)
    context.effect("model@v1", {"ref": "exact"}, lambda _id: {"ok": True}, lambda _id: {})
    effect_id = effect_identity("train@v1", "a" * 64, "model@v1")
    journal = tmp_path / "can_lifecycle/effects" / f"{effect_id}.intent.json"
    linked = tmp_path / "linked-intent.json"
    linked.hardlink_to(journal)
    with pytest.raises(ValueError, match="single-link"):
        _context(tmp_path).effect(
            "model@v1", {"ref": "exact"}, lambda _id: {}, lambda _id: {},
        )


def test_store_detects_pinned_directory_and_lock_substitution(tmp_path: Path):
    import hashlib
    import shutil

    store = LocalCanLifecycleStore(tmp_path)
    locks = tmp_path / "can_lifecycle/locks"
    displaced = tmp_path / "displaced-locks"
    locks.rename(displaced)
    locks.mkdir()
    with pytest.raises(ValueError, match="directory substituted"):
        with store.lock("train@v1", "attempt"):
            pass

    fresh = LocalCanLifecycleStore(tmp_path / "fresh")
    key = hashlib.sha256(b"train@v1\0attempt").hexdigest()
    lock = tmp_path / "fresh/can_lifecycle/locks" / f"{key}.lock"
    target = tmp_path / "target"
    target.write_text("")
    lock.symlink_to(target)
    with pytest.raises((OSError, ValueError)):
        with fresh.lock("train@v1", "attempt"):
            pass
    shutil.rmtree(displaced)
