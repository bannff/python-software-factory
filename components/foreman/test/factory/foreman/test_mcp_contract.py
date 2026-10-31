"""Contract tests for Foreman's complete strict typed FastMCP surface."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError

from factory.foreman.mcp_contract_check import inventory_mcp_contracts
from factory.foreman.runtime.runtime import ForemanRuntime
from factory.foreman.server import create_server
from factory.mcp_utils.interface import ToolResult


_DETERMINISTIC = {
    "get_capabilities", "health_check", "describe_config_schema", "foreman_info",
    "foreman_check", "foreman_guardian_check", "foreman_get_repo_guardrails",
    "foreman_build_bricks_index", "foreman_resolve_dependencies",
}
_OPERATIONAL = {
    "foreman_create_component", "foreman_create_base", "foreman_write_bricks_index",
    "foreman_create_project", "foreman_sync_brick_deps",
}


def _tool(name: str):
    return asyncio.run(create_server().get_tool(name))


def test_catalog_is_exact_and_categories_are_preserved() -> None:
    tools = {tool.name: tool for tool in asyncio.run(create_server().list_tools())}
    assert set(tools) == _DETERMINISTIC | _OPERATIONAL
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "deterministic"} == _DETERMINISTIC
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "operational"} == _OPERATIONAL


def test_registered_tools_have_public_descriptions() -> None:
    tools = asyncio.run(create_server().list_tools())
    assert all(tool.description and tool.description.strip() for tool in tools)


def test_contract_tools_return_typed_envelopes_with_typed_data() -> None:
    result = _tool("get_capabilities").fn()
    assert isinstance(result, ToolResult)
    assert result.ok and result.data is not None
    assert result.data.schema_version == 1
    assert result.data.tooling.deterministic == sorted(_DETERMINISTIC, key=result.data.tooling.deterministic.index)
    assert result.data.tooling.operational == sorted(_OPERATIONAL, key=result.data.tooling.operational.index)

    health = _tool("health_check").fn()
    assert health.ok and health.data is not None
    assert health.data.details.server == "foreman"


def test_flat_ingress_rejects_unknown_fields_and_keeps_defaults() -> None:
    guardian = _tool("foreman_guardian_check")
    with pytest.raises(SchemaMigrationError):
        guardian.fn(unexpected=True)
    parameters = inspect.signature(guardian.fn).parameters
    assert parameters["file_size_mode"].default == "strict"
    assert parameters["base_sha"].default is None


def test_workspace_information_is_a_representative_typed_outcome() -> None:
    result = _tool("foreman_info").fn()
    assert result.ok and result.data is not None
    assert result.data.components_count == len(result.data.components)
    assert result.data.projects_count == len(result.data.projects)

    index = _tool("foreman_build_bricks_index").fn()
    assert index.ok and index.data is not None
    assert index.data.bricks.components


def test_foreman_has_no_static_contract_inventory_findings() -> None:
    root = Path(__file__).parents[5]
    violations = inventory_mcp_contracts(root)
    assert not [item for item in violations if item["brick"] == "foreman"]


def test_runtime_exposes_pr_ratchet_inputs_with_strict_defaults() -> None:
    parameters = inspect.signature(ForemanRuntime.check_all).parameters
    assert parameters["file_size_mode"].default == "strict"
    assert parameters["base_sha"].default is None
