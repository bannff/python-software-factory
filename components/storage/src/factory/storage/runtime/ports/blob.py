"""Blob storage port - S3-style object storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, BinaryIO

from .common import StorageHealth


@dataclass
class BlobMetadata:
    """Metadata for a stored blob."""
    key: str
    size: int
    content_type: str = "application/octet-stream"
    etag: str = ""
    last_modified: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str] = field(default_factory=dict)


class BlobStore(Protocol):
    """Port: Blob/object storage (S3, local filesystem, etc.)"""

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> BlobMetadata:
        """Store a blob."""
        ...

    def get(self, key: str) -> tuple[bytes, BlobMetadata]:
        """Retrieve a blob and its metadata."""
        ...

    def delete(self, key: str) -> bool:
        """Delete a blob."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a blob exists."""
        ...

    def list_keys(self, prefix: str = "", limit: int = 1000) -> list[BlobMetadata]:
        """List blobs with optional prefix filter."""
        ...

    def health_check(self) -> StorageHealth:
        """Check blob store health."""
        ...
