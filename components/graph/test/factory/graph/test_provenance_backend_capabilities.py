"""Backend capability contracts for Graph provenance."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from factory.graph.mcp._deterministic_meta import capabilities_for
from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.adapters.persistent_networkx import (
    PersistentNetworkXGraph,
    UnsupportedBlobStoreError,
)
from factory.graph.runtime.ports import Entity
from factory.graph.runtime.provenance_models import GraphRelationshipWrite, GraphTombstone
from factory.graph.runtime.provenance_ports import GraphProvenanceUnsupportedError
from factory.graph.runtime.runtime import GraphRuntime


def _write() -> GraphRelationshipWrite:
    return GraphRelationshipWrite(
        source_system="test", source_identity="item", source_digest="digest",
        relation_type="OBSERVED", source_endpoint="source", target_endpoint="target",
        source_ref="ref", visibility="private", browse_metadata={},
    )


class RemoteBlobStore:
    def exists(self, _key: str) -> bool:
        return False


def test_persistent_graph_fails_closed_for_remote_non_cas_store() -> None:
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=RemoteBlobStore(),
    ):
        graph = PersistentNetworkXGraph()
        with pytest.raises(UnsupportedBlobStoreError, match="CAS"):
            graph.add_entity(Entity(id="remote", type="Node"))


def test_neo4j_provenance_is_explicitly_unsupported() -> None:
    graph = Neo4jGraph()
    with pytest.raises(GraphProvenanceUnsupportedError, match="neo4j"):
        graph.write_relationship(_write())
    with pytest.raises(GraphProvenanceUnsupportedError, match="neo4j"):
        graph.tombstone_relationship(GraphTombstone(
            source_system="test", source_identity="item", source_digest="digest",
            deleted_at=datetime.now(timezone.utc),
        ))
    assert "neo4j" not in GraphRuntime.provenance_backends()
    assert "neo4j" not in capabilities_for(GraphRuntime())["provenance_backends"]


def test_neo4j_mcp_provenance_returns_typed_unsupported_error() -> None:
    from factory.graph.server import create_mcp_server

    server = create_mcp_server(GraphRuntime({"default_backend": "neo4j"}))
    tool = asyncio.run(server.get_tool("graph_write_relationship"))
    result = tool.fn(
        source_system="test", source_identity="item", source_digest="digest",
        relation_type="OBSERVED", source_endpoint="source", target_endpoint="target",
        source_ref="ref", visibility="private", browse_metadata={}, backend="neo4j",
    )
    assert result.ok is False
    assert result.error == "unsupported_backend"
