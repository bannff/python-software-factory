"""Complete strict typed-boundary regression for the Memory MCP surface."""
from __future__ import annotations

import asyncio
from inspect import Parameter, signature
from typing import Any, get_type_hints

import pytest
from pydantic import BaseModel

from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult, get_service, set_service


_EXPECTED: dict[str, tuple[str | None, tuple[tuple[str, Any], ...]]] = {
    "get_capabilities": (None, ()), "health_check": (None, ()),
    "describe_config_schema": (None, ()),
    "memory_get": (None, (("memory_id", Parameter.empty),)),
    "memory_recall_inspect": (None, (("memory_id", Parameter.empty),)),
    "memory_history": (None, (("memory_id", Parameter.empty),)),
    "memory_bulk_preview": (None, (("user_id", None), ("query", None), ("memory_type", None), ("metadata", None), ("limit", 1000))),
    "memory_list": (None, (("user_id", None), ("limit", 100), ("metadata", None))),
    "memory_stats": (None, (("user_id", None),)),
    "memory_get_embedding_status": (None, ()),
    "memory_store": (None, (("content", Parameter.empty), ("user_id", None), ("memory_type", "short_term"), ("category", "custom"), ("metadata", None), ("ttl_seconds", None), ("idempotency_key", None))),
    "memory_retrieve": (None, (("query", Parameter.empty), ("user_id", None), ("memory_type", None), ("category", None), ("min_relevance", 0.3), ("limit", 5), ("tags", None), ("metadata", None))),
    "memory_delete": (None, (("memory_id", Parameter.empty),)),
    "memory_update": (None, (("memory_id", Parameter.empty), ("content", Parameter.empty))),
    "memory_bulk_delete": (None, (("user_id", None), ("query", None), ("memory_type", None), ("metadata", None), ("limit", 1000))),
    "memory_delete_user": (None, (("user_id", None),)),
    "memory_consolidate": (None, (("user_id", None),)),
    "memory_evolve": (None, (("user_id", None), ("memory_ids", None))),
    "memory_hybrid_search": ("operational", (("user_id", Parameter.empty), ("query", None), ("anchor_memory_id", None), ("limit", 10), ("semantic_weight", 0.5), ("structural_weight", 0.3), ("traversal_weight", 0.2))),
    "memory_embed_backfill": ("operational", (("user_id", Parameter.empty), ("limit", 100))),
    "memory_search_by_time": ("operational", (("user_id", None), ("time_from", None), ("time_to", None), ("query", None), ("limit", 20))),
    "memory_import_record": ("operational", (("tenant_id", Parameter.empty), ("owner_id", Parameter.empty), ("source_adapter", Parameter.empty), ("source_fingerprint", Parameter.empty), ("plan_digest", Parameter.empty), ("kind", Parameter.empty), ("source_record_id", Parameter.empty), ("target_digest", Parameter.empty), ("subtype", Parameter.empty), ("content", Parameter.empty), ("key", Parameter.empty), ("tags", ()))),
    "memory_get_views": ("deterministic", ()),
}


def _tools() -> dict[str, object]:
    server = create_mcp_server(MemoryRuntime())
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_catalog_categories_models_annotations_and_signatures() -> None:
    tools = _tools()
    assert set(tools) == set(_EXPECTED)
    assert len(_EXPECTED) == 23
    for name, (category, expected_parameters) in _EXPECTED.items():
        fn = tools[name].fn
        assert getattr(fn, "_mcp_category", None) == category
        input_model = getattr(fn, "_mcp_input_model")
        output_model = getattr(fn, "_mcp_output_model")
        assert issubclass(input_model, BaseModel) and issubclass(output_model, BaseModel)
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        assert get_type_hints(fn)["return"] == ToolResult[output_model]
        actual = tuple((item.name, item.default) for item in signature(fn).parameters.values())
        assert actual == expected_parameters, name


