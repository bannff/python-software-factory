"""Boundary tests for every public Blueprint FastMCP tool."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest
from factory.blueprint.server import get_mcp_server
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.interface import ToolResult


EXPECTED_CATEGORIES = {
    "blueprint_get_capabilities": "deterministic",
    "blueprint_health_check": "deterministic",
    "blueprint_describe_config_schema": "deterministic",
    "blueprint_get_service_url": "deterministic",
    "blueprint_list_services": "deterministic",
    "blueprint_list_supported_services": "deterministic",
    "blueprint_validate_specs": "deterministic",
    "blueprint_update_service_url": "authoring",
}
UNCATEGORIZED = {
    "blueprint_generate_dockerfile", "blueprint_generate_compose", "blueprint_generate_makefile",
    "blueprint_generate_env", "blueprint_generate_all", "blueprint_introspect_project",
    "blueprint_generate_cdk", "blueprint_generate_pipeline",
}


def _tools():
    mcp = get_mcp_server()
    return {name: asyncio.run(mcp.get_tool(name)) for name in set(EXPECTED_CATEGORIES) | UNCATEGORIZED}


def test_full_catalog_has_strict_typed_contracts() -> None:
    tools = _tools()
    assert len(tools) == 16
    for name, tool in tools.items():
        function = tool.fn
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        assert input_model.model_config["extra"] == "forbid", name
        return_type = get_type_hints(function)["return"]
        assert return_type.__pydantic_generic_metadata__["origin"] is ToolResult, name
        assert return_type.__pydantic_generic_metadata__["args"][0] is output_model, name


def test_categories_preserve_existing_catalog() -> None:
    for name, tool in _tools().items():
        if name in UNCATEGORIZED:
            assert not hasattr(tool.fn, "_mcp_category"), name
        else:
            assert tool.fn._mcp_category == EXPECTED_CATEGORIES[name]


def test_unknown_kwargs_are_rejected() -> None:
    tool = _tools()["blueprint_generate_pipeline"]
    with pytest.raises(SchemaMigrationError):
        tool.fn(renderer="github_actions", unexpected=True)


def test_missing_project_is_successful_typed_negative() -> None:
    result = _tools()["blueprint_generate_makefile"].fn(project_name="missing-project")
    assert result.ok is True
    assert result.data.found is False
    assert result.data.error


def test_authoring_mutation_remains_process_local() -> None:
    result = _tools()["blueprint_update_service_url"].fn(service_name="local", url="http://example.test")
    assert result.ok is True
    service = _tools()["blueprint_get_service_url"].fn(service_name="local")
    assert service.ok is True
    assert service.data.url == "http://example.test"
