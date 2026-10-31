"""Versioned, integrity-checked NetworkX snapshot encoding."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .networkx_edges import ensure_multidigraph

_LEGACY_SNAPSHOT_VERSION = 1
_NODE_LINK_SNAPSHOT_VERSION = 2
_SNAPSHOT_VERSION = 3
_SNAPSHOT_NODE_ID = "__factory_node_id__"
_GRAPH_FORMAT = "factory-networkx-records-v1"


class SnapshotIntegrityError(ValueError):
    """Raised when a persisted graph snapshot cannot be trusted."""


@dataclass(frozen=True)
class DecodedSnapshot:
    """Version-tagged snapshot payload for unambiguous legacy restoration."""

    graph: dict[str, Any]
    schema_version: int | None


def encode_snapshot(graph: Any) -> bytes:
    """Encode a graph in a versioned integrity envelope."""
    snapshot = serialize_graph(graph)
    envelope = {
        "schema_version": _SNAPSHOT_VERSION,
        "checksum": _checksum(_SNAPSHOT_VERSION, snapshot),
        "graph": snapshot,
    }
    return _canonical_json(envelope)


def serialize_graph(graph: Any) -> dict[str, Any]:
    """Serialize node identity separately from arbitrary user attributes."""
    multigraph = graph.is_multigraph()
    nodes = [
        {"identity": node_id, "attributes": dict(attributes)}
        for node_id, attributes in graph.nodes(data=True)
    ]
    if multigraph:
        edges = [
            {"source": source, "target": target, "key": key, "attributes": dict(attributes)}
            for source, target, key, attributes in graph.edges(data=True, keys=True)
        ]
    else:
        edges = [
            {"source": source, "target": target, "attributes": dict(attributes)}
            for source, target, attributes in graph.edges(data=True)
        ]
    return {
        "format": _GRAPH_FORMAT,
        "directed": graph.is_directed(),
        "multigraph": multigraph,
        "graph": dict(graph.graph),
        "nodes": nodes,
        "edges": edges,
    }


def decode_snapshot(data: bytes) -> DecodedSnapshot:
    """Decode v3, legacy enveloped, or bare NetworkX node-link snapshots."""
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotIntegrityError("snapshot is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise SnapshotIntegrityError("snapshot must be a JSON object")
    if "schema_version" not in parsed:
        return DecodedSnapshot(graph=parsed, schema_version=None)
    version = parsed.get("schema_version")
    if type(version) is not int or version not in (
        _LEGACY_SNAPSHOT_VERSION, _NODE_LINK_SNAPSHOT_VERSION, _SNAPSHOT_VERSION,
    ):
        raise SnapshotIntegrityError("unsupported graph snapshot schema")
    graph = parsed.get("graph")
    checksum = parsed.get("checksum")
    if not isinstance(graph, dict) or not isinstance(checksum, str):
        raise SnapshotIntegrityError("snapshot envelope is incomplete")
    if _checksum(version, graph) != checksum:
        raise SnapshotIntegrityError("snapshot checksum mismatch")
    return DecodedSnapshot(graph=graph, schema_version=version)


def restore_graph(snapshot: DecodedSnapshot) -> Any:
    """Restore v3 records or migrate versioned legacy node-link snapshots."""
    if snapshot.schema_version == _SNAPSHOT_VERSION:
        if snapshot.graph.get("format") != _GRAPH_FORMAT:
            raise SnapshotIntegrityError("record snapshot format is unsupported")
        return _restore_records(snapshot.graph)
    node_id_field = (
        _SNAPSHOT_NODE_ID
        if snapshot.schema_version == _NODE_LINK_SNAPSHOT_VERSION else "id"
    )
    return _restore_node_link(snapshot.graph, node_id_field)


def _restore_records(data: dict[str, Any]) -> Any:
    import networkx as nx

    directed = data.get("directed") is True
    multigraph = data.get("multigraph") is True
    graph_type = (
        nx.MultiDiGraph if directed and multigraph else nx.DiGraph if directed
        else nx.MultiGraph if multigraph else nx.Graph
    )
    graph = graph_type()
    graph_attrs = data.get("graph", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(graph_attrs, dict) or not isinstance(nodes, list) or not isinstance(edges, list):
        raise SnapshotIntegrityError("record snapshot is malformed")
    graph.graph.update(graph_attrs)
    for node in nodes:
        if not isinstance(node, dict) or "identity" not in node or not isinstance(node.get("attributes"), dict):
            raise SnapshotIntegrityError("record snapshot node is malformed")
        graph.add_node(node["identity"], **node["attributes"])
    for edge in edges:
        if not isinstance(edge, dict) or not isinstance(edge.get("attributes"), dict):
            raise SnapshotIntegrityError("record snapshot edge is malformed")
        if "source" not in edge or "target" not in edge:
            raise SnapshotIntegrityError("record snapshot edge is malformed")
        if multigraph:
            if "key" not in edge:
                raise SnapshotIntegrityError("record snapshot edge key is missing")
            graph.add_edge(edge["source"], edge["target"], key=edge["key"], **edge["attributes"])
        else:
            graph.add_edge(edge["source"], edge["target"], **edge["attributes"])
    return ensure_multidigraph(graph)


def _restore_node_link(data: dict[str, Any], node_id_field: str) -> Any:
    from networkx.readwrite import json_graph

    return ensure_multidigraph(
        json_graph.node_link_graph(data, directed=True, name=node_id_field),
    )


def _checksum(version: int, graph: dict[str, Any]) -> str:
    payload: Any = graph if version < _SNAPSHOT_VERSION else {
        "schema_version": version, "graph": graph,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
