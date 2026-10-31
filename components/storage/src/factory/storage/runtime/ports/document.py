"""Document storage port - MongoDB-style document database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .common import StorageHealth


@dataclass
class Document:
    """A document in a collection."""
    id: str
    collection: str
    data: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DocumentWriteResult:
    """Outcome of an immutable create-or-match attempt."""
    status: str
    document: Document
    existing_content_hash: str = ""


class DocumentStore(Protocol):
    """Port: Document database (MongoDB, TinyDB, etc.)"""

    def insert(self, collection: str, data: dict[str, Any], doc_id: str | None = None) -> Document:
        """Insert a document."""
        ...

    def get(self, collection: str, doc_id: str) -> Document | None:
        """Get a document by ID."""
        ...

    def create_or_match(
        self, collection: str, doc_id: str, data: dict[str, Any], content_hash: str,
    ) -> DocumentWriteResult:
        """Create immutable data or compare it with an existing document."""
        ...

    def update(self, collection: str, doc_id: str, data: dict[str, Any]) -> Document | None:
        """Update a document."""
        ...

    def delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document."""
        ...

    def find(
        self,
        collection: str,
        query: dict[str, Any],
        limit: int = 100,
        skip: int = 0,
    ) -> list[Document]:
        """Find documents matching a query."""
        ...

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        """Count documents in a collection."""
        ...

    def health_check(self) -> StorageHealth:
        """Check document store health."""
        ...
