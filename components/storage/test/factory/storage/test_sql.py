"""Tests for SQL storage adapters."""

import pytest
from pathlib import Path

from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


class TestSQLiteSQLStore:
    """Tests for SQLiteSQLStore adapter."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> SQLiteSQLStore:
        """Create a temporary SQL store."""
        store = SQLiteSQLStore(db_path=str(tmp_path / "test.db"))
        # Create a test table
        store.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER
            )
        """)
        return store

    def test_execute_insert(self, store: SQLiteSQLStore) -> None:
        """Test executing an insert."""
        result = store.execute(
            "INSERT INTO users (name, age) VALUES (:name, :age)",
            {"name": "Alice", "age": 30},
        )
        assert result.row_count == 1

    def test_fetch_one(self, store: SQLiteSQLStore) -> None:
        """Test fetching a single row."""
        store.execute(
            "INSERT INTO users (name, age) VALUES (:name, :age)",
            {"name": "Bob", "age": 25},
        )

        row = store.fetch_one("SELECT * FROM users WHERE name = :name", {"name": "Bob"})
        assert row is not None
        assert row["name"] == "Bob"
        assert row["age"] == 25

    def test_fetch_one_not_found(self, store: SQLiteSQLStore) -> None:
        """Test fetching when no row matches."""
        row = store.fetch_one("SELECT * FROM users WHERE name = :name", {"name": "Nobody"})
        assert row is None

    def test_fetch_all(self, store: SQLiteSQLStore) -> None:
        """Test fetching all rows."""
        store.execute("INSERT INTO users (name, age) VALUES ('A', 1)")
        store.execute("INSERT INTO users (name, age) VALUES ('B', 2)")
        store.execute("INSERT INTO users (name, age) VALUES ('C', 3)")

        rows = store.fetch_all("SELECT * FROM users ORDER BY name")
        assert len(rows) == 3
        assert rows[0]["name"] == "A"
        assert rows[2]["name"] == "C"

    def test_execute_with_columns(self, store: SQLiteSQLStore) -> None:
        """Test that execute returns column names."""
        store.execute("INSERT INTO users (name, age) VALUES ('Test', 20)")
        result = store.execute("SELECT name, age FROM users")

        assert "name" in result.columns
        assert "age" in result.columns
        assert len(result.rows) == 1

    def test_table_exists(self, store: SQLiteSQLStore) -> None:
        """Test checking table existence."""
        assert store.table_exists("users")
        assert not store.table_exists("nonexistent")

    def test_health_check(self, store: SQLiteSQLStore) -> None:
        """Test health check."""
        health = store.health_check()
        assert health.healthy
        assert health.backend == "sqlite"
        assert health.latency_ms >= 0

    def test_execute_many(self, store: SQLiteSQLStore) -> None:
        """Test executing with multiple parameter sets."""
        params = [
            {"name": "X", "age": 10},
            {"name": "Y", "age": 20},
            {"name": "Z", "age": 30},
        ]
        count = store.execute_many(
            "INSERT INTO users (name, age) VALUES (:name, :age)",
            params,
        )
        assert count == 3

        rows = store.fetch_all("SELECT * FROM users")
        assert len(rows) == 3
