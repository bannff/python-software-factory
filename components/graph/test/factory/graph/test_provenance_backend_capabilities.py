"""Backend capability contracts for Graph provenance."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from factory.graph.mcp._deterministic_meta import capabilities_for
from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.adapters.persistent_networkx import (
    PersistentNetworkXGraph,
    UnsupportedBlobStoreError,
)
from factory.graph.runtime.ports import Entity
from factory.graph.runtime.provenance_models import GraphRelationshipWrite
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


def test_neo4j_advertises_native_provenance() -> None:
    assert "neo4j" in GraphRuntime.provenance_backends()
    assert "neo4j" in capabilities_for(GraphRuntime())["provenance_backends"]
    graph = Neo4jGraph()
    for name in ("write_relationship", "tombstone_relationship", "rebuild"):
        assert callable(getattr(graph, name))


def test_neo4j_rejects_a_relation_type_that_is_not_an_identifier() -> None:
    bad = _write().model_copy(update={"relation_type": "a`b) DETACH DELETE n //"})
    with pytest.raises(ValueError, match="identifier"):
        Neo4jGraph().write_relationship(bad)
