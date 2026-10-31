"""Ports (interfaces) for knowledge base module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import Document, SearchResult




class VectorStore(ABC):
    """Abstract base class for vector search backends."""

    @abstractmethod
    def add(self, document: Document, **kwargs: Any) -> Any:
        """Add a document to the vector store.

        Returns extraction result when entity extraction runs, else ``None``.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for documents similar to the query."""
        pass

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Delete a document from the vector store."""
        pass

    @abstractmethod
    def get(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        pass

    @abstractmethod
    def list_documents(self, limit: int = 100) -> list[Document]:
        """List documents in the vector store."""
        pass


class Retriever(ABC):
    """Abstract base class for document retrievers."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Retrieve documents relevant to the query."""
        pass
