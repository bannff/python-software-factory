"""SQL storage port - relational database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .common import StorageHealth


@dataclass
class SQLResult:
    """Result from a SQL query."""
    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str] = field(default_factory=list)


class SQLStore(Protocol):
    """Port: SQL database (Postgres, SQLite, etc.)"""

    def execute(self, query: str, params: dict[str, Any] | None = None) -> SQLResult:
        """Execute a SQL query."""
        ...

    def execute_many(self, query: str, params_list: list[dict[str, Any]]) -> int:
        """Execute a query with multiple parameter sets. Returns affected rows."""
        ...

    def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row."""
        ...

    def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows."""
        ...

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        ...

    def health_check(self) -> StorageHealth:
        """Check SQL store health."""
        ...
