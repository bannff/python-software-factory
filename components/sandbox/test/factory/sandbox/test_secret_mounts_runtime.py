"""Runtime execute/download secret-output suppression tests."""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter
from factory.sandbox.runtime.runtime import SandboxRuntime

async def test_execute_suppresses_output_when_store_misses_and_inspect_fails(
    monkeypatch,
) -> None:
    from factory.sandbox.runtime.adapters import docker_adapter

    sentinel = "SYNTHETIC_SECRET_SENTINEL"

    calls = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 1, "", "Docker unavailable"

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    store = MagicMock()
    store.load.return_value = None
    runtime = SandboxRuntime(adapter=DockerAdapter(), store=store)
    runtime._store.load.return_value = None
    result = await runtime.execute("edge-lab", "cat license")

    assert result.stdout == ""
    assert "Execution is disabled" in result.stderr
    assert calls == [[
        "docker", "inspect", "--format",
        '{{ index .Config.Labels "factory.sandbox.secret_output_suppressed" }}',
        "edge-lab",
    ]]



def test_docker_secret_suppression_marker_survives_store_miss(monkeypatch) -> None:
    def fake_run(command, timeout=30):  # noqa: ANN001
        assert command[:3] == ["docker", "inspect", "--format"]
        return 0, "true\n", ""

    monkeypatch.setattr(
        "factory.sandbox.runtime.adapters.docker_adapter._run", fake_run,
    )
    assert DockerAdapter().get_secret_output_suppression("edge-lab") is True


def test_docker_secret_suppression_marker_is_unknown_on_inspect_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.sandbox.runtime.adapters.docker_adapter._run",
        lambda command, timeout=30: (1, "", "Docker unavailable"),
    )
    assert DockerAdapter().get_secret_output_suppression("edge-lab") is None


@pytest.mark.parametrize(
    "inspect_result",
    [
        (0, "true\n", ""),
        (1, "", "Docker unavailable"),
        (0, "unexpected marker output\n", ""),
    ],
)
@pytest.mark.asyncio
async def test_docker_adapter_execute_denies_secret_or_unverified_container(
    monkeypatch, inspect_result,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        if command[:3] == ["docker", "inspect", "--format"]:
            return inspect_result
        raise AssertionError("secret-enabled container must not receive docker exec")

    monkeypatch.setattr(
        "factory.sandbox.runtime.adapters.docker_adapter._run", fake_run,
    )
    result = await DockerAdapter().execute("edge-lab", "cat /run/secrets/license")

    assert result["exit_code"] == 126
    assert "Execution is disabled" in result["stderr"]
    assert calls == [[
        "docker", "inspect", "--format",
        '{{ index .Config.Labels "factory.sandbox.secret_output_suppressed" }}',
        "edge-lab",
    ]]



async def test_secret_enabled_download_is_blocked_before_host_copy(monkeypatch) -> None:
    from factory.sandbox.core import EnvironmentStatus
    from factory.sandbox.runtime.models import EnvironmentInfo

    sentinel = "SYNTHETIC_SECRET_SENTINEL"
    adapter = MagicMock()
    adapter.download_file = AsyncMock(return_value={
        "success": True, "contents": sentinel,
    })
    store = MagicMock()
    store.load.return_value = EnvironmentInfo(
        env_id="edge-1", status=EnvironmentStatus.RUNNING,
        instance_type="docker", created_at="2026-09-30T00:00:00+00:00",
        metadata={"secret_mounts_enabled": True},
    )
    runtime = SandboxRuntime(adapter=adapter, store=store)
    emitted: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "factory.sandbox.runtime.runtime.emit",
        lambda event, payload: emitted.append((event, payload)),
    )

    result = await runtime.download_file("edge-1", "/run/secrets/license", "/tmp/license")

    assert result["success"] is False
    assert "disabled" in result["error"]
    adapter.download_file.assert_not_awaited()
    assert sentinel not in json.dumps({"result": result, "events": emitted})


@pytest.mark.asyncio
async def test_download_fails_closed_when_store_misses_and_docker_is_unavailable(
    monkeypatch,
) -> None:
    from factory.sandbox.runtime.adapters import docker_adapter

    calls: list[list[str]] = []

    def fake_run(command, timeout=30):  # noqa: ANN001
        calls.append(command)
        return 1, "", "Docker unavailable"

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    runtime = SandboxRuntime(adapter=DockerAdapter(), store=MagicMock())
    runtime._store.load.return_value = None
    result = await runtime.download_file("edge-lab", "/secret", "/tmp/secret")

    assert result["success"] is False
    assert calls == [[
        "docker", "inspect", "--format",
        '{{ index .Config.Labels "factory.sandbox.secret_output_suppressed" }}',
        "edge-lab",
    ]]


