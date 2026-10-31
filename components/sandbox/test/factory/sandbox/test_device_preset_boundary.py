"""Device selectors at the typed MCP and Docker provisioning boundaries."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.core import EnvironmentStatus
from factory.sandbox.mcp.deterministic import register as register_deterministic
from factory.sandbox.mcp.operational import register as register_operational
from factory.sandbox.runtime.models import EnvironmentInfo, SandboxConfig
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.provision_context import build_provision_context
from factory.sandbox.runtime.runtime import SandboxRuntime


@pytest.fixture
def edge_lab_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "edge-lab.yaml").write_text(
        "image: alpine:3.20\n"
        "container_name: edge-lab\n"
        "replace_existing: false\n"
        "entrypoint: [sleep, infinity]\n"
    )


def test_selected_device_sets_proxy_limits_and_fidelity_metadata(edge_lab_profile) -> None:
    config, metadata, _ = build_provision_context(
        SandboxConfig(), "edge-lab", "iphone-15",
    )
    preset = metadata["device_preset"]
    assert preset["name"] == "iphone-15"
    assert preset["form_factor"] == "phone"
    assert preset["os_family"] == "ios"
    assert preset["fidelity"] == "linux_proxy"
    assert preset["source_url"].startswith("https://")
    assert config["platform"] == preset["proxy"]["platform"]
    assert config["cpus"] == preset["proxy"]["cpus"]
    assert config["memory_mb"] == preset["proxy"]["memory_mb"]
    assert config["replace_existing"] is False
    assert config["container_name"] != "edge-lab"


def test_each_preset_run_gets_a_distinct_container_identity(edge_lab_profile) -> None:
    first, _, _ = build_provision_context(SandboxConfig(), "edge-lab", "iphone-15")
    second, _, _ = build_provision_context(SandboxConfig(), "edge-lab", "iphone-15")
    tablet, tablet_meta, _ = build_provision_context(SandboxConfig(), "edge-lab", "ipad-a16")
    assert len({first["container_name"], second["container_name"], tablet["container_name"]}) == 3
    assert tablet_meta["device_preset"]["form_factor"] == "tablet"
    assert all(c["replace_existing"] is False for c in (first, second, tablet))


def test_no_device_selector_preserves_profile_launch_settings(edge_lab_profile) -> None:
    config, metadata, _ = build_provision_context(SandboxConfig(), "edge-lab")
    assert config["container_name"] == "edge-lab"
    assert config["replace_existing"] is False
    assert "device_preset" not in metadata


def test_device_selector_without_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="profile"):
        build_provision_context(SandboxConfig(), None, "iphone-15")


def test_inline_target_and_selected_preset_are_ambiguous(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "inline-target.yaml").write_text(
        "image: alpine:3.20\n"
        "device_target:\n  family: iphone\n  fidelity: linux_proxy\n"
    )
    with pytest.raises(ValueError, match="device_target|ambiguous"):
        build_provision_context(SandboxConfig(), "inline-target", "iphone-15")


@pytest.mark.asyncio
async def test_invalid_device_preset_fails_before_adapter_provision(edge_lab_profile) -> None:
    adapter = MagicMock()
    adapter.provision = AsyncMock()
    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    with pytest.raises(ValueError, match="Unknown device preset"):
        await runtime.provision(SandboxConfig(), profile="edge-lab", device_preset="missing")
    adapter.provision.assert_not_awaited()


@pytest.mark.asyncio
async def test_selected_device_requires_docker_adapter(edge_lab_profile) -> None:
    adapter = MockAdapter()
    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    with pytest.raises(ValueError, match="Docker adapter"):
        await runtime.provision(
            SandboxConfig(), profile="edge-lab", device_preset="iphone-15",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("profile_settings,error", [
    ("platform: linux/amd64\ncpus: 1\nmemory_mb: 128\n", ValueError),
    ("cpus: -1\nmemory_mb: 0\n", ValidationError),
])
async def test_conflicting_or_invalid_profile_envelope_never_reaches_adapter(
    tmp_path, monkeypatch, profile_settings, error,
) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "constrained.yaml").write_text(
        "image: alpine:3.20\n" + profile_settings
    )
    adapter = MagicMock()
    adapter.provision = AsyncMock()
    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    with pytest.raises(error):
        await runtime.provision(
            SandboxConfig(), profile="constrained", device_preset="iphone-15",
        )
    adapter.provision.assert_not_awaited()


@pytest.mark.asyncio
async def test_selected_device_rejects_fixed_profile_host_ports_before_adapter(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(tmp_path))
    (tmp_path / "port-bound.yaml").write_text(
        "image: alpine:3.20\n"
        "ports:\n  '5050': '5000'\n"
    )
    adapter = MagicMock()
    adapter.provision = AsyncMock()
    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    with pytest.raises(ValueError, match="port|host"):
        await runtime.provision(
            SandboxConfig(), profile="port-bound", device_preset="iphone-15",
        )
    adapter.provision.assert_not_awaited()


@pytest.mark.asyncio
async def test_provision_mcp_accepts_typed_device_selector() -> None:
    runtime = MagicMock()
    runtime.provision = AsyncMock(return_value=EnvironmentInfo(
        env_id="env-1", status=EnvironmentStatus.PROVISIONING,
        instance_type="docker", created_at="2026-09-30T00:00:00+00:00",
    ))
    catalog = ToolCatalog("device-preset-boundary")
    register_operational(catalog, runtime)
    tool = await catalog.get_tool("sandbox.provision")
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    assert "device_preset" in schema["properties"]
    result = await tool.fn(profile="edge-lab", device_preset="iphone-15")
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.environment.env_id == "env-1"
    assert runtime.provision.await_args.kwargs["device_preset"] == "iphone-15"
    with pytest.raises(SchemaMigrationError):
        await tool.fn(profile="edge-lab", device_preset="../escape")


@pytest.mark.asyncio
async def test_device_catalog_is_exposed_as_typed_mcp_result() -> None:
    catalog = ToolCatalog("device-preset-catalog")
    register_deterministic(catalog, MagicMock())
    tool = await catalog.get_tool("sandbox.list_device_presets")
    assert tool.fn._mcp_input_model.model_json_schema()["properties"] == {}
    result = tool.fn()
    assert isinstance(result, ToolResult) and result.ok
    iphone = result.data.presets["iphone-15"]
    assert iphone.name == "iphone-15"
    assert iphone.form_factor == "phone"
    assert iphone.fidelity == "linux_proxy"
    assert iphone.proxy.platform in {"linux/arm64", "linux/amd64"}
