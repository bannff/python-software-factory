"""Typed MCP boundary tests for extended Sandbox operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.core import EnvironmentStatus
from factory.sandbox.mcp.deterministic_extended import register as register_deterministic
from factory.sandbox.mcp.operational_extended import register as register_operational
from factory.sandbox.runtime.models import CommandResult, EnvironmentInfo
from factory.sandbox.runtime.workspace import get_or_create_workspace


@pytest.fixture
def runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.execute = AsyncMock(return_value=CommandResult(
        success=False, exit_code=1, stdout="", stderr="failed", duration_ms=3,
    ))
    runtime.upload_file = AsyncMock(return_value={"success": True, "remote_path": "/remote"})
    runtime.download_file = AsyncMock(return_value={"success": False, "error": "missing"})
    runtime.apply_service_mocks = AsyncMock(return_value={"env_id": "env-1", "mocks_applied": ["authorizer"]})
    runtime.workspace_dir.return_value = "/tmp/factory-sandbox/env-1/artifacts"
    runtime.list_environments.return_value = [EnvironmentInfo(
        env_id="env-1", status=EnvironmentStatus.RUNNING, instance_type="mock",
        created_at="2026-08-18T00:00:00+00:00",
    )]
    return runtime


async def _tool(runtime: MagicMock, name: str):
    mcp = ToolCatalog("sandbox-extended-boundary-test")
    register_operational(mcp, runtime)
    register_deterministic(mcp, runtime)
    return await mcp.get_tool(name)


@pytest.mark.asyncio
async def test_execute_preserves_nonzero_exit_as_typed_data(runtime) -> None:
    tool = await _tool(runtime, "sandbox.execute")
    assert tool.telemetry_excluded_argument_fields == frozenset({"command"})
    result = await tool.fn(
        env_id="env-1", command="false",
    )
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data.success is False
    assert result.data.exit_code == 1


@pytest.mark.asyncio
async def test_file_transfers_normalize_success_and_failure(runtime) -> None:
    upload = await (await _tool(runtime, "sandbox.upload_file")).fn(
        env_id="env-1", local_path="/local", remote_path="/remote",
    )
    download = await (await _tool(runtime, "sandbox.download_file")).fn(
        env_id="env-1", remote_path="/remote", local_path="/local",
    )
    assert upload.ok is True and upload.data.remote_path == "/remote"
    assert download.ok is False and download.data is None
    assert download.error == "missing"


@pytest.mark.asyncio
async def test_service_mocks_have_nested_ingress_schema_and_typed_result(runtime) -> None:
    tool = await _tool(runtime, "sandbox.apply_service_mocks")
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    assert "config" in schema["properties"]
    result = await tool.fn(env_id="env-1", config={"authorizer": {"enabled": True}})
    assert result.ok is True
    assert result.data.mocks_applied == ["authorizer"]


@pytest.mark.asyncio
async def test_list_and_cfn_are_deterministic_typed_results(runtime) -> None:
    listed = (await _tool(runtime, "sandbox.list_environments")).fn()
    cfn = (await _tool(runtime, "sandbox.generate_cfn_from_recon")).fn(
        resources=[{"type": "S3", "name": "bucket"}, {"type": "unknown", "name": "x"}],
    )
    assert listed.ok is True and listed.data.count == 1
    assert cfn.ok is True and cfn.data.generated_count == 1
    assert cfn.data.skipped[0].reason == "unsupported_type"


def test_workspace_rejects_traversal_and_is_idempotent(tmp_path) -> None:
    workspace = get_or_create_workspace(tmp_path, "env-1")
    assert get_or_create_workspace(tmp_path, "env-1") == workspace
    with pytest.raises(ValueError):
        get_or_create_workspace(tmp_path, "../escape")
