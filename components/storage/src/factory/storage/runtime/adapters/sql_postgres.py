"""PostgreSQL SQL storage adapter."""

from __future__ import annotations

import importlib.util
import time
from typing import Any

from factory.storage.runtime.ports import SQLResult, StorageHealth

PSYCOPG2_AVAILABLE = importlib.util.find_spec("psycopg2") is not None


def _require_psycopg2() -> None:
    if not PSYCOPG2_AVAILABLE:
        raise ImportError("psycopg2 required. Install with: pip install psycopg2-binary")


class PostgresSQLStore:
    """PostgreSQL implementation of SQLStore port."""

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/factory",
        **kwargs: Any,
    ) -> None:
        _require_psycopg2()
        import psycopg2
        from psycopg2.extras import RealDictCursor
        self._connection_string = connection_string
        self._conn = psycopg2.connect(connection_string, **kwargs)
        self._cursor_factory = RealDictCursor

    def execute(self, query: str, params: dict[str, Any] | None = None) -> SQLResult:
        """Execute a SQL query."""
        cursor = self._conn.cursor(cursor_factory=self._cursor_factory)
        cursor.execute(query, params)
        self._conn.commit()

        if cursor.description:
            columns = [col.name for col in cursor.description]
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
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %(name)s
            )
            """,
            {"name": table_name},
        )
        return result.get("exists", False) if result else False

    def health_check(self) -> StorageHealth:
        """Check PostgreSQL health."""
        start = time.time()
        try:
            self.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(healthy=True, backend="postgres", latency_ms=latency)
        except Exception as e:
            return StorageHealth(healthy=False, backend="postgres", message=str(e))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
