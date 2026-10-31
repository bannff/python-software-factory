"""Contract regression tests for the typed Workflow MCP boundary."""
from __future__ import annotations

import asyncio
from collections import Counter
from typing import get_type_hints

import pytest
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.workflow.mcp.contracts.base import DTO
from factory.workflow.server import create_mcp_server


EXPECTED_COUNTS = {"deterministic": 13, "operational": 14, "authoring": 4}


def _tools():
    return asyncio.run(create_mcp_server().list_tools())


def test_workflow_server_catalog_has_exact_typed_surface() -> None:
    tools = _tools()
    assert len(tools) == 31
    assert Counter(getattr(tool.fn, "_mcp_category", None) for tool in tools) == EXPECTED_COUNTS
    assert {tool.name for tool in tools} >= {
        "workflow.start_run", "workflow.executor.list_tasks",
        "workflow.authoring.get_status", "workflow_get_views",
        "workflow.start_loop", "workflow.get_loop", "workflow.stop_loop",
    }
    for tool in tools:
        fn = tool.fn
        input_model = getattr(fn, "_mcp_input_model", None)
        output_model = getattr(fn, "_mcp_output_model", None)
        assert input_model is not None and issubclass(input_model, DTO)
        assert output_model is not None and issubclass(output_model, DTO)
        assert input_model.model_config.get("extra") == "forbid"
        assert get_type_hints(fn)["return"] == ToolResult[output_model]


def test_typed_boundary_rejects_unknown_flat_kwargs() -> None:
    tool = asyncio.run(create_mcp_server().get_tool("workflow.health_check"))
    with pytest.raises(SchemaMigrationError):
        tool.fn(unexpected=True)


def test_dashboard_inputs_preserve_declared_defaults() -> None:
    mcp = create_mcp_server()
    expected = {
        "workflow_get_run_activity": 20,
        "workflow_get_run_graph_context": 12,
        "workflow_get_run_tasks": 20,
    }
    for name, limit in expected.items():
        tool = asyncio.run(mcp.get_tool(name))
        assert tool.fn._mcp_input_model.model_fields["limit"].default == limit


def test_views_and_disabled_authoring_are_enveloped() -> None:
    mcp = create_mcp_server()
    views = asyncio.run(mcp.get_tool("workflow_get_views")).fn()
    status = asyncio.run(mcp.get_tool("workflow.authoring.get_status")).fn()
    mutation = asyncio.run(mcp.get_tool("workflow.authoring.delete_workflow_definition")).fn(id="demo")
    assert views.ok and views.data is not None and views.data.views
    assert status.ok and status.data is not None and not status.data.enabled
    assert not mutation.ok and mutation.data is None and mutation.error
    actions = next(component for component in views.data.views[0]["components"] if component["id"] == "workflow-actions")
    delete_action = next(action for action in actions["props"]["actions"] if action["id"] == "delete-def")
    assert delete_action["fields"][0]["name"] == "id"
