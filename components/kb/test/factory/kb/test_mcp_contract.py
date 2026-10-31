"""Contract tests for typed KB deterministic and authoring MCP tools."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from factory.kb.runtime.collections import CollectionStats
from factory.kb.server import create_mcp_server
from factory.mcp_utils.runtime.tool_result import ToolResult


@pytest.fixture
def mcp(temp_config_dir):
    runtime = MagicMock()
    runtime._vector_store = None
    runtime.get_collection_registry.return_value.list_all.return_value = []
    runtime.get_collection_stats.return_value = CollectionStats(
        collection_id="default", document_count=0, total_size_bytes=0,
    )
    return create_mcp_server(runtime)


def _get_tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))


@pytest.mark.parametrize(
    "name",
    ["get_capabilities", "health_check", "describe_config_schema",
     "get_collection_registry", "get_collection_stats"],
)
def test_deterministic_tools_are_registered(mcp, name: str) -> None:
    assert _get_tool(mcp, name) is not None


@pytest.mark.parametrize(
    "name, arguments",
    [
        ("get_capabilities", {}), ("health_check", {}),
        ("describe_config_schema", {}), ("get_collection_registry", {}),
        ("get_collection_stats", {}),
    ],
)
def test_deterministic_tools_return_typed_envelopes(mcp, name, arguments) -> None:
    result = _get_tool(mcp, name).fn(**arguments)
    assert isinstance(result, ToolResult)
    assert result.ok is True and result.data is not None


def test_collection_stats_schema_constrains_collection_id(mcp) -> None:
    tool = _get_tool(mcp, "get_collection_stats")
    properties = tool.fn._mcp_input_model.model_json_schema()["properties"]
    assert properties["collection_id"]["anyOf"][0]["minLength"] == 1


@pytest.mark.parametrize(
    "name, arguments",
    [
        ("authoring.get_status", {}),
        ("authoring.validate_collections", {"dry_run": True}),
        ("authoring.upsert_collection", {
            "collection_id": "test", "collection_data": {"id": "test", "name": "Test"},
            "dry_run": True,
        }),
        ("authoring.delete_collection", {"collection_id": "test"}),
    ],
)
def test_authoring_tools_return_typed_envelopes_when_disabled(
    mcp, name, arguments, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KB_ENABLE_AUTHORING_TOOLS", raising=False)
    result = _get_tool(mcp, name).fn(**arguments)
    assert isinstance(result, ToolResult)
    assert result.ok is True and result.data is not None
    if name != "authoring.get_status":
        assert result.data.ok is False
