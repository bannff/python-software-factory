"""Properties and recovery invariants for ML-owned CAN lifecycle attempts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

from hypothesis import given, settings, strategies as st
from pydantic import BaseModel, ConfigDict
import pytest

from factory.machine_learning.runtime.adapters import local_can_files, local_can_objects
from factory.machine_learning.runtime.adapters.local_can_lifecycle import LocalCanLifecycleStore
from factory.machine_learning.runtime.can_lifecycle_canonical import (
    canonical_json, semantic_request,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleCoordinator
from factory.machine_learning.runtime.can_lifecycle_identity import (
    CONFORMANCE_UNIT, CONFORM_OPERATION, DATASET_BUNDLE_UNIT, ISSUE_OPERATION,
    LIGHTGBM_UNIT, PASSPORT_ISSUE_UNIT, PASSPORT_PROMOTE_UNIT, PROJECT_OPERATION,
    PROMOTE_OPERATION, TRAIN_OPERATION,
)
from factory.machine_learning.runtime.can_lifecycle_refs import CanTerminalRef

_OP = "generic-operation@v1"
_SELF = {"self": "generic-operation@v1"}


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class _ValueResult(_Result):
    value: int


class _OkResult(_Result):
    ok: bool


class _WinnerResult(_Result):
    winner: bool


class _PayloadResult(_Result):
    payload: dict[str, int]


@given(st.dictionaries(
    st.text(min_size=1, max_size=8),
    st.integers(min_value=-100, max_value=100), max_size=8,
))
@settings(max_examples=50)
def test_semantic_hash_is_order_independent_and_excludes_attempt(values):
    left = {"attempt_id": "first", "config": values, "refs": ["a", "b"]}
    right = {
        "refs": ["a", "b"], "config": dict(reversed(list(values.items()))),
        "attempt_id": "second",
    }
    assert semantic_request(_OP, left, _SELF)[1] == semantic_request(
        _OP, right, _SELF,
    )[1]


def test_hash_authenticates_refs_config_and_tool_identity():
    base = {"attempt_id": "a", "ref": {"digest": "1"}, "config": {"seed": 1}}
    digest = semantic_request(_OP, base, _SELF)[1]
    assert digest != semantic_request(
        _OP, {**base, "ref": {"digest": "2"}}, _SELF,
    )[1]
    assert digest != semantic_request(
        _OP, {**base, "config": {"seed": 2}}, _SELF,
    )[1]
    assert digest != semantic_request(_OP, base, {"self": "other@v1"})[1]
    with pytest.raises(ValueError, match="@v1"):
        semantic_request("unversioned", base, _SELF)


def test_equal_replay_conflict_restart_and_failed_terminal(tmp_path: Path):
    calls = []
    coordinator = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path))
    request = {"attempt_id": "attempt-1", "value": 1}

    def run(_context):
        calls.append(True)
        return {"value": 3}

    first = coordinator.run(_OP, request, _SELF, run, _ValueResult)
    replay = coordinator.run(_OP, request, _SELF, run, _ValueResult)
    restarted = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path)).run(
        _OP, request, _SELF, run, _ValueResult,
    )
    assert first == replay == restarted
    assert calls == [True]
    assert CanTerminalRef.model_validate(first["terminal_ref"]).operation == _OP
    conflict = coordinator.run(
        _OP, {"attempt_id": "attempt-1", "value": 2}, _SELF, run, _ValueResult,
    )
    assert conflict["status"] == "conflict" and calls == [True]

    failed = coordinator.run(
        "failure@v1", request, {"self": "failure@v1"},
        lambda _ctx: (_ for _ in ()).throw(RuntimeError("sealed failure")),
        _ValueResult,
    )
    assert failed["status"] == "failed"
    assert coordinator.run(
        "failure@v1", request, {"self": "failure@v1"},
        lambda _ctx: pytest.fail("failed terminal must replay"), _ValueResult,
    ) == failed


def test_tamper_and_cross_operation_terminal_refs_fail_closed(tmp_path: Path):
    store = LocalCanLifecycleStore(tmp_path)
    coordinator = CanLifecycleCoordinator(store)
    request = {"attempt_id": "tamper", "value": 1}
    result = coordinator.run(
        _OP, request, _SELF, lambda _ctx: {"ok": True}, _OkResult,
    )
    record = store.load(_OP, "tamper")
    assert record and record.terminal_uri
    path = Path(record.terminal_uri.removeprefix("file://"))
    path.chmod(0o600)
    value = json.loads(path.read_bytes()); value["ok"] = False
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="writable|digest"):
        coordinator.run(_OP, request, _SELF, lambda _ctx: {}, _OkResult)

    clean = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path / "clean")).run(
        _OP, request, _SELF, lambda _ctx: {"ok": True}, _OkResult,
    )
    ref = dict(clean["terminal_ref"]); ref["operation"] = "other@v1"
    from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext
    context = CanLifecycleContext("consumer@v1", "b" * 64, LocalCanLifecycleStore(tmp_path / "clean"))
    with pytest.raises(ValueError, match="crosses"):
        context.completed_terminal(ref, _OP)
    ref = dict(clean["terminal_ref"]); ref["terminal_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="exact completed"):
        context.completed_terminal(ref, _OP)


def test_concurrent_equal_attempt_executes_once(tmp_path: Path):
    coordinator = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path))
    calls = []

    def invoke():
        return coordinator.run(
            _OP, {"attempt_id": "race", "value": 1}, _SELF,
            lambda _ctx: calls.append(True) or {"winner": True}, _WinnerResult,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _index: invoke(), range(16)))
    assert calls == [True]
    assert all(result == results[0] for result in results)


def _terminal_bytes(store, operation: str, attempt_id: str) -> bytes:
    record = store.load(operation, attempt_id)
    assert record and record.terminal_uri
    return Path(record.terminal_uri.removeprefix("file://")).read_bytes()


@pytest.mark.parametrize("fails", [False, True])
def test_first_return_terminal_body_is_byte_equivalent_to_replay(tmp_path: Path, fails):
    store = LocalCanLifecycleStore(tmp_path)
    coordinator = CanLifecycleCoordinator(store)
    request = {"attempt_id": f"bytes-{fails}", "value": 1}

    def run(_context):
        if fails:
            raise RuntimeError("canonical failure")
        return {"payload": {"z": 1, "a": 2}}

    first = coordinator.run(_OP, request, _SELF, run, _PayloadResult)
    replay = coordinator.run(
        _OP, request, _SELF, lambda _context: pytest.fail("terminal must replay"),
        _PayloadResult,
    )
    assert first == replay
    body = {key: value for key, value in first.items() if key != "terminal_ref"}
    assert canonical_json(body) == _terminal_bytes(store, _OP, f"bytes-{fails}")


@pytest.mark.parametrize("reserved", [
    "schema_version", "operation", "status", "attempt_id", "request_sha256",
    "existing_request_sha256", "error", "terminal_ref",
])
def test_runner_results_cannot_override_reserved_envelope_keys(
    tmp_path: Path, reserved: str,
):
    result = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path)).run(
        _OP, {"attempt_id": reserved}, _SELF,
        lambda _context: {reserved: "attacker-controlled"}, _ValueResult,
    )
    assert result["status"] == "failed"
    assert "reserved envelope keys" in result["error"]
    assert result["operation"] == _OP


def test_runner_results_reject_undeclared_operation_fields(tmp_path: Path):
    result = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path)).run(
        _OP, {"attempt_id": "undeclared"}, _SELF,
        lambda _context: {"value": 3, "caller_trusted_body": {"forged": True}},
        _ValueResult,
    )
    assert result["status"] == "failed"
    assert "caller_trusted_body" in result["error"]
    assert "Extra inputs are not permitted" in result["error"]


def test_write_atomic_retains_fd_and_detects_final_name_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    real_replace = os.replace

    def swap(src, dst, *, src_dir_fd, dst_dir_fd):
        real_replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
        os.unlink(dst, dir_fd=dst_dir_fd)
        attacker = os.open(
            dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600, dir_fd=dst_dir_fd,
        )
        try:
            os.write(attacker, b"attacker")
        finally:
            os.close(attacker)

    monkeypatch.setattr(local_can_objects.os, "replace", swap)
    try:
        with pytest.raises(ValueError, match="swapped"):
            local_can_objects.write_atomic(directory, "attempt.json", b"trusted")
    finally:
        os.close(directory)


def test_secure_flag_absence_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delattr(local_can_files.os, "O_NOFOLLOW")
    with pytest.raises(RuntimeError, match="requires os.O_NOFOLLOW"):
        local_can_files._required_flag("O_NOFOLLOW")


def test_write_atomic_detects_same_content_swap_during_directory_fsync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = os.fsync
    swapped = False

    def fsync_with_swap(fd):
        nonlocal swapped
        real_fsync(fd)
        if fd == directory and not swapped:
            swapped = True
            os.unlink("attempt.json", dir_fd=directory)
            attacker = os.open(
                "attempt.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=directory,
            )
            try:
                os.write(attacker, b"trusted")
            finally:
                os.close(attacker)

    monkeypatch.setattr(local_can_objects.os, "fsync", fsync_with_swap)
    try:
        with pytest.raises(ValueError, match="finalizing"):
            local_can_objects.write_atomic(directory, "attempt.json", b"trusted")
    finally:
        os.close(directory)


@given(
    operation=st.sampled_from([
        TRAIN_OPERATION, ISSUE_OPERATION, CONFORM_OPERATION, PROMOTE_OPERATION,
        PROJECT_OPERATION,
    ]),
    unit=st.sampled_from([
        DATASET_BUNDLE_UNIT, LIGHTGBM_UNIT, PASSPORT_ISSUE_UNIT,
        CONFORMANCE_UNIT, PASSPORT_PROMOTE_UNIT,
    ]),
    attempt=st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,31}", fullmatch=True),
    can_id=st.integers(min_value=0, max_value=0x7FF),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=75)
def test_production_identities_are_stable_and_attempt_independent(
    operation, unit, attempt, can_id, seed,
):
    from factory.machine_learning.runtime.can_lifecycle_canonical import effect_identity

    request = {
        "attempt_id": attempt, "can_id": f"0x{can_id:X}",
        "config": {"seed": seed}, "refs": {"digest": "a" * 64},
    }
    alternate = {**request, "attempt_id": f"other-{attempt}"}
    left = semantic_request(operation, request, {"self": operation})[1]
    right = semantic_request(operation, alternate, {"self": operation})[1]
    assert left == right
    assert effect_identity(operation, left, unit) == effect_identity(operation, right, unit)
    assert effect_identity(operation, left, unit) != effect_identity(
        operation, left, f"{unit.removesuffix('@v1')}:other@v1",
    )


def test_equal_semantic_attempts_serialize_shared_effect(tmp_path: Path):
    import time
    from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext

    calls = []

    def invoke(attempt_id):
        context = CanLifecycleContext(
            "ml.train-can-portfolio@v1", "d" * 64,
            LocalCanLifecycleStore(tmp_path),
        )
        return context.effect(
            "lightgbm.train-can-id@v1", {"can_id": "0x1"},
            lambda _effect_id: None,
            lambda _effect_id: calls.append(attempt_id) or time.sleep(0.02) or {"ok": True},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, ["first", "second"]))
    assert results == [{"ok": True}, {"ok": True}]
    assert len(calls) == 1
