"""SQLite SQL storage adapter."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from factory.storage.runtime.ports import SQLResult, StorageHealth


class SQLiteSQLStore:
    """SQLite implementation of SQLStore port."""

    def __init__(self, db_path: str = "./.storage/data.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def execute(self, query: str, params: dict[str, Any] | None = None) -> SQLResult:
        """Execute a SQL query."""
        cursor = self._conn.cursor()
        if params:
            # Convert dict params to named params format
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        self._conn.commit()

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = [dict(row) for row in cursor.fetchall()]
        else:
            columns = []
            rows = []

        return SQLResult(rows=rows, row_count=cursor.rowcount, columns=columns)

    def execute_many(self, query: str, params_list: list[dict[str, Any]]) -> int:
        """Execute a query with multiple parameter sets."""
        cursor = self._conn.cursor()
        cursor.executemany(query, params_list)
        self._conn.commit()
        return cursor.rowcount

    def fetch_one(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Fetch a single row."""
        result = self.execute(query, params)
        return result.rows[0] if result.rows else None

    def fetch_all(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all rows."""
        result = self.execute(query, params)
        return result.rows

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        result = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:name",
            {"name": table_name},
        )
        return result is not None

    def health_check(self) -> StorageHealth:
        """Check SQLite health."""
        start = time.time()
        try:
            self.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(
                healthy=True, backend="sqlite", latency_ms=latency,
                details={"path": self._db_path},
            )
        except Exception as e:
            return StorageHealth(healthy=False, backend="sqlite", message=str(e))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
