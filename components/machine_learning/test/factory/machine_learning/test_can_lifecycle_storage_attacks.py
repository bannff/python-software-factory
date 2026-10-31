"""Adversarial filesystem tests for local CAN lifecycle authority."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest
from pydantic import BaseModel, ConfigDict

from factory.machine_learning.runtime.adapters import local_can_objects
from factory.machine_learning.runtime.adapters.local_can_lifecycle import LocalCanLifecycleStore
from factory.machine_learning.runtime.can_lifecycle_canonical import canonical_json, effect_identity
from factory.machine_learning.runtime.can_lifecycle_contracts import record_digest
from factory.machine_learning.runtime.training_lifecycle_coordinator import (
    CanLifecycleContext, CanLifecycleCoordinator,
)

_OP = "storage-attack@v1"
_SELF = {"self": _OP}


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    ok: bool


def _published(root: Path):
    store = LocalCanLifecycleStore(root)
    result = CanLifecycleCoordinator(store).run(
        _OP, {"attempt_id": "attempt", "value": 1}, _SELF,
        lambda _context: {"ok": True}, _Result,
    )
    record = store.load(_OP, "attempt")
    assert record and record.terminal_uri
    context = CanLifecycleContext(_OP, "a" * 64, store)
    context.effect("probe@v1", {"ref": "exact"}, lambda _id: None,
                   lambda _id: {"ok": True})
    effect_id = effect_identity(_OP, "a" * 64, "probe@v1")
    key = hashlib.sha256(f"{_OP}\0attempt".encode()).hexdigest()
    paths = {
        "attempt": root / "can_lifecycle/attempts" / f"{key}.json",
        "terminal": Path(record.terminal_uri.removeprefix("file://")),
        "intent": root / "can_lifecycle/effects" / f"{effect_id}.intent.json",
        "receipt": root / "can_lifecycle/effects" / f"{effect_id}.receipt.json",
    }
    return store, record, effect_id, paths, result


def _read(store, record, effect_id, kind):
    if kind == "attempt":
        return store.load(_OP, "attempt")
    if kind == "terminal":
        return store.load_terminal(record)
    if kind == "intent":
        return store.load_intent(effect_id)
    return store.load_receipt(effect_id)


@pytest.mark.parametrize("kind", ["attempt", "terminal", "intent", "receipt"])
@pytest.mark.parametrize("attack", ["symlink", "hardlink"])
def test_authority_objects_reject_links(tmp_path: Path, kind: str, attack: str):
    store, record, effect_id, paths, _ = _published(tmp_path)
    path = paths[kind]
    outside = tmp_path / f"outside-{kind}"
    if attack == "symlink":
        path.rename(outside)
        path.symlink_to(outside)
    else:
        outside.hardlink_to(path)
    with pytest.raises((OSError, ValueError), match="regular|single-link|symlink|object"):
        _read(store, record, effect_id, kind)


@pytest.mark.parametrize("kind", ["terminal", "intent", "receipt"])
def test_immutable_authority_objects_reject_writable_mode(tmp_path: Path, kind: str):
    store, record, effect_id, paths, _ = _published(tmp_path)
    paths[kind].chmod(0o600)
    with pytest.raises(ValueError, match="writable"):
        _read(store, record, effect_id, kind)


def test_symlinked_receipt_rejects_valid_recomputed_self_hash(tmp_path: Path):
    store, _, effect_id, paths, _ = _published(tmp_path)
    value = json.loads(paths["receipt"].read_bytes())
    value["output"] = {"ok": False}
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = hashlib.sha256(canonical_json(body)).hexdigest()
    target = tmp_path / "valid-recomputed-receipt.json"
    target.write_bytes(canonical_json(value)); target.chmod(0o400)
    paths["receipt"].unlink(); paths["receipt"].symlink_to(target)
    with pytest.raises((OSError, ValueError), match="regular|symlink"):
        store.load_receipt(effect_id)


@pytest.mark.parametrize("category", ["attempts", "terminals", "effects", "locks"])
def test_pinned_category_substitution_fails_closed(tmp_path: Path, category: str):
    store, record, effect_id, paths, _ = _published(tmp_path)
    original = tmp_path / "can_lifecycle" / category
    displaced = tmp_path / f"displaced-{category}"
    original.rename(displaced); original.mkdir()
    with pytest.raises(ValueError, match="directory substituted"):
        if category == "attempts": store.load(_OP, "attempt")
        elif category == "terminals": store.load_terminal(record)
        elif category == "effects": store.load_receipt(effect_id)
        else:
            with store.lock(_OP, "attempt"): pass


def test_symlinked_ancestor_and_peer_writable_root_are_rejected(tmp_path: Path):
    real = tmp_path / "real"; real.mkdir()
    alias = tmp_path / "alias"; alias.symlink_to(real, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        LocalCanLifecycleStore(alias / "child")
    writable = tmp_path / "writable"; writable.mkdir(mode=0o777); writable.chmod(0o777)
    with pytest.raises(ValueError, match="non-writable by peers"):
        LocalCanLifecycleStore(writable)


def test_attempt_key_and_terminal_payload_must_match_lookup(tmp_path: Path):
    store, record, _, paths, _ = _published(tmp_path)
    target_id = "target"
    target_key = hashlib.sha256(f"{_OP}\0{target_id}".encode()).hexdigest()
    target_path = paths["attempt"].with_name(f"{target_key}.json")
    shutil.copyfile(paths["attempt"], target_path)
    with pytest.raises(ValueError, match="lookup key"):
        store.load(_OP, target_id)

    values = record.model_dump(mode="json")
    values["attempt_id"] = target_id
    values["record_sha256"] = record_digest(values)
    target_path.write_bytes(canonical_json(values))
    target_record = store.load(_OP, target_id)
    assert target_record
    with pytest.raises(ValueError, match="terminal identity"):
        store.load_terminal(target_record)


def test_effect_files_must_match_effect_lookup_key(tmp_path: Path):
    store, _, effect_id, paths, _ = _published(tmp_path)
    forged = "f" * 64
    for kind in ("intent", "receipt"):
        shutil.copyfile(paths[kind], paths[kind].with_name(f"{forged}.{kind}.json"))
        paths[kind].with_name(f"{forged}.{kind}.json").chmod(0o400)
    with pytest.raises(ValueError, match="lookup key"):
        store.load_intent(forged)


def test_read_rejects_name_swap_before_open(tmp_path: Path, monkeypatch):
    path = tmp_path / "object"; path.write_bytes(b"trusted")
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    replacement = tmp_path / "replacement"; replacement.write_bytes(b"trusted")
    real_open = local_can_objects.os.open
    swapped = False

    def open_with_swap(name, flags, *args, **kwargs):
        nonlocal swapped
        if name == "object" and not swapped:
            swapped = True; os.replace(replacement, path)
        return real_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(local_can_objects.os, "open", open_with_swap)
    try:
        with pytest.raises(ValueError, match="raced before read"):
            local_can_objects.read_regular(directory, "object")
    finally:
        os.close(directory)


def test_read_rejects_name_swap_after_read(tmp_path: Path, monkeypatch):
    path = tmp_path / "object"; path.write_bytes(b"trusted")
    replacement = tmp_path / "replacement"; replacement.write_bytes(b"trusted")
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    real_stat = local_can_objects.os.stat
    calls = 0

    def stat_with_swap(name, *args, **kwargs):
        nonlocal calls
        if name == "object":
            calls += 1
            if calls == 2: os.replace(replacement, path)
        return real_stat(name, *args, **kwargs)

    monkeypatch.setattr(local_can_objects.os, "stat", stat_with_swap)
    try:
        with pytest.raises(ValueError, match="substituted after read"):
            local_can_objects.read_regular(directory, "object")
    finally:
        os.close(directory)


def test_immutable_publication_rejects_final_name_swap(tmp_path: Path, monkeypatch):
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    real_link = local_can_objects.os.link

    def link_then_swap(src, dst, **kwargs):
        real_link(src, dst, **kwargs)
        os.unlink(dst, dir_fd=directory)
        attacker = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                           0o400, dir_fd=directory)
        os.write(attacker, b"attacker"); os.close(attacker)

    monkeypatch.setattr(local_can_objects.os, "link", link_then_swap)
    try:
        with pytest.raises(ValueError, match="changed during publication"):
            local_can_objects.write_immutable(directory, "object", b"trusted")
    finally:
        os.close(directory)


def test_active_lock_name_replacement_cannot_overlap_critical_sections(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time

    store = LocalCanLifecycleStore(tmp_path)
    entered = threading.Event(); release = threading.Event(); second_entered = threading.Event()
    key = hashlib.sha256(f"{_OP}\0attempt".encode()).hexdigest()
    lock_path = tmp_path / "can_lifecycle/locks" / f"{key}.lock"

    def first():
        with pytest.raises(ValueError, match="lock was substituted"):
            with store.lock(_OP, "attempt"):
                entered.set(); release.wait(timeout=2)

    def second():
        with store.lock(_OP, "attempt"):
            second_entered.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(first)
        assert entered.wait(timeout=2)
        lock_path.unlink(); lock_path.write_text("")
        two = pool.submit(second)
        time.sleep(0.05)
        assert not second_entered.is_set()
        release.set()
        one.result(timeout=2); two.result(timeout=2)
    assert second_entered.is_set()
