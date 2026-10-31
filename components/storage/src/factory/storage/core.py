"""Storage core - high-level convenience functions."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import get_runtime


def store_blob(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store a blob and return its key."""
    runtime = get_runtime()
    store = runtime.get_blob_store()
    meta = store.put(key, data, content_type)
    return meta.key


def load_blob(key: str) -> bytes:
    """Load a blob by key."""
    runtime = get_runtime()
    store = runtime.get_blob_store()
    content, _ = store.get(key)
    return content


def save_document(collection: str, data: dict[str, Any], doc_id: str | None = None) -> str:
    """Save a document and return its ID."""
    runtime = get_runtime()
    store = runtime.get_document_store()
    doc = store.insert(collection, data, doc_id)
    return doc.id


def find_documents(collection: str, query: dict[str, Any], limit: int = 100) -> list[dict]:
    """Find documents matching a query."""
    runtime = get_runtime()
    store = runtime.get_document_store()
    docs = store.find(collection, query, limit)
    return [{"id": d.id, **d.data} for d in docs]


def execute_sql(query: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Execute a SQL query and return rows."""
    runtime = get_runtime()
    store = runtime.get_sql_store()
    result = store.execute(query, params)
    return result.rows


def add_graph_node(labels: list[str], properties: dict[str, Any]) -> str:
    """Add a graph node and return its ID."""
    runtime = get_runtime()
    store = runtime.get_graph_store()
    node = store.add_node(labels, properties)
    return node.id


def add_graph_edge(source: str, target: str, edge_type: str) -> str:
    """Add a graph edge and return its ID."""
    runtime = get_runtime()
    store = runtime.get_graph_store()
    edge = store.add_edge(source, target, edge_type)
    return edge.id
