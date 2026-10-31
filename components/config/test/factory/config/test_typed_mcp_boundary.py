"""Full strict DTO and behavior inventory for Config's eleven MCP tools."""
from __future__ import annotations

import asyncio
from inspect import signature

import pytest

from factory.config.runtime.runtime import ConfigRuntime
from factory.config.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError


DETERMINISTIC = {
    "get_capabilities", "health_check", "describe_config_schema", "config_environment",
    "config_get_aws_identity",
}
OPERATIONAL = {
    "config_get", "config_set", "config_delete", "config_keys", "config_get_all",
    "config_get_typed",
}


def _tools(runtime: ConfigRuntime):
    return {tool.name: tool for tool in asyncio.run(create_mcp_server(runtime).list_tools())}


def test_all_eleven_tools_have_strict_same_brick_dto_boundaries() -> None:
    tools = _tools(ConfigRuntime())
    assert set(tools) == DETERMINISTIC | OPERATIONAL
    assert sum(tool.fn._mcp_category == "deterministic" for tool in tools.values()) == 5
    assert sum(tool.fn._mcp_category == "operational" for tool in tools.values()) == 6
    for name, tool in tools.items():
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__ == "factory.config.mcp.contracts", name
        assert output_model.__module__ == "factory.config.mcp.contracts", name
        assert input_model.model_config["extra"] == "forbid", name
        assert input_model.model_config["strict"] is True, name
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_flat_defaults_and_raw_strict_ingress_are_preserved() -> None:
    tools = _tools(ConfigRuntime())
    assert signature(tools["config_get"].fn).parameters["default"].default is None
    assert signature(tools["config_keys"].fn).parameters["prefix"].default == ""
    assert signature(tools["config_get_all"].fn).parameters["prefix"].default == ""
    assert signature(tools["config_get_typed"].fn).parameters["value_type"].default == "str"
    assert signature(tools["config_get_aws_identity"].fn).parameters["force_refresh"].default is False
    with pytest.raises(Exception):
        tools["config_get"].fn(key=1)
    with pytest.raises(Exception):
        tools["config_get_aws_identity"].fn(force_refresh="true")
    with pytest.raises(Exception):
        tools["config_keys"].fn(prefix="", unexpected=True)


def test_config_operations_preserve_success_and_normal_negative_semantics() -> None:
    tools = _tools(ConfigRuntime())
    set_result = tools["config_set"].fn(key="typed.boundary.answer", value="42")
    assert isinstance(set_result, ToolResult) and set_result.ok and set_result.data.success
    found = tools["config_get"].fn(key="typed.boundary.answer", default="fallback")
    missing = tools["config_get"].fn(key="typed.boundary.missing", default="fallback")
    assert found.ok and found.data.value == "42" and found.data.found is True
    assert missing.ok and missing.data.value == "fallback" and missing.data.found is False
    keys = tools["config_keys"].fn(prefix="typed.boundary")
    values = tools["config_get_all"].fn(prefix="typed.boundary")
    assert keys.ok and "typed.boundary.answer" in keys.data.keys
    assert values.ok and values.data.values["typed.boundary.answer"] == "42"
    assert tools["config_delete"].fn(key="typed.boundary.answer").data.deleted is True


@pytest.mark.parametrize(("label", "raw", "expected"), [
    ("str", "42", "42"), ("int", "42", 42), ("bool", "true", True), ("float", "1.5", 1.5),
])
def test_typed_get_preserves_all_legacy_type_conversions(
    label: str, raw: str, expected: str | int | bool | float,
) -> None:
    tools = _tools(ConfigRuntime())
    assert tools["config_set"].fn(key="typed.boundary.value", value=raw).ok
    result = tools["config_get_typed"].fn(key="typed.boundary.value", value_type=label)
    assert result.ok and result.data.value == expected and result.data.type == label


def test_typed_get_keeps_unknown_label_string_fallback_and_echo() -> None:
    tools = _tools(ConfigRuntime())
    tools["config_set"].fn(key="typed.boundary.legacy", value="17")
    result = tools["config_get_typed"].fn(key="typed.boundary.legacy", value_type="legacy-label")
    assert result.ok and result.data.value == "17"
    assert result.data.type == "legacy-label" and result.data.found is True


def test_health_schema_environment_and_aws_identity_are_concrete_envelopes() -> None:
    tools = _tools(ConfigRuntime(environment="test"))
    assert tools["config_environment"].fn().data.environment == "test"
    assert tools["health_check"].fn().data.configs == {}
    assert tools["describe_config_schema"].fn().data.properties["region"].description
    identity = tools["config_get_aws_identity"].fn()
    assert identity.ok and isinstance(identity.data.available, bool)
    assert identity.data.profile is None or isinstance(identity.data.profile, str)


def _call(server: object, name: str, arguments: dict[str, object] | None = None):
    """Invoke the public native MCP-v2 transport rather than the wrapped function."""
    return asyncio.run(server.call_tool(name, arguments or {}))


def _envelope(result: object) -> dict[str, object]:
    assert result.is_error is False
    envelope = result.structured_content
    assert envelope is not None
    assert envelope["schema_version"] == "v1"
    assert envelope["ok"] is True
    assert envelope["error"] is None
    return envelope


def test_all_eleven_tools_publish_successful_public_envelopes() -> None:
    server = create_mcp_server(ConfigRuntime(environment="test"))
    calls = {
        "get_capabilities": {}, "health_check": {}, "describe_config_schema": {},
        "config_environment": {}, "config_get_aws_identity": {},
        "config_get": {"key": "missing"}, "config_set": {"key": "saved", "value": "value"},
        "config_delete": {"key": "missing"}, "config_keys": {}, "config_get_all": {},
        "config_get_typed": {"key": "missing"},
    }
    for name, arguments in calls.items():
        _envelope(_call(server, name, arguments))
    assert _envelope(_call(server, "config_keys"))["data"]["prefix"] == ""
    assert _envelope(_call(server, "config_get_typed", {"key": "missing"}))["data"]["type"] == "str"


@pytest.mark.parametrize("arguments", [{"key": 1}, {"key": "key", "unexpected": True}])
def test_public_transport_rejects_coercion_and_unknown_fields(arguments: dict[str, object]) -> None:
    with pytest.raises(SchemaMigrationError):
        _call(create_mcp_server(ConfigRuntime()), "config_get", arguments)