def test_normal_negatives_and_json_safe_successes() -> None:
    tools = _tools()
    with pytest.raises(Exception):
        tools["memory_retrieve"].fn(query="x", unexpected=True)
    missing = tools["memory_get"].fn(memory_id="missing")
    assert missing.ok and missing.data.found is False and missing.data.memory is None
    for name, kwargs in {
        "memory_store": {"content": "fact"},
        "memory_retrieve": {"query": "fact"},
        "memory_delete_user": {}, "memory_consolidate": {}, "memory_evolve": {},
    }.items():
        result = tools[name].fn(**kwargs)
        assert result.ok and result.data.error == "user_id required: pass explicitly or authenticate via Bearer token"
    invalid = tools["memory_store"].fn(content="fact", user_id="u", category="invalid")
    assert invalid.ok and invalid.data.stored is False and invalid.data.memory is None
    assert tools["memory_delete"].fn(memory_id="missing").data.deleted is False
    for name, kwargs in {
        "memory_hybrid_search": {"user_id": "u"},
        "memory_embed_backfill": {"user_id": "u"},
        "memory_search_by_time": {"user_id": "u"},
    }.items():
        result = tools[name].fn(**kwargs)
        assert result.ok and result.data.available is False and result.data.error
    stored = tools["memory_store"].fn(content="fact", user_id="u")
    assert stored.ok and stored.data.stored is True
    retrieved = tools["memory_retrieve"].fn(query="fact", user_id="u")
    assert retrieved.ok and retrieved.data.count == 1
    assert retrieved.model_dump(mode="json")["data"]["memories"][0]["content"] == "fact"
    assert tools["memory_list"].fn(user_id="u").data.count == 1
    assert tools["memory_stats"].fn().ok
    assert tools["memory_get_views"].fn().data.views[0]["id"] == "memory-browser"


def test_memory_list_without_user_id_fails_closed_with_no_ambient_identity() -> None:
    tools = _tools()
    result = tools["memory_list"].fn()
    assert result.ok and result.data.count == 0
    assert result.data.error == (
        "user_id required: pass explicitly or authenticate via Bearer token"
    )


def test_memory_rejects_artifact_bound_inline_content() -> None:
    tools = _tools()
    result = tools["memory_store"].fn(
        content="private body canary@example.test", user_id="u-protected",
        metadata={"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv"},
    )
    assert result.ok and result.data.stored is False
    assert result.data.error == "protected content requires an approved projection"
    assert tools["memory_list"].fn(user_id="u-protected").data.count == 0


def test_memory_store_idempotency_matches_equal_retry_and_rejects_conflict() -> None:
    documents = {}

    def invoker(name, **kwargs):
        if name == "storage_doc_get":
            data = documents.get(kwargs["doc_id"])
            return {"data": data} if data else {}
        assert name == "storage_doc_create_or_match"
        existing = documents.get(kwargs["doc_id"])
        if existing is None:
            documents[kwargs["doc_id"]] = kwargs["data"]
            return {"status": "created"}
        return {"status": "matched" if existing["content_hash"] ==
                kwargs["content_hash"] else "conflict"}

    previous = get_service("tool_invoker")
    set_service("tool_invoker", invoker)
    try:
        tools = _tools()
        first = tools["memory_store"].fn(
            content="stable reward", user_id="u", memory_type="long_term",
            category="fact", idempotency_key="reward-cycle-1",
        )
        retry = tools["memory_store"].fn(
            content="stable reward", user_id="u", memory_type="long_term",
            category="fact", idempotency_key="reward-cycle-1",
        )
        conflict = tools["memory_store"].fn(
            content="changed reward", user_id="u", memory_type="long_term",
            category="fact", idempotency_key="reward-cycle-1",
        )
        assert first.data.memory.id == retry.data.memory.id
        assert conflict.data.stored is False
        assert conflict.data.error == "memory idempotency conflict"
        assert tools["memory_list"].fn(user_id="u").data.count == 1
    finally:
        set_service("tool_invoker", previous)
