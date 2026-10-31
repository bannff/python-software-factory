"""Preset catalog resilience and Docker provenance across process restarts."""
from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.mcp.deterministic import register as register_deterministic
from factory.sandbox.runtime import discovery
from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.device_presets import DeviceRunLabels
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.provision_context import build_provision_context


@pytest.mark.asyncio
async def test_malformed_user_yaml_does_not_hide_typed_device_catalog(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("SANDBOX_DEVICE_PRESETS_DIR", str(tmp_path))
    (tmp_path / "broken-device.yaml").write_text("proxy: [unclosed\n")
    catalog = ToolCatalog("device-catalog-resilience")
    register_deterministic(catalog, MagicMock())
    tool = await catalog.get_tool("sandbox.list_device_presets")

    result = tool.fn()

    assert isinstance(result, ToolResult) and result.ok
    assert "broken-device" not in result.data.presets
    assert result.data.presets["iphone-15"].fidelity == "linux_proxy"


@pytest.mark.asyncio
async def test_docker_labels_reconstruct_device_preset_after_restart(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "lab.yaml").write_text(
        "image: alpine:3.20\n"
        "container_name: lab\n"
    )
    config, expected, _ = build_provision_context(
        SandboxConfig(), "lab", "iphone-15",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 30) -> tuple[int, str, str]:
        calls.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return 1, "", "No such container"
        if command[:2] == ["docker", "run"]:
            return 0, "container-id\n", ""
        raise AssertionError(command)

    monkeypatch.setattr(docker_adapter, "_run", fake_run)
    env_id = await docker_adapter.DockerAdapter().provision(config)
    cmd = next(command for command in calls if command[:2] == ["docker", "run"])
    labels = {
        cmd[index + 1].split("=", 1)[0]: cmd[index + 1].split("=", 1)[1]
        for index, part in enumerate(cmd[:-1]) if part == "--label"
    }
    assert labels["factory.sandbox"] == "true"
    assert labels["factory.sandbox.profile"] == "lab"
    assert labels["factory.sandbox.device_preset"] == "iphone-15"
    assert labels["factory.sandbox.fidelity"] == "linux_proxy"
    assert labels["factory.sandbox.platform"] == expected["platform"]
    assert float(labels["factory.sandbox.cpus"]) == expected["cpus"]
    assert int(labels["factory.sandbox.memory_mb"]) == expected["memory_mb"]
    assert re.fullmatch(r"[0-9a-f]{64}", labels["factory.sandbox.preset_sha256"])
    assert labels["factory.sandbox.preset_sha256"] == expected["preset_sha256"]

    line = f"{env_id}\tUp 1 second\t2026-09-30 00:00:00\t" + ",".join(
        f"{key}={value}" for key, value in labels.items()
    )
    monkeypatch.setattr(
        discovery, "_docker_ps_lines",
        lambda args: [line] if args == ["--filter", "label=factory.sandbox=true"] else [],
    )
    recovered = discovery.discover_docker_envs()
    assert len(recovered) == 1
    assert recovered[0].env_id == env_id
    assert recovered[0].metadata["profile"] == "lab"
    preset = recovered[0].metadata["device_preset"]
    assert preset["name"] == expected["device_preset"]["name"]
    assert preset["fidelity"] == expected["device_preset"]["fidelity"]
    assert preset["proxy"] == expected["device_preset"]["proxy"]
    assert recovered[0].metadata["preset_sha256"] == expected["preset_sha256"]


def test_discovery_preserves_secret_marker_with_device_preset(monkeypatch) -> None:
    labels = DeviceRunLabels(
        profile="edge-n2-sdk",
        device_preset="iphone-15",
        fidelity="linux_proxy",
        platform="linux/arm64",
        cpus=1.0,
        memory_mb=512,
    ).docker_labels()
    labels.update({
        "factory.sandbox": "true",
        "factory.sandbox.secret_output_suppressed": "true",
    })
    line = "edge-n2-sdk\tUp 1 second\tjust now\t" + ",".join(
        f"{key}={value}" for key, value in labels.items()
    )
    monkeypatch.setattr(
        discovery, "_docker_ps_lines",
        lambda args: [line] if args == ["--filter", "label=factory.sandbox=true"] else [],
    )

    recovered = discovery.discover_docker_envs()

    assert len(recovered) == 1
    assert recovered[0].metadata["secret_mounts_enabled"] is True
    assert recovered[0].metadata["device_preset"]["name"] == "iphone-15"
