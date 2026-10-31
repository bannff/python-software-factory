"""Docker provision-time secret-mount enforcement and non-echo tests."""

from __future__ import annotations

import json
import logging

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory.sandbox.runtime.adapters import secret_mounts
from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter
from factory.sandbox.runtime.profiles import SandboxProfile
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.provision_context import build_provision_context
from factory.sandbox.runtime.runtime import SandboxRuntime
from ._secret_mount_helpers import INSPECTED_ENTRYPOINT, PINNED_IMAGE

async def test_secret_source_and_contents_stay_out_of_public_runtime_surfaces(
    tmp_path, monkeypatch, caplog,
) -> None:
    source = tmp_path / "offline-license"
    sentinel = "SYNTHETIC_SECRET_SENTINEL"
    source.write_text(sentinel)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "edge-lab.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "container_name: edge-lab\n"
        "replace_existing: false\n"
        "entrypoint: [run]\n"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))

    adapter = DockerAdapter()
    captured: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        captured.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            if "{{json .Config.Entrypoint}}" in command:
                return 0, INSPECTED_ENTRYPOINT, ""
            return 0, PINNED_IMAGE + "\n", ""
        if command[:3] == ["docker", "run", "-d"]:
            return 0, "container-id\n", ""
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "No such container"
        if command[:3] == ["docker", "network", "inspect"]:
            if command[-1] == "factory-sandbox-secret-lab":
                if "{{json .Containers}}" in command:
                    return 0, "{}", ""
                return 1, "", "No such network"
        return 0, "", ""

    monkeypatch.setattr(
        "factory.sandbox.runtime.adapters.docker_adapter._run", fake_run,
    )
    emitted: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "factory.sandbox.runtime.runtime.emit",
        lambda event, payload: emitted.append((event, payload)),
    )
    store = MagicMock()
    store.load.return_value = None
    runtime = SandboxRuntime(adapter=adapter, store=store)

    with caplog.at_level(logging.INFO):
        environment = await runtime.provision(SandboxConfig(), profile="edge-lab")

    docker_run = next(command for command in captured if command[:3] == ["docker", "run", "-d"])
    assert docker_run[-2:] == [PINNED_IMAGE, "run"]
    assert "--entrypoint" not in docker_run
    assert "--mount" in docker_run
    assert "factory.sandbox.secret_output_suppressed=true" in docker_run
    assert "factory.sandbox.timeout_seconds=3600" in docker_run
    mount_spec = docker_run[docker_run.index("--mount") + 1]
    assert mount_spec.endswith(",readonly")
    assert f"source={source.resolve()}" in mount_spec
    assert all(
        not (argument.startswith("-e") and str(source) in argument)
        for argument in docker_run
    )

    public_output = json.dumps({
        "environment": environment.model_dump(),
        "events": emitted,
        "logs": caplog.text,
    }, default=str)
    assert str(source) not in public_output
    assert sentinel not in public_output
    assert secret_mounts.DITTO_LICENSE_TARGET not in public_output


@pytest.mark.parametrize("override", [
    {"auto_terminate": False},
    {"timeout_seconds": 0},
    {"timeout_seconds": 86401},
    {"timeout_seconds": True},
])
@pytest.mark.asyncio
async def test_secret_provision_rejects_disabled_or_invalid_timeout_before_docker(
    monkeypatch, override,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        docker_adapter, "_run",
        lambda command, timeout=30: calls.append(command) or (0, "", ""),
    )
    with pytest.raises(ValueError, match="auto-termination|timeout"):
        await DockerAdapter().provision({
            "image": PINNED_IMAGE,
            "entrypoint": ["run"],
            "secret_mounts": [object()],
            "replace_existing": False,
            **override,
        })
    assert calls == []


@pytest.mark.asyncio
async def test_docker_failure_does_not_echo_secret_source_or_contents(
    tmp_path, monkeypatch, caplog,
) -> None:
    source = tmp_path / "offline-license"
    sentinel = "SYNTHETIC_SECRET_SENTINEL"
    source.write_text(sentinel)
    adapter = DockerAdapter()
    calls: list[list[str]] = []

    def failing_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            if "{{json .Config.Entrypoint}}" in command:
                return 0, INSPECTED_ENTRYPOINT, ""
            return 0, PINNED_IMAGE + "\n", ""
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "No such container"
        if command[:3] == ["docker", "network", "inspect"]:
            if "{{json .Containers}}" in command:
                return 0, "{}", ""
            if any("{{.Internal}}" in part for part in command):
                return 0, "python-factory|true", ""
            if any("{{json .Containers}}" in part for part in command):
                return 0, "python-factory|{}", ""
            raise AssertionError(f"Unexpected Docker network inspect: {command}")
        if command[:3] == ["docker", "run", "-d"]:
            return 1, "", f"invalid mount source {source}: {sentinel}"
        if command[:3] == ["docker", "network", "rm"]:
            return 0, "", ""
        raise AssertionError(f"Unexpected Docker call: {command}")

    monkeypatch.setattr(
        "factory.sandbox.runtime.adapters.docker_adapter._run", failing_run,
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError) as failure:
            await adapter.provision({
                "image": PINNED_IMAGE,
                "entrypoint": ["run"],
                "replace_existing": False,
                "peer_network": {
                    "network_id": "secret-lab", "alias": "edge-lab",
                    "port": 4321, "internal": True,
                },
                "secret_mounts": secret_mounts.resolve_secret_mounts(
                    ["ditto-offline-license"],
                    {secret_mounts.DITTO_LICENSE_ENV: str(source)},
                ),
            })
    docker_runs = [call for call in calls if call[:3] == ["docker", "run", "-d"]]
    assert len(docker_runs) == 1
    assert "--mount" in docker_runs[0]
    assert docker_runs[0][-2:] == [PINNED_IMAGE, "run"]
    assert "attaching a configured secret" in str(failure.value)
    public_error = f"{failure.value}\n{caplog.text}"
    assert str(source) not in public_error
    assert sentinel not in public_error


@pytest.mark.asyncio
async def test_non_docker_adapter_rejects_secret_mount_before_provision(
    tmp_path, monkeypatch,
) -> None:
    source = tmp_path / "license"
    source.write_text("SYNTHETIC_SECRET_SENTINEL")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "edge-lab.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "container_name: edge-lab\n"
        "replace_existing: false\n"
        "entrypoint: [run]\n"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
