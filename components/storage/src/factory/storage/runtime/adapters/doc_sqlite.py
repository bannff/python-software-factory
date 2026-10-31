"""SQLite document storage adapter.

File-based, no container, no external dependencies. Uses Python's
built-in sqlite3 module with WAL mode for concurrent access.
Same DocumentStore protocol as TinyDB/MongoDB/Neo4j adapters.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.storage.runtime.ports import Document, DocumentWriteResult, StorageHealth

_DEFAULT_PATH = "./.storage/docs.db"
_CREATE = """CREATE TABLE IF NOT EXISTS documents (
    id TEXT NOT NULL, collection TEXT NOT NULL,
    data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (collection, id))"""


class SQLiteDocumentStore:
    """SQLite implementation of DocumentStore port."""

    def __init__(self, db_path: str = _DEFAULT_PATH) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coll ON documents(collection)")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def insert(self, collection: str, data: dict[str, Any],
               doc_id: str | None = None) -> Document:
        doc_id = doc_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?)",
                (doc_id, collection, json.dumps(data),
                 now.isoformat(), now.isoformat()),
            )
        return Document(id=doc_id, collection=collection, data=data,
                        created_at=now, updated_at=now)

    def get(self, collection: str, doc_id: str) -> Document | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, data, created_at, updated_at FROM documents "
                "WHERE collection=? AND id=?", (collection, doc_id),
            ).fetchone()
        return self._row_to_doc(collection, row) if row else None

    def create_or_match(
        self, collection: str, doc_id: str, data: dict[str, Any], content_hash: str,
    ) -> DocumentWriteResult:
        """Atomically create immutable data or compare an existing document."""
        now = datetime.now(timezone.utc)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id, data, created_at, updated_at FROM documents "
                "WHERE collection=? AND id=?", (collection, doc_id),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO documents VALUES (?,?,?,?,?)",
                    (doc_id, collection, json.dumps(data), now.isoformat(), now.isoformat()),
                )
                return DocumentWriteResult("created", Document(doc_id, collection, data, now, now))
            document = self._row_to_doc(collection, row)
            existing_hash = str(document.data.get("content_hash", ""))
            status = "matched" if existing_hash and existing_hash == content_hash else "conflict"
            return DocumentWriteResult(status, document, existing_hash)

    def update(self, collection: str, doc_id: str,
               data: dict[str, Any]) -> Document | None:
        now = datetime.now(timezone.utc)
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE documents SET data=?, updated_at=? "
                "WHERE collection=? AND id=?",
                (json.dumps(data), now.isoformat(), collection, doc_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM documents WHERE collection=? AND id=?",
                (collection, doc_id),
            )
        return cur.rowcount > 0

    def find(self, collection: str, query: dict[str, Any],
             limit: int = 100, skip: int = 0) -> list[Document]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, data, created_at, updated_at FROM documents "
                "WHERE collection=? ORDER BY created_at DESC",
                (collection,),
            ).fetchall()
        docs = [self._row_to_doc(collection, r) for r in rows]
        if query:
            docs = [d for d in docs if self._matches(d.data, query)]
        return docs[skip:skip + limit]

    def count(self, collection: str, query: dict[str, Any] | None = None) -> int:
        if query:
            return len(self.find(collection, query, limit=100000))
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE collection=?",
                (collection,),
            ).fetchone()
        return row[0] if row else 0

    def health_check(self) -> StorageHealth:
        start = time.time()
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="sqlite",
                latency_ms=latency, details={"path": self._db_path},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="sqlite", message=str(e))

    @staticmethod
    def _matches(data: dict, query: dict) -> bool:
        return all(data.get(k) == v for k, v in query.items())

    @staticmethod
    def _row_to_doc(collection: str, row: tuple) -> Document:
        return Document(
            id=row[0], collection=collection,
            data=json.loads(row[1]),
            created_at=datetime.fromisoformat(row[2]),
            updated_at=datetime.fromisoformat(row[3]),
        )
