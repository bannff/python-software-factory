"""Infrastructure-free tests for the KB FastMCP server."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from factory.kb.runtime.collections import CollectionStats
from factory.kb.runtime.models import Document, IngestResult, SearchResult
from factory.kb.server import create_mcp_server
from factory.mcp_utils.runtime.tool_result import ToolResult


@pytest.fixture
def mcp(temp_config_dir):
    runtime = MagicMock()
    runtime._vector_store = None
    runtime.get_collection_registry.return_value.list_all.return_value = []
    runtime.get_collection_stats.return_value = CollectionStats(
        collection_id="default", document_count=1, total_size_bytes=21,
    )
    runtime.ingest.return_value = IngestResult(document_id="doc-1", status="ingested")
    runtime.get_document.return_value = Document(id="doc-1", content="hello kb contract test")
    runtime.search.return_value = [SearchResult(
        document_id="doc-1", content="hello kb contract test", score=1.0,
    )]
    return create_mcp_server(runtime)


def _get_tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))


def test_contract_tools_registered(mcp):
    names = [tool.name for tool in asyncio.run(mcp.list_tools())]
    assert {"get_capabilities", "health_check", "describe_config_schema", "ingest", "search"} <= set(names)


def test_get_capabilities_shape(mcp):
    result = _get_tool(mcp, "get_capabilities").fn()
    assert isinstance(result, ToolResult)
    assert result.data.schema_version == 1
    assert "deterministic" in result.data.tooling


def test_health_check_shape(mcp):
    result = _get_tool(mcp, "health_check").fn()
    assert isinstance(result, ToolResult)
    assert result.data.status == "ok"
    assert "document_count" in result.data.details


def test_ingest_roundtrip(mcp):
    ingested = _get_tool(mcp, "ingest").fn(content="hello kb contract test")
    fetched = _get_tool(mcp, "get_document").fn(document_id=ingested.data.document_id)
    searched = _get_tool(mcp, "search").fn(query="contract test", limit=10)
    assert ingested.ok and fetched.ok and searched.ok
    assert fetched.data.found is True
    assert searched.data.total == 1
