"""MCP tool-surface secret-hygiene tests for sandbox secret mounts."""

from __future__ import annotations

import json
import logging

from unittest.mock import AsyncMock, MagicMock

import pytest

from factory.sandbox.runtime.adapters import secret_mounts
from factory.sandbox.mcp.operational import register as register_operational
from factory.sandbox.runtime.profiles import SandboxProfile
from factory.sandbox.runtime.models import SandboxConfig
from factory.sandbox.runtime.provision_context import build_provision_context
from factory.sandbox.runtime.runtime import SandboxRuntime
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from ._secret_mount_helpers import PINNED_IMAGE

async def test_secret_source_is_not_an_mcp_parameter_or_result() -> None:
    from factory.sandbox.core import EnvironmentStatus
    from factory.sandbox.runtime.models import EnvironmentInfo

    runtime = MagicMock()
    runtime.provision = AsyncMock(return_value=EnvironmentInfo(
        env_id="edge-1", status=EnvironmentStatus.PROVISIONING,
        instance_type="docker", created_at="2026-09-30T00:00:00+00:00",
    ))
    catalog = ToolCatalog("sandbox-secret-reference")
    register_operational(catalog, runtime)
    tool = await catalog.get_tool("sandbox.provision")
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    assert "secret_refs" not in schema["properties"]
    assert "secret_mounts" not in schema["properties"]
    output = json.dumps(schema)
    assert "SANDBOX_SECRET_DITTO_OFFLINE_LICENSE_FILE" not in output
    result = await tool.fn(profile="edge-lab")
    assert result.data.environment.env_id == "edge-1"
    assert "secret_mount" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_invalid_secret_profile_path_is_hidden_from_tool_errors_and_logs(
    tmp_path, monkeypatch, caplog,
) -> None:
    host_path = "/private/synthetic/license-path-sentinel"
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "invalid-secret.yaml").write_text(
        "image: python:3.11-slim\n"
        "replace_existing: false\n"
        f"secret_refs: [{host_path}]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    adapter = MagicMock()
    adapter.provision = AsyncMock()
    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    catalog = ToolCatalog("sandbox-secret-validation")
    register_operational(catalog, runtime)
    tool = await catalog.get_tool("sandbox.provision")

    with caplog.at_level(logging.ERROR, logger="factory.mcp_utils.runtime.tool_failure"):
        result = await tool.fn(profile="invalid-secret")

    assert result.ok is False
    assert host_path not in caplog.text
    assert host_path not in result.model_dump_json()
    adapter.provision.assert_not_awaited()


@pytest.mark.parametrize("image,entrypoint,message", [
    ("python:3.11-slim", ["/usr/local/bin/runner"], "local image ID"),
    ("repo@sha256:" + "a" * 64, ["/usr/local/bin/runner"], "local image ID"),
    (PINNED_IMAGE, [], "fixed nonempty command"),
    (PINNED_IMAGE, ["/usr/local/bin/runner", ""], "fixed nonempty command"),
    (PINNED_IMAGE, ["/bin/sh", "-c", "cat /run/secrets/ditto-offline-license"],
     "fixed noninteractive command"),
])
def test_secret_profile_requires_pinned_image_and_fixed_argv(
    tmp_path, monkeypatch, image, entrypoint, message,
) -> None:
    source = tmp_path / "license"
    source.write_text("synthetic")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "secret.yaml").write_text(
        f"image: {image}\n"
        "replace_existing: false\n"
        f"entrypoint: {json.dumps(entrypoint)}\n"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))
    with pytest.raises(ValueError, match=message):
        build_provision_context(SandboxConfig(), "secret")


def test_secret_profile_accepts_fixed_command_for_baked_image_entrypoint(
    tmp_path, monkeypatch,
) -> None:
    source = tmp_path / "license"
    source.write_text("synthetic")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "secret.yaml").write_text(
        f"image: {PINNED_IMAGE}\n"
        "replace_existing: false\n"
        "entrypoint: [run]\n"
        "peer_network: {network_id: secret-lab, alias: edge-lab, port: 4321, internal: true}\n"
        "secret_refs: [ditto-offline-license]\n"
    )
    monkeypatch.setenv("SANDBOX_PROFILES_DIR", str(profiles))
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))

    config, _, _ = build_provision_context(SandboxConfig(), "secret")
    assert config["entrypoint"] == ["run"]



def test_secret_profile_serialization_contains_reference_only(tmp_path, monkeypatch) -> None:
    source = tmp_path / "secret-file"
    source.write_text("SYNTHETIC_SECRET_SENTINEL")
    monkeypatch.setenv(secret_mounts.DITTO_LICENSE_ENV, str(source))
    profile = SandboxProfile(
        name="edge-lab", image="python:3.11-slim",
        secret_refs=["ditto-offline-license"],
    )
    serialized = profile.model_dump_json()
    assert "ditto-offline-license" in serialized
    assert str(source) not in serialized
    assert "SYNTHETIC_SECRET_SENTINEL" not in serialized


