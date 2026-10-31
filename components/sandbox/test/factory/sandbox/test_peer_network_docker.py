"""Docker adapter provision guards and alias-claim exclusion for peer networks."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from factory.sandbox.runtime.adapters import docker_adapter
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_invalid_mesh_is_rejected_before_container_replacement(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        return 0, "", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValidationError):
        await docker_adapter.DockerAdapter().provision({
            "container_name": "old-peer", "replace_existing": True,
            "peer_network": {
                "network_id": "bad/name", "alias": "peer-a", "port": 1234,
            },
        })
    assert calls == []


@pytest.mark.asyncio
async def test_internal_network_rejects_host_ports_before_docker_mutation(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        return 0, "", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValueError, match="cannot publish ports to the host"):
        await docker_adapter.DockerAdapter().provision({
            "container_name": "offline-peer", "replace_existing": True,
            "ports": {"8080": "80"},
            "peer_network": {
                "network_id": "offline-mesh", "alias": "offline-peer",
                "port": 24225, "internal": True,
            },
        })
    assert calls == []


@pytest.mark.asyncio
async def test_network_name_collision_does_not_replace_container(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            return 0, "external-owner|false", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(RuntimeError, match="not Sandbox-owned"):
        await docker_adapter.DockerAdapter().provision({
            "container_name": "existing-peer", "replace_existing": True,
            "peer_network": {
                "network_id": "mesh-a", "alias": "peer-a", "port": 24225,
            },
        })
    assert len(calls) == 1
    assert calls[0][:3] == ["docker", "network", "inspect"]


@pytest.mark.asyncio
async def test_existing_bridge_must_match_requested_internal_mode(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            return 0, "python-factory|false", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(RuntimeError, match="different internal mode"):
        await docker_adapter.DockerAdapter().provision({
            "container_name": "offline-peer", "replace_existing": True,
            "peer_network": {
                "network_id": "offline-mesh", "alias": "offline-peer",
                "port": 24225, "internal": True,
            },
        })
    assert len(calls) == 1
    assert calls[0][:3] == ["docker", "network", "inspect"]


@pytest.mark.asyncio
async def test_duplicate_alias_is_rejected_before_replacing_peer(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, json.dumps({"other-id": {"Name": "other-peer"}}), ""
            return 0, "python-factory|true", ""
        if command[:2] == ["docker", "inspect"]:
            return 0, json.dumps({
                "factory-sandbox-offline-mesh": {
                    "Aliases": ["other-peer", "offline-peer"],
                },
            }), ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    with pytest.raises(ValueError, match="already attached to another container"):
        await docker_adapter.DockerAdapter().provision({
            "container_name": "replacement-peer", "replace_existing": True,
            "peer_network": {
                "network_id": "offline-mesh", "alias": "offline-peer",
                "port": 24225, "internal": True,
            },
        })
    assert not any(command[:3] == ["docker", "rm", "-f"] for command in calls)
    assert not any(command[:2] == ["docker", "run"] for command in calls)

@pytest.mark.asyncio
async def test_replacing_same_container_can_reuse_its_alias(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30):
        calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, json.dumps({"same-id": {"Name": "same-peer"}}), ""
            return 0, "python-factory|true", ""
        if command[:3] == ["docker", "rm", "-f"]:
            return 0, "", ""
        if command[:2] == ["docker", "run"]:
            return 0, "new-container-id\n", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    env_id = await docker_adapter.DockerAdapter().provision({
        "container_name": "same-peer", "replace_existing": True,
        "peer_network": {
            "network_id": "offline-mesh", "alias": "offline-peer",
            "port": 24225, "internal": True,
        },
    })
    assert env_id == "same-peer"
    assert any(command[:3] == ["docker", "rm", "-f"] for command in calls)
    assert any(command[:2] == ["docker", "run"] for command in calls)

