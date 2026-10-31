"""Convenience functions for knowledge base operations.

This module provides simple, high-level functions for common KB operations.
For advanced usage, use the KBRuntime directly via interface.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .runtime.runtime import KBRuntime
from .runtime.models import Document, SearchResult, IngestResult

# Module-level runtime instance (lazy initialized)
_runtime: KBRuntime | None = None


def get_runtime(config_dir: str | Path | None = None) -> KBRuntime:
    """Get or create the module-level runtime instance.
    
    Args:
        config_dir: Optional config directory. If not provided, uses default.
        
    Returns:
        The KBRuntime instance.
    """
    global _runtime
    if _runtime is None:
        _runtime = KBRuntime(config_dir or Path.cwd() / "config" / "kb")
    return _runtime


def reset_runtime() -> None:
    """Reset the module-level runtime (useful for testing)."""
    global _runtime
    _runtime = None


def ingest(
    content: str,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    document_id: str | None = None,
) -> IngestResult:
    """Ingest a document into the knowledge base.
    
    Args:
        content: The document content.
        metadata: Optional metadata dict.
        source: Optional source identifier.
        document_id: Optional document ID (auto-generated if not provided).
        
    Returns:
        IngestResult with document_id and status.
    """
    runtime = get_runtime()
    return runtime.ingest(content, metadata=metadata, source=source, document_id=document_id)


def search(
    query: str,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[SearchResult]:
    """Search the knowledge base.
    
    Args:
        query: Search query string.
        limit: Maximum results to return.
        filters: Optional metadata filters.
        
    Returns:
        List of SearchResult objects.
    """
    runtime = get_runtime()
    return runtime.search(query, limit=limit, filters=filters)


def get_document(document_id: str) -> Document | None:
    """Get a document by ID.
    
    Args:
        document_id: The document ID.
        
    Returns:
        Document if found, None otherwise.
    """
    runtime = get_runtime()
    return runtime.get_document(document_id)


def delete_document(document_id: str) -> bool:
    """Delete a document by ID.
    
    Args:
        document_id: The document ID.
        
    Returns:
        True if deleted, False if not found.
    """
    runtime = get_runtime()
    return runtime.delete_document(document_id)


def list_documents(limit: int = 100) -> list[Document]:
    """List documents in the knowledge base.
    
    Args:
        limit: Maximum documents to return.
        
    Returns:
        List of Document objects.
    """
    runtime = get_runtime()
    return runtime.list_documents(limit=limit)
