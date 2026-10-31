"""Tests for document storage adapters."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from factory.storage.runtime.adapters.doc_tinydb import TinyDBDocumentStore


class TestTinyDBDocumentStore:
    """Tests for TinyDBDocumentStore adapter."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> TinyDBDocumentStore:
        """Create a temporary document store."""
        return TinyDBDocumentStore(db_path=str(tmp_path / "docs.json"))

    def test_insert_and_get(self, store: TinyDBDocumentStore) -> None:
        """Test inserting and retrieving a document."""
        doc = store.insert("users", {"name": "Alice", "age": 30})

        assert doc.id is not None
        assert doc.collection == "users"
        assert doc.data["name"] == "Alice"

        retrieved = store.get("users", doc.id)
        assert retrieved is not None
        assert retrieved.data["name"] == "Alice"

    def test_insert_with_id(self, store: TinyDBDocumentStore) -> None:
        """Test inserting with a specific ID."""
        doc = store.insert("users", {"name": "Bob"}, doc_id="bob-123")
        assert doc.id == "bob-123"

        retrieved = store.get("users", "bob-123")
        assert retrieved is not None

    def test_update(self, store: TinyDBDocumentStore) -> None:
        """Test updating a document."""
        doc = store.insert("users", {"name": "Charlie", "age": 25})

        updated = store.update("users", doc.id, {"age": 26})
        assert updated is not None
        assert updated.data["age"] == 26
        assert updated.data["name"] == "Charlie"

    def test_update_nonexistent(self, store: TinyDBDocumentStore) -> None:
        """Test updating a nonexistent document."""
        result = store.update("users", "nonexistent", {"name": "Nobody"})
        assert result is None

    def test_delete(self, store: TinyDBDocumentStore) -> None:
        """Test deleting a document."""
        doc = store.insert("users", {"name": "Dave"})
        assert store.get("users", doc.id) is not None

        deleted = store.delete("users", doc.id)
        assert deleted
        assert store.get("users", doc.id) is None

    def test_delete_nonexistent(self, store: TinyDBDocumentStore) -> None:
        """Test deleting a nonexistent document."""
        deleted = store.delete("users", "nonexistent")
        assert not deleted

    def test_find_all(self, store: TinyDBDocumentStore) -> None:
        """Test finding all documents."""
        store.insert("items", {"type": "a"})
        store.insert("items", {"type": "b"})
        store.insert("items", {"type": "a"})

        all_items = store.find("items", {})
        assert len(all_items) == 3

    def test_find_with_query(self, store: TinyDBDocumentStore) -> None:
        """Test finding documents with a query."""
        store.insert("items", {"type": "a", "value": 1})
        store.insert("items", {"type": "b", "value": 2})
        store.insert("items", {"type": "a", "value": 3})

        type_a = store.find("items", {"type": "a"})
        assert len(type_a) == 2

    def test_find_with_limit(self, store: TinyDBDocumentStore) -> None:
        """Test finding documents with limit."""
        for i in range(10):
            store.insert("items", {"index": i})

        limited = store.find("items", {}, limit=5)
        assert len(limited) == 5

    def test_count(self, store: TinyDBDocumentStore) -> None:
        """Test counting documents."""
        assert store.count("empty") == 0

        store.insert("items", {"x": 1})
        store.insert("items", {"x": 2})
        assert store.count("items") == 2

    def test_health_check(self, store: TinyDBDocumentStore) -> None:
        """Test health check."""
        health = store.health_check()
        assert health.healthy
        assert health.backend == "tinydb"

    def test_concurrent_inserts_do_not_corrupt_store(self, tmp_path: Path) -> None:
        """Concurrent inserts should keep the TinyDB file readable."""
        db_path = tmp_path / "concurrent-docs.json"
        store = TinyDBDocumentStore(db_path=str(db_path))

        def insert_one(index: int) -> None:
            store.insert("telemetry_spans", {"otel_json": f'{{"i": {index}}}'})

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(insert_one, range(250)))

        data = json.loads(db_path.read_text())
        assert len(data.get("telemetry_spans", {})) == 250

    def test_get_nonexistent(self, store: TinyDBDocumentStore) -> None:
        """Test getting a nonexistent document."""
        result = store.get("users", "nonexistent")
        assert result is None

    def test_insert_recovers_from_corrupt_file(self, tmp_path: Path) -> None:
        """Corrupted TinyDB files should be rotated aside and recreated on write."""
        db_path = tmp_path / "docs.json"
        db_path.write_text('{"broken": 1}{"extra": 2}')
        store = TinyDBDocumentStore(db_path=str(db_path))

        doc = store.insert("users", {"name": "Alice"})

        assert doc.id is not None
        assert store.count("users") == 1
        backups = list(tmp_path.glob("docs.json.corrupt-*"))
        assert len(backups) == 1
        assert json.loads(db_path.read_text())

    def test_health_check_recovers_from_corrupt_file(self, tmp_path: Path) -> None:
        """Health check should self-heal a corrupted TinyDB file."""
        db_path = tmp_path / "docs.json"
        db_path.write_text('{"broken": 1}{"extra": 2}')
        store = TinyDBDocumentStore(db_path=str(db_path))

        health = store.health_check()

        assert health.healthy is True
        assert list(tmp_path.glob("docs.json.corrupt-*"))
