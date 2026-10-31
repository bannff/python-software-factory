"""Sweeper reap mechanics: collect, recheck-under-lock, lock contention, failure reporting."""

from __future__ import annotations

import fcntl
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.sandbox.runtime.adapters import uds_mount

from ._uds_mount_helpers import _PS_LINES, _inspect_state


def test_sweep_orphans_returns_reaped_list_with_policy_ids() -> None:
    def fake_run(cmd, timeout=30):  # noqa: ANN001
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, _PS_LINES, ""
        if cmd[:2] == ["docker", "inspect"]:
            labels = {"factory.sandbox": "true"}
            if cmd[-1] == "a" * 64:
                labels["factory.workload"] = "workload:launch-1"
            return 0, _inspect_state(
                cmd[-1], status="exited" if cmd[-1] == "a" * 64 else "dead",
                labels=labels,
            ), ""
        return 0, "", ""

    reaped = uds_mount.sweep_orphans(fake_run)
    assert reaped == [
        {"container_id": "a" * 64, "policy_id": "workload:launch-1", "reason": "exited"},
        {"container_id": "b" * 64, "policy_id": None, "reason": "dead"},
    ]


def test_sweep_orphans_reads_labels_before_removal() -> None:
    """CRITICAL: labels must be read (ps) BEFORE rm -f, else they vanish."""
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, _PS_LINES, ""
        if cmd[:2] == ["docker", "inspect"]:
            labels = {"factory.sandbox": "true"}
            if cmd[-1] == "a" * 64:
                labels["factory.workload"] = "workload:launch-1"
            return 0, _inspect_state(cmd[-1], labels=labels), ""
        return 0, "", ""

    uds_mount.sweep_orphans(fake_run)
    ps_idx = next(i for i, c in enumerate(calls) if c[:3] == ["docker", "ps", "-a"])
    rm_idx = next(i for i, c in enumerate(calls) if c[:3] == ["docker", "rm", "-f"])
    assert ps_idx < rm_idx, "labels/status read must precede rm -f"
    assert ["docker", "rm", "-f", "a" * 64] in calls
    assert ["docker", "rm", "-f", "b" * 64] in calls


def test_sweeper_rechecks_state_under_lock_before_removal() -> None:
    container_id = "3" * 64
    ps = f"{container_id}\tExited (0) 20 minutes ago\tfactory.sandbox=true\n"
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, "", "") if "status=running" in cmd else (0, ps, "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(container_id, status="running"), ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(fake_run) == []
    assert ["docker", "rm", "-f", container_id] not in calls


def test_sweeper_rechecks_exact_full_id_under_lock() -> None:
    container_id = "6" * 64
    ps = f"{container_id}\tDead\tfactory.sandbox=true\n"
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, "", "") if "status=running" in cmd else (0, ps, "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state("7" * 64, status="dead"), ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(fake_run) == []
    assert ["docker", "rm", "-f", container_id] not in calls


def test_sweeper_rechecks_timeout_after_restart_under_lock() -> None:
    container_id = "4" * 64
    labels = {
        "factory.sandbox": "true",
        "factory.sandbox.secret_output_suppressed": "true",
        "factory.sandbox.timeout_seconds": "3600",
    }
    ps = f"{container_id}\tUp 2 hours\t" + ",".join(
        f"{key}={value}" for key, value in labels.items()
    ) + "\n"
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, ps, "") if "status=running" in cmd else (0, "", "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(
                container_id, status="running", started="2026-09-30T11:59:00Z",
                labels=labels,
            ), ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(
        fake_run, now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
    ) == []
    assert ["docker", "rm", "-f", container_id] not in calls


def test_sweeper_skips_collector_lock_then_reaps_after_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SANDBOX_TMP_ROOT", str(tmp_path))
    container_id = "d" * 64
    ps = f"{container_id}\tExited (0) 20 minutes ago\tfactory.sandbox=true\n"
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, ps, ""
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(container_id), ""
        return 0, "", ""

    lock_dir = tmp_path / "collector-locks"
    lock_dir.mkdir(mode=0o700)
    lock_file = lock_dir / f"{container_id}.lock"
    lock_file.touch(mode=0o600)
    with lock_file.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert uds_mount.sweep_orphans(fake_run) == []
        assert ["docker", "rm", "-f", container_id] not in calls
        fcntl.flock(handle, fcntl.LOCK_UN)

    assert uds_mount.sweep_orphans(fake_run) == [
        {"container_id": container_id, "policy_id": None, "reason": "exited"}
    ]
    assert lock_file.exists()


def test_sweeper_does_not_report_failed_removal() -> None:
    container_id = "f" * 64

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, f"{container_id}\tDead\tfactory.sandbox=true\n", ""
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(container_id, status="dead"), ""
        return 1, "", "removal failed"

    assert uds_mount.sweep_orphans(fake_run) == []
