"""Regression tests for Config's required typed contract tools."""
from __future__ import annotations

import asyncio

import pytest

from factory.config.runtime.runtime import reset_runtime
from factory.config.server import get_mcp_server
from factory.mcp_utils.interface import ToolResult


def _get_tool(name: str):
    return asyncio.run(get_mcp_server().get_tool(name))


@pytest.fixture(autouse=True)
def reset_state():
    reset_runtime()
    yield
    reset_runtime()


@pytest.mark.parametrize("name", ["get_capabilities", "health_check", "describe_config_schema"])
def test_required_contract_tools_are_registered(name: str) -> None:
    assert _get_tool(name) is not None


def test_capabilities_are_returned_inside_a_typed_envelope() -> None:
    result = _get_tool("get_capabilities").fn()
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.name == "config"
    assert "key_value" in result.data.features


def test_health_check_preserves_no_config_message() -> None:
    result = _get_tool("health_check").fn()
    assert result.ok and result.data.healthy
    assert result.data.configs == {}
    assert result.data.message == "No configs initialized"


def test_schema_has_concrete_backend_property() -> None:
    result = _get_tool("describe_config_schema").fn()
    assert result.ok and result.data.type == "object"
    assert result.data.properties["backend"].enum == ["env", "file", "ssm"]
