"""Exhaustive Cache typed-boundary inventory regressions."""
from __future__ import annotations

import asyncio
from inspect import signature
from typing import Any

import pytest

from factory.cache.runtime.runtime import CacheRuntime
from factory.cache.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError


_DIRECT_CALLS = {
    "get_capabilities": {}, "health_check": {}, "describe_config_schema": {},
    "cache_get_views": {}, "cache_get": {"key": "missing"},
    "cache_set": {"key": "saved", "value": "value"},
    "cache_delete": {"key": "missing"}, "cache_keys": {}, "cache_stats": {},
    "cache_clear": {}, "cache_exists": {"key": "missing"},
    "cache_ttl": {"key": "missing"},
}
_STRICT_REJECTIONS = [
    ("get_capabilities", {"unexpected": True}),
    ("health_check", {"unexpected": True}),
    ("describe_config_schema", {"unexpected": True}),
    ("cache_get_views", {"unexpected": True}),
    ("cache_get", {"key": 1}),
    ("cache_set", {"key": "key", "value": 1}),
    ("cache_delete", {"key": 1}),
    ("cache_keys", {"pattern": 1}),
    ("cache_stats", {"unexpected": True}),
    ("cache_clear", {"unexpected": True}),
    ("cache_exists", {"key": 1}),
    ("cache_ttl", {"key": 1}),
]


def _server() -> tuple[CacheRuntime, Any]:
    runtime = CacheRuntime()
    runtime.get_cache("memory")
    return runtime, create_mcp_server(runtime)


def _tools(server: Any) -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def _call(server: Any, name: str, arguments: dict[str, object]) -> Any:
    return asyncio.run(server.call_tool(name, arguments))


def _data(result: Any) -> dict[str, Any]:
    assert result.is_error is False
    envelope = result.structured_content
    assert envelope["ok"] is True
    return envelope["data"]


def test_all_twelve_tools_use_strict_cache_local_dtos_and_exact_egress() -> None:
    _, server = _server()
    tools = _tools(server)
    assert set(tools) == set(_DIRECT_CALLS)
    for name, tool in tools.items():
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__.startswith("factory.cache.mcp.contracts"), name
        assert output_model.__module__.startswith("factory.cache.mcp.contracts"), name
        for model in (input_model, output_model):
            assert model.model_config.get("extra") == "forbid", name
            assert model.model_config.get("strict") is True, name
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]", name


@pytest.mark.parametrize(("name", "arguments"), _DIRECT_CALLS.items())
def test_every_direct_handler_returns_a_tool_result(name: str, arguments: dict[str, object]) -> None:
    _, server = _server()
    assert isinstance(_tools(server)[name].fn(**arguments), ToolResult)


@pytest.mark.parametrize(("name", "arguments"), _STRICT_REJECTIONS)
def test_transport_rejects_invalid_arguments_for_every_tool(name: str, arguments: dict[str, object]) -> None:
    _, server = _server()
    tool = _tools(server)[name]
    with pytest.raises(SchemaMigrationError):
        tool.fn(**arguments)


def test_capabilities_and_health_publish_their_semantic_contracts() -> None:
    _, server = _server()
    capabilities = _data(_call(server, "get_capabilities", {}))
    assert capabilities["name"] == "cache"
    assert isinstance(capabilities["version"], str) and capabilities["version"]
    assert isinstance(capabilities["backends"], list)
    assert "key_value" in capabilities["features"]
    assert isinstance(_data(_call(server, "health_check", {}))["healthy"], bool)


def test_cache_keys_preserves_a_successful_typed_listing_above_ten_thousand() -> None:
    runtime, server = _server()
    cache = runtime.get_cache()
    for index in range(10_001):
        cache.set(f"large:{index}", "value")
    result = _call(server, "cache_keys", {"pattern": "large:*"})
    data = _data(result)
    assert data["count"] == 10_001
    assert len(data["keys"]) == 10_001
    assert all(isinstance(key, str) for key in data["keys"])
