"""Fresh-server contract coverage for Sandbox's complete typed MCP boundary."""
from __future__ import annotations

from inspect import signature

import pytest
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.interface import Runtime, create_server
from factory.sandbox.runtime.adapters.mock import MockAdapter


DETERMINISTIC = {
    "sandbox.get_capabilities", "sandbox.health_check", "sandbox.describe_config_schema",
    "sandbox.list_profiles", "sandbox.list_device_presets",
    "sandbox.list_environments", "sandbox.generate_cfn_from_recon",
    "sandbox.validate_manifest", "sandbox.list_live_launch_ids",
    "sandbox_get_dashboard_summary",
    "sandbox_get_environment_activity", "sandbox_get_environment_graph_context", "sandbox_get_views",
}
OPERATIONAL = {
    "sandbox.provision", "sandbox.terminate", "sandbox.get_status", "sandbox.execute",
    "sandbox.upload_file", "sandbox.download_file", "sandbox.apply_service_mocks",
    "sandbox.workspace_dir", "sandbox.write_file", "sandbox.diff",
    "sandbox.deploy_cfn", "sandbox.list_stacks",
    "sandbox.describe_stack", "sandbox.delete_stack", "sandbox.translate_cfn",
    "sandbox.plan_provision", "sandbox.apply_provision",
}
AUTHORING = {
    "sandbox.authoring.get_status", "sandbox.authoring.list_templates",
    "sandbox.authoring.upsert_template", "sandbox.authoring.delete_template",
}


def _server():
    return create_server(Runtime(MockAdapter()))


@pytest.mark.asyncio
async def test_fresh_server_has_exact_strict_typed_catalog() -> None:
    tools = await _server().list_tools()
    assert {tool.name for tool in tools} == DETERMINISTIC | OPERATIONAL | AUTHORING
    categories = {name: tool.fn._mcp_category for name, tool in ((t.name, t) for t in tools)}
    assert {name for name, category in categories.items() if category == "deterministic"} == DETERMINISTIC
    assert {name for name, category in categories.items() if category == "operational"} == OPERATIONAL
    assert {name for name, category in categories.items() if category == "authoring"} == AUTHORING
    assert len(DETERMINISTIC) == 13 and len(OPERATIONAL) == 17 and len(AUTHORING) == 4
    for tool in tools:
        input_model = getattr(tool.fn, "_mcp_input_model", None)
        output_model = getattr(tool.fn, "_mcp_output_model", None)
        assert input_model and output_model, tool.name
        assert input_model.__module__.startswith("factory.sandbox.mcp"), tool.name
        assert output_model.__module__.startswith("factory.sandbox.mcp"), tool.name
        assert input_model.model_config.get("extra") == "forbid", tool.name
        assert input_model.model_config.get("strict") is True, tool.name
        assert output_model.model_config.get("extra") == "forbid", tool.name
        assert output_model.model_config.get("strict") is True, tool.name
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


@pytest.mark.asyncio
async def test_typed_envelopes_flat_ingress_and_cfn_requirements() -> None:
    server = _server()
    provision = await server.get_tool("sandbox.provision")
    schema = provision.fn._mcp_input_model.model_json_schema(mode="validation")
    assert "schema_version" not in schema["properties"]
    result = await provision.fn(instance_type="t3.small", timeout_seconds=60)
    assert isinstance(result, ToolResult) and result.ok and result.data is not None

    execute = await server.get_tool("sandbox.execute")
    with pytest.raises(SchemaMigrationError):
        await execute.fn(env_id="", command="echo nope")

    list_stacks = await server.get_tool("sandbox.list_stacks")
    describe = await server.get_tool("sandbox.describe_stack")
    delete = await server.get_tool("sandbox.delete_stack")
    list_schema = list_stacks.fn._mcp_input_model.model_json_schema(mode="validation")
    describe_schema = describe.fn._mcp_input_model.model_json_schema(mode="validation")
    delete_schema = delete.fn._mcp_input_model.model_json_schema(mode="validation")
    assert list_schema["required"] == ["env_id"]
    assert describe_schema["required"] == ["env_id", "stack_name"]
    assert delete_schema["required"] == ["env_id", "stack_name"]
    with pytest.raises(SchemaMigrationError):
        await list_stacks.fn(env_id="env", stack_name="unexpected")


@pytest.mark.asyncio
async def test_capabilities_match_the_fresh_server_catalog() -> None:
    server = _server()
    result = (await server.get_tool("sandbox.get_capabilities")).fn()
    assert result.ok
    assert {name for names in result.data.tools.values() for name in names} == (
        DETERMINISTIC | OPERATIONAL | AUTHORING
    )


@pytest.mark.asyncio
async def test_authoring_is_enveloped_when_disabled_and_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SANDBOX_ENABLE_AUTHORING_TOOLS", raising=False)
    disabled = _server()
    status = (await disabled.get_tool("sandbox.authoring.get_status")).fn()
    listed = (await disabled.get_tool("sandbox.authoring.list_templates")).fn()
    assert status.ok and status.data.enabled is False
    assert not listed.ok and listed.error == "Authoring tools disabled"

    monkeypatch.setenv("SANDBOX_ENABLE_AUTHORING_TOOLS", "1")
    enabled = create_server(Runtime(MockAdapter()), config_dir=tmp_path)
    upsert = await enabled.get_tool("sandbox.authoring.upsert_template")
    saved = upsert.fn(id="sample", config={"instance_type": "mock"})
    assert saved.ok and saved.data.path.endswith("sample.yaml")


@pytest.mark.asyncio
async def test_resources_and_prompts_remain_native_protocol_surfaces() -> None:
    server = _server()
    resources = {str(resource.uri) for resource in await server.list_resources()}
    templates = {template.uri_template for template in await server.list_resource_templates()}
    prompts = {prompt.name for prompt in await server.list_prompts()}
    assert len(resources | templates) == 8
    assert "sandbox://docs/{doc_name}" in templates
    assert prompts == {"provision_environment", "execute_command", "debug_environment"}
