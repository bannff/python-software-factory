"""Secret-boundary guards for diff, deploy, discovery, and file mutations."""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter
from factory.sandbox.runtime.runtime import SandboxRuntime

@pytest.mark.asyncio
async def test_diff_cannot_bypass_docker_secret_execute_guard(monkeypatch) -> None:
    from factory.sandbox.runtime.adapters import docker_adapter

    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 0, "true\n", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    store = MagicMock()
    store.load.return_value = None
    runtime = SandboxRuntime(adapter=DockerAdapter(), store=store)

    result = await runtime.diff("edge-lab")

    assert result == {
        "is_git_repo": False, "path": ".", "files": [], "stat": "",
    }
    assert calls and all(call[:2] == ["docker", "inspect"] for call in calls)


@pytest.mark.asyncio
async def test_cfn_deploy_cannot_bypass_docker_secret_execute_guard(monkeypatch) -> None:
    from factory.sandbox.runtime.adapters import docker_adapter

    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 0, "true\n", ""

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    runtime = SandboxRuntime(adapter=DockerAdapter(), store=MagicMock())

    result = await runtime.deploy_stack(
        "edge-lab", "stack", "Resources: {}",
    )

    assert result["success"] is False
    assert calls and all(call[:2] == ["docker", "inspect"] for call in calls)


def test_discovery_restores_secret_suppression_marker(monkeypatch) -> None:
    from factory.sandbox.runtime import discovery

    monkeypatch.setattr(
        discovery, "_docker_ps_lines", lambda args: [
            "edge-lab\tUp 1 minute\tjust now\t"
            "factory.sandbox=true,factory.sandbox.secret_output_suppressed=true"
        ],
    )
    environments = discovery.discover_docker_envs()
    assert environments[0].metadata["secret_mounts_enabled"] is True



@pytest.mark.asyncio
async def test_runtime_file_mutations_and_diff_stop_at_secret_boundary(monkeypatch) -> None:
    from factory.sandbox.core import EnvironmentStatus
    from factory.sandbox.runtime.models import EnvironmentInfo

    environment = EnvironmentInfo(
        env_id="edge-1", status=EnvironmentStatus.RUNNING,
        instance_type="docker", created_at="2026-09-30T00:00:00+00:00",
        metadata={"secret_mounts_enabled": True},
    )
    adapter = MagicMock()
    adapter.upload_file = AsyncMock(return_value={"success": True})
    adapter.execute = AsyncMock(return_value={"exit_code": 0, "stdout": "secret"})
    adapter.download_file = AsyncMock(return_value={"success": True})
    store = MagicMock()
    store.load.return_value = environment
    runtime = SandboxRuntime(adapter=adapter, store=store)
    monkeypatch.setattr("factory.sandbox.runtime.runtime.emit", lambda *_: None)

    assert (await runtime.write_file("edge-1", "/tmp/x", "payload"))["success"] is False
    assert (await runtime.upload_file("edge-1", "/tmp/x", "/tmp/y"))["success"] is False
    assert await runtime.diff("edge-1") == {
        "is_git_repo": False, "path": ".", "files": [], "stat": "",
    }
    assert (await runtime.download_file("edge-1", "/tmp/x", "/tmp/y"))["success"] is False
    adapter.upload_file.assert_not_awaited()
    adapter.execute.assert_not_awaited()
    adapter.download_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_file_mutations_fail_closed_if_docker_inspect_fails(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 1, "", "Docker unavailable"

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    store = MagicMock()
    store.load.return_value = None
    runtime = SandboxRuntime(adapter=DockerAdapter(), store=store)
    assert (await runtime.write_file("edge-lab", "/tmp/x", "payload"))["success"] is False
    assert (await runtime.upload_file("edge-lab", "/tmp/x", "/tmp/y"))["success"] is False
    assert (await runtime.download_file("edge-lab", "/tmp/x", "/tmp/y"))["success"] is False
    assert (await runtime.diff("edge-lab"))["files"] == []
    assert calls and all(command[:2] == ["docker", "inspect"] for command in calls)



