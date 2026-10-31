"""Strict public MCP contract tests for the Test brick."""
from __future__ import annotations

import asyncio
import inspect
import json

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.test.interface import TestRuntime, create_server


_DETERMINISTIC = {
    "test_get_capabilities", "test_health_check", "test_describe_config_schema",
    "test_discover", "test_compare_junit",
}
_OPERATIONAL = {"test_run_all", "test_run_component", "test_run_path", "test_list_files"}
_AUTHORING = {
    "test_authoring_get_status", "test_authoring_set_adapter", "test_authoring_set_timeout",
    "test_authoring_set_pattern", "test_authoring_set_verbose",
}


def _server():
    return create_server(TestRuntime(adapter_type="memory"))


def _tool(name: str):
    return asyncio.run(_server().get_tool(name))


def test_catalog_is_exact_and_categories_are_preserved() -> None:
    tools = {tool.name: tool for tool in asyncio.run(_server().list_tools())}
    expected = _DETERMINISTIC | _OPERATIONAL | _AUTHORING
    assert set(tools) == expected
    assert {n for n, t in tools.items() if t.fn._mcp_category == "deterministic"} == _DETERMINISTIC
    assert {n for n, t in tools.items() if t.fn._mcp_category == "operational"} == _OPERATIONAL
    assert {n for n, t in tools.items() if t.fn._mcp_category == "authoring"} == _AUTHORING


def test_every_tool_has_local_strict_dtos_and_exact_egress() -> None:
    for tool in asyncio.run(_server().list_tools()):
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__ == "factory.test.mcp.contracts"
        assert output_model.__module__ == "factory.test.mcp.contracts"
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert str(inspect.signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_flat_defaults_and_unknown_kwargs_are_preserved() -> None:
    expected_defaults = {
        "test_discover": {"path": ".", "pattern": "test_*.py"},
        "test_run_all": {"verbose": False},
        "test_run_component": {"verbose": False},
        "test_run_path": {"pattern": "test_*.py", "verbose": False},
    }
    for name, fields in expected_defaults.items():
        parameters = inspect.signature(_tool(name).fn).parameters
        for field, default in fields.items():
            assert parameters[field].default == default
    with pytest.raises(Exception):
        _tool("test_get_capabilities").fn(unexpected=True)
    with pytest.raises(Exception):
        _tool("test_run_path").fn(path=".", unexpected=True)


def test_contract_tools_return_typed_data() -> None:
    capabilities = _tool("test_get_capabilities").fn()
    assert isinstance(capabilities, ToolResult) and capabilities.ok
    assert capabilities.data.name == "test"
    assert capabilities.data.config_dir
    assert capabilities.data.features.adapters == ["pytest", "memory"]

    health = _tool("test_health_check").fn()
    assert health.ok and health.data.status in {"healthy", "unhealthy", "unknown"}
    assert health.data.config_dir

    schema = _tool("test_describe_config_schema").fn()
    assert schema.ok and schema.data.schema_definition["type"] == "object"
    assert "adapter" in schema.data.schema_definition["properties"]


def test_discovery_and_execution_use_typed_data(tmp_path) -> None:
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    mcp = create_server(runtime)
    discover = asyncio.run(mcp.get_tool("test_discover")).fn(path=".")
    assert discover.ok and discover.data.target == "."
    result = asyncio.run(mcp.get_tool("test_run_path")).fn(path=".")
    assert result.ok and result.data.outcome == "passed"
    assert result.data.success is True


@pytest.mark.parametrize("name", sorted(_DETERMINISTIC | _OPERATIONAL | _AUTHORING))
def test_every_tool_rejects_unknown_fields(name: str) -> None:
    with pytest.raises(Exception):
        _tool(name).fn(unexpected=True)


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("test_discover", {"path": 1}),
        ("test_compare_junit", {"base_report": 1, "candidate_report": "x"}),
        ("test_run_all", {"verbose": "false"}),
        ("test_run_component", {"component_name": 1}),
        ("test_run_path", {"path": ".", "pattern": 1}),
        ("test_authoring_set_adapter", {"adapter": 1}),
        ("test_authoring_set_timeout", {"timeout_seconds": "3"}),
        ("test_authoring_set_pattern", {"pattern": 1}),
        ("test_authoring_set_verbose", {"verbose": 1}),
    ],
)
def test_public_ingress_rejects_non_coercive_values(name: str, kwargs: dict) -> None:
    with pytest.raises(Exception):
        _tool(name).fn(**kwargs)


def test_valid_component_and_list_tools_use_typed_data(tmp_path) -> None:
    target = tmp_path / "components" / "example" / "test"
    target.mkdir(parents=True)
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    component = asyncio.run(mcp.get_tool("test_run_component")).fn(component_name="example")
    listed = asyncio.run(mcp.get_tool("test_list_files")).fn()
    assert component.ok and component.data.target == "components/example/test"
    assert listed.ok and listed.data.count == 0


def test_result_resource_schema_declares_typed_error_field(tmp_path) -> None:
    async def read() -> str:
        mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
        result = await mcp.read_resource("test://schemas/result")
        return result.contents[0].content

    schema = json.loads(asyncio.run(read()))
    data_schema = schema["properties"]["data"]
    assert {
        item["$ref"].rsplit("/", 1)[-1]
        for item in data_schema["anyOf"] if "$ref" in item
    } == {
        "CapabilitiesOutput", "HealthOutput", "ConfigSchemaOutput", "DiscoveryOutput",
        "JunitCompareOutput", "ExecutionOutput", "ListFilesOutput",
        "AuthoringStatusOutput", "MutationOutput",
    }
    assert schema["$defs"]["ExecutionOutput"]["properties"]["error"]["anyOf"] == [
        {"type": "string"}, {"type": "null"}
    ]
    assert schema["$defs"]["JunitCompareOutput"]["additionalProperties"] is False



def test_public_status_and_info_do_not_expose_absolute_config_or_root(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "configured-secrets"
    monkeypatch.setenv("TEST_CONFIG_DIR", str(config_dir))
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))
    capabilities = _tool("test_get_capabilities").fn()
    health = _tool("test_health_check").fn()
    status = _tool("test_authoring_get_status").fn()

    async def read_info() -> str:
        result = await mcp.read_resource("test://info")
        return result.contents[0].content

    info = asyncio.run(read_info())
    assert capabilities.data.config_dir == "<configured>"
    assert health.data.config_dir == "<configured>"
    assert status.data.config_dir == "<configured>"
    assert str(config_dir) not in str(capabilities)
    assert str(config_dir) not in str(health)
    assert str(config_dir) not in str(status)
    assert str(tmp_path) not in info
    assert "<test-root>" in info and "error" not in info
