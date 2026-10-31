"""Peer-network attach, status reporting, and empty-network cleanup."""

from __future__ import annotations

import json

import pytest
from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.peer_network import PeerNetworkSpec
from factory.sandbox.runtime.runtime import SandboxRuntime


@pytest.mark.asyncio
async def test_peer_network_requires_docker_adapter(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "mesh.yaml").write_text("image: alpine:3.20\n")
    with pytest.raises(ValueError, match="peer networks require the Docker adapter"):
        await SandboxRuntime(adapter=MockAdapter()).provision(
            profile="mesh",
            peer_network=PeerNetworkSpec(
                network_id="mesh-a", alias="peer-a", port=24225,
            ),
        )


@pytest.mark.asyncio
async def test_provision_attaches_peer_and_status_exposes_stable_endpoint(monkeypatch) -> None:
    calls: list[list[str]] = []
    labels = {
        "factory.sandbox.peer_network_id": "factory-test",
        "factory.sandbox.peer_alias": "peer-a",
        "factory.sandbox.peer_port": "4321",
        "factory.sandbox.peer_internal": "false",
    }

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "not found"
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, "{}", ""
            return 1, "", "not found"
        if command[:3] == ["docker", "network", "create"]:
            return 0, "network-id\n", ""
        if command[:2] == ["docker", "run"]:
            return 0, "container-id\n", ""
        if command[0:2] == ["docker", "inspect"] and "{{json .Config.Labels}}" in command:
            return 0, json.dumps(labels), ""
        if command[0:2] == ["docker", "inspect"]:
            return 0, "running\n", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    adapter = docker_adapter.DockerAdapter()
    env_id = await adapter.provision({
        "image": "alpine:3.20", "container_name": "peer-a",
        "replace_existing": False,
        "peer_network": {"network_id": "factory-test", "alias": "peer-a", "port": 4321},
    })
    run = next(command for command in calls if command[:2] == ["docker", "run"])
    assert run[run.index("--network") + 1] == "factory-sandbox-factory-test"
    assert run[run.index("--network-alias") + 1] == "peer-a"
    network_create = next(
        command for command in calls if command[:3] == ["docker", "network", "create"]
    )
    assert "--internal" not in network_create
    assert run[run.index("--label") + 1] == "factory.sandbox=true"
    status = await adapter.get_status(env_id)
    assert status["peer_network"]["endpoint"] == "peer-a:4321"
    assert status["peer_network"]["internal"] is False


@pytest.mark.asyncio
async def test_internal_peer_network_uses_internal_bridge_and_reports_mode(monkeypatch) -> None:
    calls: list[list[str]] = []
    labels = {
        "factory.sandbox.peer_network_id": "offline-mesh",
        "factory.sandbox.peer_alias": "offline-a",
        "factory.sandbox.peer_port": "24225",
        "factory.sandbox.peer_internal": "true",
    }

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "not found"
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, "{}", ""
            return 1, "", "not found"
        if command[:3] == ["docker", "network", "create"]:
            return 0, "network-id\n", ""
        if command[:2] == ["docker", "run"]:
            return 0, "container-id\n", ""
        if command[0:2] == ["docker", "inspect"] and "{{json .Config.Labels}}" in command:
            return 0, json.dumps(labels), ""
        if command[0:2] == ["docker", "inspect"]:
            return 0, "running\n", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    adapter = docker_adapter.DockerAdapter()
    env_id = await adapter.provision({
        "image": "alpine:3.20", "container_name": "offline-a",
        "replace_existing": False,
        "peer_network": {
            "network_id": "offline-mesh", "alias": "offline-a",
            "port": 24225, "internal": True,
        },
    })
    network_create = next(
        command for command in calls if command[:3] == ["docker", "network", "create"]
    )
    assert "--internal" in network_create
    run = next(command for command in calls if command[:2] == ["docker", "run"])
    assert run[run.index("--network") + 1] == "factory-sandbox-offline-mesh"
    assert run[run.index("--network-alias") + 1] == "offline-a"
    status = await adapter.get_status(env_id)
    assert status["peer_network"]["internal"] is True
    assert status["peer_network"]["endpoint"] == "offline-a:24225"


def test_cleanup_only_removes_empty_sandbox_owned_network(monkeypatch) -> None:
    calls: list[list[str]] = []
    outputs = iter([
        (0, 'python-factory|{"peer": {}}', ""),
        (0, 'python-factory|{}', ""),
    ])

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            return next(outputs)
        return 0, "", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    docker_adapter.DockerAdapter._remove_empty_owned_peer_network(
        "factory-sandbox-factory-test",
    )
    assert not any(command[:3] == ["docker", "network", "rm"] for command in calls)

    calls.clear()
    outputs = iter([(0, 'python-factory|{}', "")])
    docker_adapter.DockerAdapter._remove_empty_owned_peer_network(
        "factory-sandbox-factory-test",
    )
    assert ["docker", "network", "rm", "factory-sandbox-factory-test"] in calls


def test_cleanup_leaves_unowned_network_untouched(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        return 0, 'false|{}', ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    docker_adapter.DockerAdapter._remove_empty_owned_peer_network("external")
    assert len(calls) == 1
