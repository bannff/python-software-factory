"""Multi-edge-safe primitives shared by NetworkX Graph adapters."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any


def iter_edges(graph: Any) -> Iterator[tuple[Any, Any, Any, dict[str, Any]]]:
    """Yield ``(source, target, key, attributes)`` for either graph shape."""
    if graph.is_multigraph():
        yield from graph.edges(data=True, keys=True)
        return
    for source, target, data in graph.edges(data=True):
        yield source, target, data.get("id"), data


def remove_edge_id(graph: Any, relationship_id: str) -> bool:
    """Remove every edge carrying one portable relationship identity."""
    removed = False
    for source, target, key, data in list(iter_edges(graph)):
        if data.get("id") != relationship_id and key != relationship_id:
            continue
        if graph.is_multigraph():
            graph.remove_edge(source, target, key=key)
        else:
            graph.remove_edge(source, target)
        removed = True
    return removed


def first_edge_data(graph: Any, source: Any, target: Any) -> dict[str, Any] | None:
    """Select one deterministic edge for a node-only shortest path."""
    data = graph.get_edge_data(source, target)
    if data is None:
        return None
    if not graph.is_multigraph():
        return data
    return min(data.items(), key=lambda item: str(item[0]))[1]


def ensure_multidigraph(graph: Any) -> Any:
    """Upgrade a legacy DiGraph while preserving its nodes and edge IDs."""
    if graph.is_multigraph():
        return graph
    import networkx as nx

    migrated = nx.MultiDiGraph()
    migrated.graph.update(graph.graph)
    migrated.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        attrs = dict(data)
        key = str(attrs.get("id") or _legacy_edge_key(source, target, attrs))
        migrated.add_edge(source, target, key=key, **attrs)
    return migrated


def _legacy_edge_key(source: Any, target: Any, data: dict[str, Any]) -> str:
    payload = json.dumps(
        [source, target, data], default=str, sort_keys=True, separators=(",", ":"),
    ).encode()
    return "legacy-" + hashlib.sha256(payload).hexdigest()


__all__ = ["ensure_multidigraph", "first_edge_data", "iter_edges", "remove_edge_id"]
