"""Portable Graph FastMCP contract tests."""
from __future__ import annotations

import inspect

import pytest

from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import reset_runtime
from factory.mcp_utils.runtime.tool_result import ToolResult


@pytest.fixture
def server():
    reset_runtime()
    yield create_mcp_server()
    reset_runtime()


@pytest.mark.asyncio
async def test_public_graph_surface_has_exactly_35_typed_tools(server):
    # 34 -> 35 (2026-09-16): graph_import split into graph_import_begin +
    # graph_import_page (paged transfer, see backup.py's module docstring
    # for why a single-call inline transfer couldn't stay under the 16 MiB
    # typed-egress cap once the graph outgrows ~11 MB raw).
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert len(tools) == 35
    retired = {"graph_query", "graph_record_run_findings", "graph_vector_search",
               "graph_hybrid_search", "graph_run_fastrp", "graph_create_vector_index"}
    assert not retired & tools.keys()
    for name, tool in tools.items():
        signature = inspect.signature(tool.fn)
        input_model = getattr(tool.fn, "_mcp_input_model")
        output_model = getattr(tool.fn, "_mcp_output_model")
        assert input_model.model_json_schema().get("additionalProperties") is False, name
        assert output_model.model_json_schema().get("type") == "object", name
        assert "ToolResult" in str(signature.return_annotation), name


@pytest.mark.asyncio
async def test_contract_and_dashboard_helpers_return_tool_results(server):
    for name, kwargs in {"graph_get_capabilities": {}, "graph_health_check": {},
                         "graph_describe_config_schema": {}, "graph_list_recent_runs": {},
                         "graph_get_dashboard_summary": {}, "graph_get_entity_context": {"entity_id": "missing"},
                         "graph_get_views": {}}.items():
        result = (await server.get_tool(name)).fn(**kwargs)
        assert isinstance(result, ToolResult)
        assert result.ok and result.data is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("graph_get_stats", {}),
        ("graph_get_entity", {"entity_id": "missing"}),
        ("graph_find_entities", {}),
    ],
)
async def test_unknown_backend_is_a_successful_domain_negative_envelope(server, tool_name, kwargs):
    result = (await server.get_tool(tool_name)).fn(backend="private-backend", **kwargs)

    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.error is None
    assert result.data is not None
    assert result.data.error == "unknown_backend"
    assert result.data.available == ["persistent_networkx", "networkx", "neo4j"]
    assert "private-backend" not in (result.data.available or [])
