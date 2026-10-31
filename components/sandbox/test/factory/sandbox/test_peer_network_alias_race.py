"""Concurrent peer-alias claim exclusion for Docker peer-network provisioning."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from factory.sandbox.runtime.adapters import docker_adapter


def test_concurrent_provision_cannot_claim_same_peer_alias(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        docker_adapter, "_PEER_NETWORK_LOCK_DIR", tmp_path / "peer-locks",
    )
    first_run_started = threading.Event()
    release_first_run = threading.Event()
    second_started = threading.Event()
    calls_lock = threading.Lock()
    calls: list[list[str]] = []
    attached_names: list[str] = []

    def fake_run(command: list[str], timeout: int = 30):
        with calls_lock:
            calls.append(command)
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, json.dumps({
                    name: {"Name": name} for name in attached_names
                }), ""
            return 0, "python-factory|false", ""
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "not found"
        if command[:2] == ["docker", "inspect"]:
            return 0, json.dumps({
                "factory-sandbox-mesh": {"Aliases": ["shared-peer"]},
            }), ""
        if command[:2] == ["docker", "run"]:
            name = command[command.index("--name") + 1]
            if name == "peer-one":
                first_run_started.set()
                assert release_first_run.wait(timeout=2)
            with calls_lock:
                attached_names.append(name)
            return 0, f"{name}-container-id\n", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)

    def provision(name: str) -> tuple[str, ValueError | None]:
        if name == "peer-two":
            second_started.set()
        try:
            result = asyncio.run(docker_adapter.DockerAdapter().provision({
                "image": "alpine:3.20", "container_name": name,
                "replace_existing": False,
                "peer_network": {
                    "network_id": "mesh", "alias": "shared-peer", "port": 4321,
                },
            }))
            return result, None
        except ValueError as error:
            return name, error

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(provision, "peer-one")
        assert first_run_started.wait(timeout=2)
        second = executor.submit(provision, "peer-two")
        assert second_started.wait(timeout=2)
        time.sleep(0.05)
        with calls_lock:
            assert sum(call[:2] == ["docker", "run"] for call in calls) == 1
        release_first_run.set()
        first_result = first.result(timeout=2)
        second_result = second.result(timeout=2)

    assert first_result == ("peer-one", None)
    assert second_result[0] == "peer-two"
    assert isinstance(second_result[1], ValueError)
    assert "already attached to another container" in str(second_result[1])
