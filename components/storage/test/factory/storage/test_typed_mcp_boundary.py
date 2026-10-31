"""Whole-server strict ingress and exact-envelope regression for Storage."""
from __future__ import annotations

import asyncio
from typing import get_type_hints
from uuid import uuid4

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.storage.server import create_mcp_server
from factory.storage.runtime.runtime import StorageRuntime, reset_runtime

_EXPECTED = {"get_capabilities": "deterministic", "health_check": "deterministic", "describe_config_schema": "deterministic", "blob_put": "operational", "blob_get": "operational", "blob_delete": "operational", "blob_list": "operational", "doc_insert": "operational", "doc_get": "operational", "doc_find": "operational", "doc_delete": "operational", "doc_create_or_match": "operational", "sql_execute": "operational", "sql_fetch_one": "operational", "sql_fetch_all": "operational", "sql_table_exists": "operational", "graph_add_node": "operational", "graph_get_node": "operational", "graph_update_node": "operational", "graph_delete_node": "operational", "graph_add_edge": "operational", "graph_get_edges": "operational", "graph_delete_edge": "operational", "graph_query": "operational", "storage_get_views": "deterministic"}


def _tool(server, name):
    return asyncio.run(server.get_tool(name))


def test_all_25_tools_are_strict_typed_envelopes() -> None:
    reset_runtime()
    server = create_mcp_server(StorageRuntime())
    for name in _EXPECTED:
        assert _tool(server, name) is not None
    assert len(_EXPECTED) == 25
    for name, category in _EXPECTED.items():
        fn = _tool(server, name).fn
        assert getattr(fn, "_mcp_category") == category
        assert getattr(fn, "_mcp_input_model").model_config["extra"] == "forbid"
        assert getattr(fn, "_mcp_input_model").model_config["strict"] is True
        output_model = getattr(fn, "_mcp_output_model")
        assert output_model is not None
        assert output_model.model_config["extra"] == "forbid"
        assert output_model.model_config["strict"] is True
        annotation = get_type_hints(fn)["return"]
        assert annotation == ToolResult[output_model]


def test_strict_json_and_normal_negative_outcomes() -> None:
    reset_runtime()
    server = create_mcp_server(StorageRuntime())
    with pytest.raises(Exception):
        _tool(server, "doc_insert").fn(collection="x", data={}, unexpected=True)
    missing = _tool(server, "doc_get").fn(collection="x", doc_id="none")
    assert isinstance(missing, ToolResult) and missing.ok and missing.data.found is False
    payload = {"content_hash": "hash", "nested": [1, {"ok": True}]}
    doc_id = f"typed-{uuid4()}"
    immutable = _tool(server, "doc_create_or_match").fn(collection="x", doc_id=doc_id, data=payload, content_hash="hash")
    assert immutable.ok and immutable.data.status == "created" and immutable.data.existing_content_hash == ""
    matched = _tool(server, "doc_create_or_match").fn(collection="x", doc_id=doc_id, data=payload, content_hash="hash")
    assert matched.ok and matched.data.status == "matched"
