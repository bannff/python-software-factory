"""Fail-closed Graph projection compatibility with MCPAggregator.tool_invoker."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.dataset.interface import dataset_project_can_graph
from factory.dataset.runtime.adapters.mcp_graph_projection import McpGraphProjectionAdapter
from factory.mcp_utils.interface import get_service, set_service


def _success(name: str, **kwargs):
    if name == "graph_graph_add_entity":
        data = {
            "id": kwargs["entity_id"], "type": kwargs["entity_type"],
            "properties": kwargs["properties"], "labels": [],
        }
    else:
        data = {
            "id": kwargs["relationship_id"], "type": kwargs["relationship_type"],
            "source_id": kwargs["source_id"], "target_id": kwargs["target_id"],
            "properties": kwargs["properties"],
        }
    return {
        "schema_version": "v1", "ok": True, "data": data,
        "error": None, "idempotency_key": None,
    }


def test_adapter_accepts_only_exact_typed_graph_success_shapes() -> None:
    adapter = McpGraphProjectionAdapter(_success, backend="networkx")
    entity = adapter.add_entity("e1", "Frame", {"value": 1})
    relationship = adapter.add_relationship("r1", "LINKS", "e1", "e2", {})
    assert entity == {"id": "e1", "type": "Frame",
                      "properties": {"value": 1}, "labels": []}
    assert relationship == {"id": "r1", "type": "LINKS",
                            "source_id": "e1", "target_id": "e2", "properties": {}}


@pytest.mark.parametrize("result", [
    {
        "schema_version": "v1", "ok": False, "data": None,
        "error": "tool_execution_failed", "idempotency_key": None,
    },
    {
        "schema_version": "v1", "ok": True,
        "data": {"id": "e1", "type": "Frame", "properties": {}},
        "error": None, "idempotency_key": None,
    },
    {"id": "e1", "type": "Frame", "properties": {}, "labels": []},
])
def test_adapter_rejects_failed_or_malformed_typed_results(result: dict) -> None:
    adapter = McpGraphProjectionAdapter(lambda *_args, **_kwargs: result)
    with pytest.raises(RuntimeError):
        adapter.add_entity("e1", "Frame", {})


def test_adapter_raises_transport_failures() -> None:
    def failed(*_args, **_kwargs):
        raise ConnectionError("transport down")

    with pytest.raises(RuntimeError, match="transport failure"):
        McpGraphProjectionAdapter(failed).add_entity("e1", "Frame", {})


def test_project_can_graph_cannot_complete_after_graph_error(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "frames.jsonl"
    dataset.write_text(json.dumps({
        "vehicle_id": "v1", "trip_id": "t1", "timestamp_ns": 1,
        "bus_name": "CAN1", "arbitration_id": "0x1", "dlc": 8,
    }) + "\n")
    calls = []

    def partial(name: str, **kwargs):
        calls.append(name)
        return _success(name, **kwargs) if len(calls) == 1 else {"error": "graph failed"}

    previous = get_service("tool_invoker")
    set_service("tool_invoker", partial)
    try:
        with pytest.raises(RuntimeError):
            dataset_project_can_graph(dataset.resolve().as_uri(), "networkx")
        assert len(calls) == 2
    finally:
        set_service("tool_invoker", previous)
