"""Property tests for typed sandbox extended-MCP boundary invariants.

Verifies workspace containment, CFN skip diagnostics, transfer envelopes,
registration categories, and nested service-mock ingress validation.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from hypothesis import given, settings, strategies as st
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.interface import Runtime, create_server
from factory.sandbox.mcp.deterministic_extended import register as register_deterministic
from factory.sandbox.mcp.operational_extended import register as register_operational
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.runtime.workspace import get_or_create_workspace

_SAFE_IDS = st.text(
    min_size=1, max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


def _extended_tool(runtime: MagicMock, name: str):
    mcp = ToolCatalog("sandbox-extended-properties")
    register_operational(mcp, runtime)
    register_deterministic(mcp, runtime)
    return asyncio.run(mcp.get_tool(name))


@settings(max_examples=50)
@given(env_id=_SAFE_IDS)
def test_workspace_get_or_create_is_contained_and_idempotent(env_id: str) -> None:
    """Every safe environment identifier has one contained artifact directory."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workspace = get_or_create_workspace(root, env_id)
        assert workspace == get_or_create_workspace(root, env_id)
        assert workspace.is_dir()
        assert workspace.relative_to(root.resolve()) == Path(env_id) / "artifacts"


@settings(max_examples=50)
@given(env_id=st.sampled_from(["", ".", "..", "../escape", "a/b", "/absolute"]))
def test_workspace_rejects_non_segment_identifiers(env_id: str) -> None:
    """Traversal and non-segment identifiers never create a workspace."""
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(ValueError):
            get_or_create_workspace(Path(directory), env_id)


@settings(max_examples=50)
@given(
    resources=st.lists(
        st.fixed_dictionaries({
            "type": st.sampled_from([None, "", "S3", "not-supported"]),
            "name": st.sampled_from([None, "", "resource"]),
        }),
        max_size=12,
    ),
)
def test_cfn_skips_report_each_invalid_resource(resources: list[dict[str, str | None]]) -> None:
    """CFN diagnostics classify every omitted recon entry by its first cause."""
    tool = _extended_tool(MagicMock(), "sandbox.generate_cfn_from_recon")
    result = tool.fn(resources=resources)
    expected = []
    for index, resource in enumerate(resources):
        if not resource["type"]:
            expected.append((index, "missing_type"))
        elif not resource["name"]:
            expected.append((index, "missing_name"))
        elif resource["type"] != "S3":
            expected.append((index, "unsupported_type"))
    assert [(item.index, item.reason) for item in result.data.skipped] == expected
    assert result.data.generated_count <= len(resources) - len(expected)


@settings(max_examples=50)
@given(error=st.text(min_size=1, max_size=200))
def test_transfer_failure_has_no_data_and_preserves_error(error: str) -> None:
    """Failed file transfers always retain the generic typed failure envelope."""
    runtime = MagicMock()
    runtime.upload_file = AsyncMock(return_value={"success": False, "error": error})
    tool = _extended_tool(runtime, "sandbox.upload_file")
    result = asyncio.run(tool.fn(env_id="env", local_path="local", remote_path="remote"))
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.data is None
    assert result.error == error


def test_extended_tools_register_once_with_expected_categories() -> None:
    """The complete server registers one typed tool per name and category."""
    server = create_server(Runtime(MockAdapter()))
    tools = asyncio.run(server.list_tools())
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))
    expected = {
        "sandbox.list_environments": "deterministic",
        "sandbox.generate_cfn_from_recon": "deterministic",
        "sandbox.execute": "operational",
        "sandbox.upload_file": "operational",
        "sandbox.download_file": "operational",
        "sandbox.apply_service_mocks": "operational",
        "sandbox.workspace_dir": "operational",
        "sandbox.write_file": "operational",
        "sandbox.diff": "operational",
    }
    actual = {tool.name: getattr(tool.fn, "_mcp_category") for tool in tools if tool.name in expected}
    assert actual == expected


def test_service_mock_rejects_malformed_nested_config() -> None:
    """Service-mock ingress validates nested child models before runtime calls."""
    runtime = MagicMock()
    runtime.apply_service_mocks = AsyncMock()
    tool = _extended_tool(runtime, "sandbox.apply_service_mocks")
    with pytest.raises(SchemaMigrationError):
        asyncio.run(tool.fn(env_id="env", config={"rpc_service": {"service_stubs": "bad"}}))
    runtime.apply_service_mocks.assert_not_awaited()
