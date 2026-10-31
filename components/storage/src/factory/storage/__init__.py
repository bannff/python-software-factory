"""Storage brick - unified storage abstraction with pluggable backends."""

from .runtime import (
    BlobStore,
    BlobMetadata,
    DocumentStore,
    Document,
    SQLStore,
    SQLResult,
    GraphStore,
    GraphNode,
    GraphEdge,
    GraphQueryResult,
    StorageHealth,
    StorageRuntime,
    get_runtime,
)

__all__ = [
    # Ports
    "BlobStore",
    "DocumentStore",
    "SQLStore",
    "GraphStore",
    # Models
    "BlobMetadata",
    "Document",
    "SQLResult",
    "GraphNode",
    "GraphEdge",
    "GraphQueryResult",
    "StorageHealth",
    # Runtime
    "StorageRuntime",
    "get_runtime",
]
