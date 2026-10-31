"""TinyDB document storage adapter."""

from __future__ import annotations

import importlib.util
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from factory.storage.runtime.adapters._document_atomic import LockingCreateOrMatchMixin
from factory.storage.runtime.ports import Document, StorageHealth

TINYDB_AVAILABLE = importlib.util.find_spec("tinydb") is not None
logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _require_tinydb() -> None:
    if not TINYDB_AVAILABLE:
        raise ImportError("tinydb required. Install with: pip install tinydb")


class TinyDBDocumentStore(LockingCreateOrMatchMixin):
    """TinyDB implementation of DocumentStore port."""

    def __init__(self, db_path: str = "./.storage/docs.json") -> None:
        _require_tinydb()
        self._db_path = db_path
        self._lock = threading.RLock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = self._open_db()

    def _open_db(self):
        """Open the TinyDB backing file."""
        from tinydb import TinyDB

        return TinyDB(self._db_path)

    def _recover_from_corruption(self) -> None:
        """Rotate a corrupted TinyDB file aside and reopen a clean store."""
        corrupt_path = Path(self._db_path)
        backup_path = corrupt_path.with_name(
            f"{corrupt_path.name}.corrupt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )
        try:
            self._db.close()
        except Exception:
            pass
        if corrupt_path.exists():
            corrupt_path.rename(backup_path)
        logger.warning(
            "Recovered corrupted TinyDB file",
            extra={"path": self._db_path, "backup": str(backup_path)},
        )
        self._db = self._open_db()

    def _run_with_recovery(self, operation: Callable[[], _T]) -> _T:
        """Retry a TinyDB operation once after recovering a corrupted DB file."""
        with self._lock:
            try:
                return operation()
            except json.JSONDecodeError:
                self._recover_from_corruption()
                return operation()

    def insert(
        self, collection: str, data: dict[str, Any], doc_id: str | None = None
    ) -> Document:
        """Insert a document into TinyDB."""
        doc_id = doc_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        record = {
            "_id": doc_id,
            "_created_at": now.isoformat(),
            "_updated_at": now.isoformat(),
            **data,
        }

        def _insert() -> None:
            table = self._db.table(collection)
            table.insert(record)

        self._run_with_recovery(_insert)

        return Document(
            id=doc_id, collection=collection, data=data,
            created_at=now, updated_at=now,
        )

    def get(self, collection: str, doc_id: str) -> Document | None:
        """Get a document by ID."""
        from tinydb import Query

        q = Query()

        def _get() -> list[dict[str, Any]]:
            table = self._db.table(collection)
            return table.search(q._id == doc_id)

        result = self._run_with_recovery(_get)
        if not result:
            return None

        record = result[0]
        return self._record_to_document(collection, record)

    def update(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> Document | None:
        """Update a document."""
        from tinydb import Query

        q = Query()

        def _existing() -> list[dict[str, Any]]:
            table = self._db.table(collection)
            return table.search(q._id == doc_id)

        existing = self._run_with_recovery(_existing)
        if not existing:
            return None

        now = datetime.now(timezone.utc)
        update_data = {
            **data,
            "_updated_at": now.isoformat(),
        }

        def _update() -> None:
            table = self._db.table(collection)
            table.update(update_data, q._id == doc_id)

        self._run_with_recovery(_update)

        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document."""
        from tinydb import Query

        q = Query()

        def _delete() -> list[int]:
            table = self._db.table(collection)
            return table.remove(q._id == doc_id)

        removed = self._run_with_recovery(_delete)
        return len(removed) > 0

    def find(
        self,
        collection: str,
        query: dict[str, Any],
        limit: int = 100,
        skip: int = 0,
    ) -> list[Document]:
        """Find documents matching a query."""
        from tinydb import Query

        def _find() -> list[dict[str, Any]]:
            table = self._db.table(collection)
            if not query:
                return table.all()
            q = Query()
            conditions = []
            for key, value in query.items():
                conditions.append(getattr(q, key) == value)
            if conditions:
                compound = conditions[0]
                for condition in conditions[1:]:
                    compound = compound & condition
                return table.search(compound)
            return table.all()

        results = self._run_with_recovery(_find)
        return [
            self._record_to_document(collection, record)
            for record in results[skip:skip + limit]
        ]

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        """Count documents in a collection."""
        if query:
            return len(self.find(collection, query, limit=100000))

        def _count() -> int:
            return len(self._db.table(collection))

        return self._run_with_recovery(_count)

    def health_check(self) -> StorageHealth:
        """Check TinyDB health."""
        start = time.time()
        try:
            self._run_with_recovery(lambda: self._db.tables())
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="tinydb", latency_ms=latency,
                details={"path": self._db_path},
            )
        except Exception as exc:
            return StorageHealth(healthy=False, backend="tinydb", message=str(exc))

    def _record_to_document(self, collection: str, record: dict[str, Any]) -> Document:
        """Convert a TinyDB record to a Document."""
        doc_id = record.pop("_id", str(uuid.uuid4()))
        created_at = record.pop("_created_at", None)
        updated_at = record.pop("_updated_at", None)

        return Document(
            id=doc_id,
            collection=collection,
            data=record,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else datetime.now(timezone.utc),
        )
