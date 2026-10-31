"""MongoDB document storage adapter."""

from __future__ import annotations

import importlib.util
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.storage.runtime.ports import Document, DocumentWriteResult, StorageHealth

PYMONGO_AVAILABLE = importlib.util.find_spec("pymongo") is not None


def _require_pymongo() -> None:
    if not PYMONGO_AVAILABLE:
        raise ImportError("pymongo required. Install with: pip install pymongo")


class MongoDBDocumentStore:
    """MongoDB implementation of DocumentStore port."""

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017",
        database: str = "factory",
    ) -> None:
        _require_pymongo()
        from pymongo import MongoClient
        self._client = MongoClient(connection_string)
        self._db = self._client[database]
        self._connection_string = connection_string
        self._database = database

    def insert(
        self, collection: str, data: dict[str, Any], doc_id: str | None = None
    ) -> Document:
        """Insert a document into MongoDB."""
        doc_id = doc_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        record = {
            "_id": doc_id,
            "_created_at": now,
            "_updated_at": now,
            **data,
        }
        self._db[collection].insert_one(record)

        return Document(
            id=doc_id, collection=collection, data=data,
            created_at=now, updated_at=now,
        )

    def create_or_match(
        self, collection: str, doc_id: str, data: dict[str, Any], content_hash: str,
    ) -> DocumentWriteResult:
        """Atomically create data or compare the immutable stored hash."""
        if data.get("content_hash") != content_hash:
            raise ValueError("data content_hash must match content_hash")
        now = datetime.now(timezone.utc)
        record = {
            "_id": doc_id, "_created_at": now, "_updated_at": now, **data,
        }
        result = self._db[collection].update_one(
            {"_id": doc_id}, {"$setOnInsert": record}, upsert=True,
        )
        if result.upserted_id is not None:
            return DocumentWriteResult("created", Document(doc_id, collection, data, now, now))
        existing = self._db[collection].find_one({"_id": doc_id})
        document = self._record_to_document(collection, existing)
        existing_hash = str(document.data.get("content_hash", ""))
        status = "matched" if existing_hash and existing_hash == content_hash else "conflict"
        return DocumentWriteResult(status, document, existing_hash)

    def get(self, collection: str, doc_id: str) -> Document | None:
        """Get a document by ID."""
        record = self._db[collection].find_one({"_id": doc_id})
        if not record:
            return None
        return self._record_to_document(collection, record)

    def update(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> Document | None:
        """Update a document."""
        now = datetime.now(timezone.utc)
        result = self._db[collection].update_one(
            {"_id": doc_id},
            {"$set": {**data, "_updated_at": now}},
        )
        if result.matched_count == 0:
            return None
        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document."""
        result = self._db[collection].delete_one({"_id": doc_id})
        return result.deleted_count > 0

    def find(
        self,
        collection: str,
        query: dict[str, Any],
        limit: int = 100,
        skip: int = 0,
    ) -> list[Document]:
        """Find documents matching a query."""
        cursor = self._db[collection].find(query).skip(skip).limit(limit)
        return [self._record_to_document(collection, r) for r in cursor]

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        """Count documents in a collection."""
        return self._db[collection].count_documents(query or {})

    def health_check(self) -> StorageHealth:
        """Check MongoDB health."""
        start = time.time()
        try:
            self._client.admin.command("ping")
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="mongodb", latency_ms=latency,
                details={"database": self._database},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="mongodb", message=str(e))

    def _record_to_document(self, collection: str, record: dict[str, Any]) -> Document:
        """Convert a MongoDB record to a Document."""
        doc_id = str(record.pop("_id", uuid.uuid4()))
        created_at = record.pop("_created_at", datetime.now(timezone.utc))
        updated_at = record.pop("_updated_at", datetime.now(timezone.utc))

        return Document(
            id=doc_id,
            collection=collection,
            data=record,
            created_at=created_at if isinstance(created_at, datetime) else datetime.now(timezone.utc),
            updated_at=updated_at if isinstance(updated_at, datetime) else datetime.now(timezone.utc),
        )
