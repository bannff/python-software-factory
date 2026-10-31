"""Sweeper owned-peer-network cleanup retries and preservation rules."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.sandbox.runtime.adapters import uds_mount

from ._uds_mount_helpers import _inspect_state


def test_sweeper_retries_stale_owned_network_without_container() -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, "", ""
        if cmd[:3] == ["docker", "network", "ls"]:
            return 0, "factory-sandbox-lab\n", ""
        if cmd[:3] == ["docker", "network", "inspect"]:
            if "{{.Created}}" in cmd[4]:
                return 0, "python-factory|{}|2026-09-30T10:00:00Z", ""
            return 0, "python-factory|{}", ""
        return 0, "", ""

    assert uds_mount.sweep_orphans(
        fake_run, now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
    ) == []
    assert ["docker", "network", "rm", "factory-sandbox-lab"] in calls


@pytest.mark.parametrize("state", [
    "python-factory|{}|2026-09-30T11:59:30Z",
    'python-factory|{"attached":{}}|2026-09-30T10:00:00Z',
    "other|{}|2026-09-30T10:00:00Z",
])
def test_sweeper_preserves_recent_occupied_or_foreign_network(state: str) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, "", ""
        if cmd[:3] == ["docker", "network", "ls"]:
            return 0, "factory-sandbox-lab\n", ""
        if cmd[:3] == ["docker", "network", "inspect"]:
            return 0, state, ""
        return 0, "", ""

    uds_mount.sweep_orphans(
        fake_run, now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
    )
    assert ["docker", "network", "rm", "factory-sandbox-lab"] not in calls


@pytest.mark.parametrize("containers_json", ["{}", "null"])
def test_sweeper_removes_only_empty_owned_peer_network_after_reap(
    containers_json: str,
) -> None:
    container_id = "e" * 64
    ps = (
        f"{container_id}\tExited (0) 20 minutes ago\t"
        "factory.sandbox=true,factory.sandbox.peer_network_name=factory-sandbox-lab\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, ps, ""
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(container_id, labels={
                "factory.sandbox": "true",
                "factory.sandbox.peer_network_name": "factory-sandbox-lab",
            }), ""
        if cmd[:3] == ["docker", "network", "inspect"]:
            return 0, f"python-factory|{containers_json}", ""
        return 0, "", ""

    uds_mount.sweep_orphans(fake_run)
    assert ["docker", "network", "rm", "factory-sandbox-lab"] in calls
    assert calls.index(["docker", "rm", "-f", container_id]) < calls.index(
        ["docker", "network", "rm", "factory-sandbox-lab"]
    )


@pytest.mark.parametrize("network_state", ["someone-else|{}", "python-factory|{\"x\":{}}"])
def test_sweeper_preserves_non_owned_or_occupied_network(network_state: str) -> None:
    container_id = "e" * 64
    ps = (
        f"{container_id}\tDead\t"
        "factory.sandbox=true,factory.sandbox.peer_network_name=factory-sandbox-lab\n"
    )
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, ps, ""
        if cmd[:2] == ["docker", "inspect"]:
            return 0, _inspect_state(container_id, status="dead", labels={
                "factory.sandbox": "true",
                "factory.sandbox.peer_network_name": "factory-sandbox-lab",
            }), ""
        if cmd[:3] == ["docker", "network", "inspect"]:
            return 0, network_state, ""
        return 0, "", ""

    uds_mount.sweep_orphans(fake_run)
    assert ["docker", "network", "rm", "factory-sandbox-lab"] not in calls
