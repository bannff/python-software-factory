"""Public native MCP-v2 transport coverage for the Test brick."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from factory.mcp_utils.interface import SchemaMigrationError
from factory.test.interface import TestResult, TestRuntime, create_server
from factory.test.runtime.junit_fixtures import case, write_report


_TOOL_ARGS = {
    "test_get_capabilities": {},
    "test_health_check": {},
    "test_describe_config_schema": {},
    "test_discover": {"path": "target"},
    "test_compare_junit": {"base_report": "base.xml", "candidate_report": "candidate.xml"},
    "test_run_all": {},
    "test_run_component": {"component_name": "missing"},
    "test_run_path": {"path": "target"},
    "test_list_files": {},
    "test_authoring_get_status": {},
    "test_authoring_set_adapter": {"adapter": "memory"},
    "test_authoring_set_timeout": {"timeout_seconds": 11},
    "test_authoring_set_pattern": {"pattern": "spec_*.py"},
    "test_authoring_set_verbose": {"verbose": False},
}


def test_all_fourteen_tools_cross_public_transport(tmp_path) -> None:
    write_report(tmp_path / "base.xml", case("test_debt", "failure"))
    write_report(tmp_path / "candidate.xml", case("test_debt"))
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))

    async def exercise() -> list[tuple[str, dict]]:
        results = []
        for name, arguments in _TOOL_ARGS.items():
            result = await mcp.call_tool(name, arguments)
            assert result.is_error is False, (name, result)
            assert result.structured_content is not None
            envelope = result.structured_content
            assert {"schema_version", "ok", "data", "error", "idempotency_key"} <= envelope.keys()
            assert envelope["schema_version"] == "v1"
            assert envelope["ok"] is True
            results.append((name, envelope))
        return results

    results = dict(asyncio.run(exercise()))
    assert results["test_compare_junit"]["data"]["resolved_count"] == 1


def test_public_transport_rejects_coercion_before_runtime(tmp_path) -> None:
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.set_default_timeout(19)
    mcp = create_server(runtime)

    with pytest.raises(SchemaMigrationError):
        asyncio.run(mcp.call_tool("test_authoring_set_timeout", {"timeout_seconds": "12"}))
    with pytest.raises(SchemaMigrationError):
        asyncio.run(mcp.call_tool("test_run_path", {"path": ".", "verbose": "false"}))
    assert runtime.timeout_seconds == 19


def test_public_transport_preserves_omitted_authored_defaults(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    adapter = MagicMock()
    adapter.run_tests.return_value = TestResult(passed=1)
    runtime.set_adapter(adapter)
    mcp = create_server(runtime)

    async def exercise():
        await mcp.call_tool("test_authoring_set_pattern", {"pattern": "spec_*.py"})
        await mcp.call_tool("test_authoring_set_verbose", {"verbose": True})
        omitted = await mcp.call_tool("test_run_path", {"path": "target"})
        explicit = await mcp.call_tool(
            "test_run_path",
            {"path": "target", "pattern": "test_*.py", "verbose": False},
        )
        return omitted, explicit

    omitted, explicit = asyncio.run(exercise())
    assert omitted.is_error is False and explicit.is_error is False
    assert adapter.run_tests.call_args_list[0].args == ("target", "spec_*.py", True)
    assert adapter.run_tests.call_args_list[1].args == ("target", "test_*.py", False)


def test_public_resources_templates_and_prompts_are_registered(tmp_path) -> None:
    mcp = create_server(TestRuntime(root_dir=tmp_path, adapter_type="memory"))

    async def inspect_server():
        resources = await mcp.list_resources()
        templates = await mcp.list_resource_templates()
        prompts = await mcp.list_prompts()
        config = json.loads((await mcp.read_resource("test://schemas/config")).contents[0].content)
        result = json.loads((await mcp.read_resource("test://schemas/result")).contents[0].content)
        return resources, templates, prompts, config, result

    resources, templates, prompts, config, result = asyncio.run(inspect_server())
    assert {str(item.uri) for item in resources} >= {
        "test://schemas/config", "test://schemas/result", "test://docs",
        "test://info", "test://adapters", "test://factory",
    }
    assert "test://docs/{doc_name}" in {str(item.uri_template) for item in templates}
    assert {item.name for item in prompts} == {"run_tests", "debug_failure", "add_tests"}
    assert config["properties"]["adapter"]["default"] == "pytest"
    assert config["required"] == [] and config["additionalProperties"] is False
    assert result["properties"]["idempotency_key"]["anyOf"] == [
        {"type": "string", "maxLength": 256}, {"type": "null"}
    ]
    assert result["properties"]["data"]["anyOf"]
    assert {
        item["$ref"].rsplit("/", 1)[-1]
        for item in result["properties"]["data"]["anyOf"] if "$ref" in item
    } == {
        "CapabilitiesOutput", "HealthOutput", "ConfigSchemaOutput", "DiscoveryOutput",
        "JunitCompareOutput", "ExecutionOutput", "ListFilesOutput",
        "AuthoringStatusOutput", "MutationOutput",
    }
