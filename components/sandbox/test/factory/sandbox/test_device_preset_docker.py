"""Selected device presets reach Docker as a bounded Linux proxy launch."""
from __future__ import annotations

import re

import pytest

from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.provision_context import build_provision_context


@pytest.mark.asyncio
async def test_selected_preset_builds_bounded_docker_run_without_replacing_container(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "lab.yaml").write_text(
        "image: alpine:3.20\n"
        "container_name: lab\n"
        "replace_existing: true\n"
        "entrypoint: [sleep, infinity]\n"
    )
    config, metadata, _ = build_provision_context(
        SandboxConfig(), "lab", "iphone-15",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30) -> tuple[int, str, str]:
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "No such container"
        if command[:2] == ["docker", "run"]:
            return 0, "container-id\n", ""
        raise AssertionError(f"Unexpected Docker command: {command}")

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    env_id = await docker_adapter.DockerAdapter().provision(config)

    assert metadata["device_preset"]["fidelity"] == "linux_proxy"
    assert len(calls) == 2
    assert calls[0] == ["docker", "container", "inspect", env_id]
    cmd = calls[1]
    assert cmd[:3] == ["docker", "run", "-d"]
    assert cmd[cmd.index("--name") + 1] == env_id
    assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", env_id)
    assert env_id != "lab"
    assert cmd[cmd.index("--platform") + 1] == metadata["device_preset"]["proxy"]["platform"]
    assert float(cmd[cmd.index("--cpus") + 1]) == metadata["device_preset"]["proxy"]["cpus"]
    assert cmd[cmd.index("--memory") + 1] == f"{metadata['device_preset']['proxy']['memory_mb']}m"
    assert "alpine:3.20" in cmd
    assert not any(command[:3] == ["docker", "rm", "-f"] for command in calls)
