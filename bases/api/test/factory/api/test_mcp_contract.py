"""Fresh-server strict MCP boundary tests for the API base."""

from __future__ import annotations

from inspect import signature

import pytest
from pydantic import ValidationError
from factory.api.runtime.runtime import APIRuntime, reset_runtime
from factory.api.server import create_mcp_server
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.runtime.tool_result import ToolResult


DETERMINISTIC = {
    "api_get_capabilities", "api_health_check", "api_describe_config_schema",
    "api_list_routes", "api_get_openapi_schema",
}
OPERATIONAL = {
    "api.add_route", "api.remove_route", "api.switch_adapter",
}
AUTHORING = {
    "api.authoring.get_status", "api.authoring.set_config", "api.authoring.reset_routes",
}


@pytest.fixture(autouse=True)
def reset_state():
    reset_runtime()
    yield
    reset_runtime()


def _server(*, authoring: bool = False):
    return create_mcp_server(APIRuntime(), enable_authoring=authoring)


@pytest.mark.asyncio
async def test_fresh_server_has_exact_strict_typed_catalog() -> None:
    tools = await _server().list_tools()
    assert {tool.name for tool in tools} == DETERMINISTIC | OPERATIONAL | AUTHORING
    assert len(DETERMINISTIC) == 5 and len(OPERATIONAL) == 3 and len(AUTHORING) == 3
    categories = {tool.name: tool.fn._mcp_category for tool in tools}
    assert {name for name, category in categories.items() if category == "deterministic"} == DETERMINISTIC
    assert {name for name, category in categories.items() if category == "operational"} == OPERATIONAL
    assert {name for name, category in categories.items() if category == "authoring"} == AUTHORING
    for tool in tools:
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__.startswith("factory.api.mcp.contracts")
        assert output_model.__module__.startswith("factory.api.mcp.contracts")
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert output_model.model_config.get("extra") == "forbid"
        assert output_model.model_config.get("strict") is True
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


@pytest.mark.asyncio
async def test_flat_defaults_and_strict_ingress_are_preserved() -> None:
    server = _server()
    add = await server.get_tool("api.add_route")
    schema = add.fn._mcp_input_model.model_json_schema(mode="validation")
    assert schema["properties"]["method"]["default"] == "GET"
    assert schema["properties"]["handler_name"]["default"] == "noop"
    result = add.fn(path="/users")
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.method == "GET" and result.data.handler == "noop"
    with pytest.raises(SchemaMigrationError):
        add.fn(path="/users", unknown=True)
    with pytest.raises(SchemaMigrationError):
        add.fn(path="/users", method=1)
    with pytest.raises(ValidationError):
        add.fn._mcp_input_model.model_validate({"path": "/users", "method": 1})
    with pytest.raises(ValidationError):
        add.fn._mcp_input_model.model_validate({"path": "/users", "unknown": True})


@pytest.mark.asyncio
async def test_expected_negative_outcomes_are_typed_success_data() -> None:
    server = _server()
    switch = await server.get_tool("api.switch_adapter")
    invalid = switch.fn(adapter_type="grpc")
    assert invalid.ok and not invalid.data.switched
    assert invalid.data.error == "Unknown adapter: grpc"
    assert invalid.data.available == ["rest", "graphql"]

    authoring = await server.get_tool("api.authoring.set_config")
    disabled = authoring.fn(title="Ignored")
    assert disabled.ok and not disabled.data.updated
    assert disabled.data.error == "Authoring is disabled"

    switch.fn(adapter_type="graphql")
    schema = (await server.get_tool("api_get_openapi_schema")).fn()
    assert schema.ok and not schema.data.supported
    assert schema.data.error == "OpenAPI not supported by this adapter"


@pytest.mark.asyncio
async def test_unexpected_errors_become_typed_boundary_failures(monkeypatch) -> None:
    runtime = APIRuntime()

    def _raise():
        raise RuntimeError("internal adapter failure")

    monkeypatch.setattr(runtime, "health_check", _raise)
    result = (await create_mcp_server(runtime).get_tool("api_health_check")).fn()
    assert not result.ok and result.data is None and result.error


@pytest.mark.asyncio
async def test_authoring_tools_remain_registered_and_enveloped_when_enabled() -> None:
    server = _server(authoring=True)
    set_config = await server.get_tool("api.authoring.set_config")
    configured = set_config.fn(adapter_type="graphql", title="Factory")
    assert configured.ok and configured.data.updated
    assert configured.data.changes.adapter == "graphql"
    reset = (await server.get_tool("api.authoring.reset_routes")).fn()
    assert reset.ok and reset.data.reset
