"""Secret-output-suppressed container evidence hold and labeled-timeout reaping."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.sandbox.runtime.adapters import uds_mount

from ._uds_mount_helpers import _inspect_state


def test_secret_evidence_container_is_retained_briefly_then_reaped() -> None:
    ps = (
        f"{'c' * 64}\tExited (0) 1 minute ago\t"
        "factory.sandbox=true,factory.sandbox.secret_output_suppressed=true\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, ps, ""
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(
                "c" * 64, finished="2026-09-30T12:00:00Z",
                labels={
                    "factory.sandbox": "true",
                    "factory.sandbox.secret_output_suppressed": "true",
                },
            ), ""
        return 0, "", ""

    now = datetime(2026, 9, 30, 12, 5, tzinfo=timezone.utc)
    assert uds_mount.sweep_orphans(fake_run, now=now) == []
    assert ["docker", "rm", "-f", "c" * 64] not in calls

    later = datetime(2026, 9, 30, 12, 11, tzinfo=timezone.utc)
    assert uds_mount.sweep_orphans(fake_run, now=later) == [
        {"container_id": "c" * 64, "policy_id": None, "reason": "exited"}
    ]
    assert ["docker", "rm", "-f", "c" * 64] in calls


@pytest.mark.parametrize("inspect_code,finished_at", [
    (1, "2026-09-30T10:00:00Z"),
    (0, "not-a-timestamp"),
])
def test_secret_evidence_hold_skips_when_exit_time_unverified(
    inspect_code: int, finished_at: str,
) -> None:
    ps = (
        f"{'c' * 64}\tExited (0) 1 minute ago\t"
        "factory.sandbox=true,factory.sandbox.secret_output_suppressed=true\n"
    )

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, ps, ""
        if cmd[:2] == ["docker", "inspect"]:
            return inspect_code, _inspect_state(
                "c" * 64, finished=finished_at,
                labels={
                    "factory.sandbox": "true",
                    "factory.sandbox.secret_output_suppressed": "true",
                },
            ), "inspect unavailable" if inspect_code else ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(fake_run) == []


def test_sweeper_ignores_flattened_labels_for_secret_hold() -> None:
    container_id = "5" * 64
    ps = (
        f"{container_id}\tExited (0) 20 minutes ago\t"
        "factory.sandbox=true,factory.workload=foo,"
        "factory.sandbox.secret_output_suppressed=false\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, "", "") if "status=running" in cmd else (0, ps, "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(
                container_id, finished="2026-09-30T11:59:00Z",
                labels={
                    "factory.sandbox": "true",
                    "factory.workload": "foo,factory.sandbox.secret_output_suppressed=false",
                    "factory.sandbox.secret_output_suppressed": "true",
                },
            ), ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(
        fake_run, now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
    ) == []
    assert ["docker", "rm", "-f", container_id] not in calls


def test_sweeper_reaps_secret_running_past_labeled_timeout() -> None:
    container_id = "1" * 64
    ps = (
        f"{container_id}\tUp 2 hours\t"
        "factory.sandbox=true,factory.sandbox.secret_output_suppressed=true,"
        "factory.sandbox.timeout_seconds=3600\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, ps, "") if "status=running" in cmd else (0, "", "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(
                container_id, status="running", started="2026-09-30T10:00:00Z",
                labels={
                    "factory.sandbox": "true",
                    "factory.sandbox.secret_output_suppressed": "true",
                    "factory.sandbox.timeout_seconds": "3600",
                },
            ), ""
        return 0, "", ""

    now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    assert uds_mount.sweep_orphans(fake_run, now=now) == [
        {"container_id": container_id, "policy_id": None, "reason": "timeout"}
    ]
    assert ["docker", "rm", "-f", container_id] in calls


@pytest.mark.parametrize("timeout_label,started_at", [
    ("", "2026-09-30T10:00:00Z"),
    ("invalid", "2026-09-30T10:00:00Z"),
    ("86401", "2026-09-30T10:00:00Z"),
    ("3600", "unknown"),
    ("3600", "2026-09-30T11:30:00Z"),
])
def test_sweeper_preserves_running_secret_without_verified_expiry(
    timeout_label: str, started_at: str,
) -> None:
    container_id = "2" * 64
    timeout_part = (
        f",factory.sandbox.timeout_seconds={timeout_label}" if timeout_label else ""
    )
    ps = (
        f"{container_id}\tUp 2 hours\t"
        f"factory.sandbox=true,factory.sandbox.secret_output_suppressed=true{timeout_part}\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return (0, ps, "") if "status=running" in cmd else (0, "", "")
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(
                container_id, status="running", started=started_at,
                labels={
                    "factory.sandbox": "true",
                    "factory.sandbox.secret_output_suppressed": "true",
                    **({"factory.sandbox.timeout_seconds": timeout_label} if timeout_label else {}),
                },
            ), ""
        return 0, "", ""

    now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    assert uds_mount.sweep_orphans(fake_run, now=now) == []
    assert ["docker", "rm", "-f", container_id] not in calls
