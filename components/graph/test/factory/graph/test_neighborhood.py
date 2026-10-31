"""Authority, bounds, and durability tests for graph_neighborhood."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from factory.graph.mcp.neighborhood_models import NeighborhoodInput
from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.adapters.persistent_networkx import PersistentNetworkXGraph
from factory.graph.runtime.neighborhood import (
    NeighborhoodRequest, decode_node_id, encode_node_id, matches_authority,
)
from factory.graph.runtime.ports import Entity, Relationship
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server
from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.storage.runtime.adapters.blob_local import LocalBlobStore

TENANT, OWNER = "tenant-a", "owner-a"


def _id(index: int, owner: str = OWNER) -> str:
    return encode_node_id("lesson", TENANT, owner, f"node-{index}")


def _graph(count: int, edges: set[tuple[int, int]]) -> NetworkXGraph:
    graph = NetworkXGraph()
    for index in range(count):
        graph.add_entity(Entity(_id(index), "Lesson"))
    for index, (source, target) in enumerate(sorted(edges)):
        graph.add_relationship(Relationship(
            f"edge-{index}", "LINKS", _id(source), _id(target),
        ))
    return graph


@given(
    count=st.integers(min_value=1, max_value=8),
    raw_edges=st.sets(st.tuples(
        st.integers(min_value=0, max_value=7),
        st.integers(min_value=0, max_value=7),
    ), max_size=20),
    depth=st.integers(min_value=1, max_value=3),
    node_limit=st.integers(min_value=1, max_value=8),
    edge_limit=st.integers(min_value=1, max_value=20),
)
def test_neighborhood_is_deterministic_bounded_and_same_authority(
    count: int, raw_edges: set[tuple[int, int]], depth: int,
    node_limit: int, edge_limit: int,
) -> None:
    edges = {(a, b) for a, b in raw_edges if a < count and b < count}
    graph = _graph(count, edges)
    request = NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, max_depth=depth,
        node_limit=node_limit, edge_limit=edge_limit,
    )
    first = graph.get_neighborhood(request)
    second = graph.get_neighborhood(request)
    assert first == second
    assert len(first.entities) <= node_limit
    assert len(first.relationships) <= edge_limit
    ids = {entity.id for entity in first.entities}
    assert all(matches_authority(value, TENANT, OWNER) for value in ids)
    assert all({edge.source_id, edge.target_id} <= ids for edge in first.relationships)
    assert [entity.id for entity in first.entities] == sorted(ids)
    assert [edge.id for edge in first.relationships] == sorted(
        edge.id for edge in first.relationships
    )


def test_foreign_edge_is_never_returned_or_traversed() -> None:
    graph = _graph(2, {(0, 1)})
    foreign = _id(9, "owner-b")
    graph.add_entity(Entity(foreign, "Lesson"))
    graph.add_relationship(Relationship("foreign", "LINKS", _id(1), foreign))
    result = graph.get_neighborhood(NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, max_depth=3,
    ))
    assert foreign not in {entity.id for entity in result.entities}
    assert "foreign" not in {edge.id for edge in result.relationships}


def test_direction_filter_and_truncation_are_truthful() -> None:
    graph = _graph(3, {(0, 1), (2, 0)})
    graph.add_relationship(Relationship("other", "OTHER", _id(0), _id(2)))
    result = graph.get_neighborhood(NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, ("LINKS",), "out", 1, 2, 1,
    ))
    assert [entity.id for entity in result.entities] == [_id(0), _id(1)]
    assert [edge.type for edge in result.relationships] == ["LINKS"]
    assert result.edges_truncated is False
    capped = graph.get_neighborhood(NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, max_depth=1, node_limit=1,
    ))
    assert capped.nodes_truncated is True


def test_node_id_round_trip_encodes_delimiters_and_rejects_unsafe_values() -> None:
    node_id = encode_node_id("memory", TENANT, "owner:a", "item:1")
    assert decode_node_id(node_id) == ("memory", TENANT, "owner:a", "item:1")
    with pytest.raises(ValueError):
        encode_node_id("memory", TENANT, "owner~a", "item")


@pytest.mark.parametrize("payload", [
    {"seed_ids": []},
    {"seed_ids": ["x"], "max_depth": "2"},
    {"seed_ids": ["x"], "max_depth": 4},
    {"seed_ids": ["x", "y"], "node_limit": 1},
    {"seed_ids": ["x"], "extra": True},
])
def test_neighborhood_input_is_strict(payload: dict) -> None:
    with pytest.raises(ValidationError):
        NeighborhoodInput.model_validate(payload)


def test_mcp_returns_edges_and_ambient_authority_wins() -> None:
    runtime = GraphRuntime({"default_backend": "networkx"})
    graph = runtime.get_graph("networkx")
    graph.add_entity(Entity(_id(0), "Lesson"))
    graph.add_entity(Entity(_id(1), "WorkflowRun"))
    graph.add_relationship(Relationship("learned", "LEARNED_IN", _id(0), _id(1)))
    tool = asyncio.run(create_mcp_server(runtime).get_tool("graph_neighborhood"))
    token = set_envelope({"tenant_id": TENANT, "principal_id": OWNER})
    try:
        result = tool.fn(
            seed_ids=[_id(0)], max_depth=1,
            envelope={"tenant_id": "foreign", "principal_id": "foreign"},
        )
    finally:
        reset_envelope(token)
    assert result.ok and result.data is not None
    assert result.data.relationship_count == 1
    assert result.data.relationships[0].id == "learned"


def test_persistent_neighborhood_survives_snapshot_reconstruction(tmp_path: Path) -> None:
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    request = NeighborhoodRequest((_id(0),), TENANT, OWNER, max_depth=2)
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=store,
    ):
        first = PersistentNetworkXGraph()
        first.add_entity(Entity(_id(0), "Lesson"))
        first.add_entity(Entity(_id(1), "WorkflowRun"))
        first.add_relationship(Relationship("learned", "LEARNED_IN", _id(0), _id(1)))
        expected = first.get_neighborhood(request)
        restored = PersistentNetworkXGraph().get_neighborhood(request)
    assert restored == expected


def test_mcp_resolves_source_refs_inside_graph_authority() -> None:
    runtime = GraphRuntime({"default_backend": "networkx"})
    node_id = encode_node_id("memory", TENANT, OWNER, "memory-1")
    runtime.get_graph("networkx").add_entity(Entity(node_id, "Memory"))
    tool = asyncio.run(create_mcp_server(runtime).get_tool("graph_neighborhood"))
    token = set_envelope({"tenant_id": TENANT, "principal_id": OWNER})
    try:
        result = tool.fn(seed_refs=[{"kind": "memory", "local_id": "memory-1"}])
    finally:
        reset_envelope(token)
    assert result.ok and result.data.seed_ids == [node_id]
    assert [item.id for item in result.data.entities] == [node_id]
