"""Codec-level regression coverage for persistent NetworkX snapshots."""

from __future__ import annotations

import json

import networkx as nx
import pytest

from factory.graph.runtime.adapters.persistent_networkx_snapshot import (
    _GRAPH_FORMAT,
    SnapshotIntegrityError,
    decode_snapshot,
    encode_snapshot,
    restore_graph,
)


def test_v3_round_trip_isolates_identity_from_attributes_and_edge_keys() -> None:
    """V3 records preserve arbitrary attributes and parallel relationship keys."""
    graph = nx.MultiDiGraph(graph_name="provenance")
    graph.add_node(
        "node-a",
        id="user-visible-id",
        __factory_node_id__="user-sentinel",
    )
    graph.add_node("node-b")
    graph.add_edge("node-a", "node-b", key="relationship-a", id="relationship-a")
    graph.add_edge("node-a", "node-b", key="relationship-b", id="relationship-b")

    encoded = encode_snapshot(graph)
    envelope = json.loads(encoded)
    decoded = decode_snapshot(encoded)
    restored = restore_graph(decoded)

    assert envelope["schema_version"] == 3
    assert envelope["graph"]["format"] == _GRAPH_FORMAT
    assert decoded.schema_version == 3
    assert restored.graph == {"graph_name": "provenance"}
    assert restored.nodes["node-a"] == {
        "id": "user-visible-id", "__factory_node_id__": "user-sentinel",
    }
    assert set(restored["node-a"]["node-b"]) == {"relationship-a", "relationship-b"}


@pytest.mark.parametrize("version", [True, 1.0, 2.0, 3.0])
def test_snapshot_rejects_non_integer_schema_versions(version: object) -> None:
    """Schema selection is exact and cannot coerce Python-equivalent values."""
    envelope = {"schema_version": version, "checksum": "unused", "graph": {}}

    with pytest.raises(SnapshotIntegrityError, match="unsupported"):
        decode_snapshot(json.dumps(envelope).encode())


def test_v3_checksum_binds_schema_and_record_payload() -> None:
    """A valid v3 checksum rejects version and payload substitutions."""
    graph = nx.MultiDiGraph()
    graph.add_node("node")
    envelope = json.loads(encode_snapshot(graph))

    version_tampered = {**envelope, "schema_version": 2}
    payload_tampered = {
        **envelope,
        "graph": {**envelope["graph"], "format": "untrusted-format"},
    }

    for tampered in (version_tampered, payload_tampered):
        with pytest.raises(SnapshotIntegrityError, match="checksum"):
            decode_snapshot(json.dumps(tampered).encode())
