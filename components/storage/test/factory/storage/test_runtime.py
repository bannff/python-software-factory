"""Tests for storage runtime."""

import pytest
from pathlib import Path

from factory.storage.runtime.runtime import StorageRuntime, get_runtime, reset_runtime


class TestStorageRuntime:
    """Tests for StorageRuntime."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset global runtime before each test."""
        reset_runtime()

    def test_available_backends(self) -> None:
        """Test listing available backends."""
        backends = StorageRuntime.available_backends()

        assert "blob" in backends
        assert "local" in backends["blob"]
        assert "s3" in backends["blob"]

        assert "document" in backends
        assert "tinydb" in backends["document"]

        assert "sql" in backends
        assert "sqlite" in backends["sql"]

        assert "graph" in backends
        assert "networkx" in backends["graph"]

    def test_get_blob_store(self, tmp_path: Path) -> None:
        """Test getting a blob store."""
        runtime = StorageRuntime()
        store = runtime.get_blob_store("local", root_path=str(tmp_path / "blobs"))

        # Should be able to use it
        store.put("test.txt", b"hello")
        assert store.exists("test.txt")

    def test_get_document_store(self, tmp_path: Path) -> None:
        """Test getting a document store."""
        runtime = StorageRuntime()
        store = runtime.get_document_store("tinydb", db_path=str(tmp_path / "docs.json"))

        doc = store.insert("test", {"key": "value"})
        assert doc.id is not None

    def test_get_sql_store(self, tmp_path: Path) -> None:
        """Test getting a SQL store."""
        runtime = StorageRuntime()
        store = runtime.get_sql_store("sqlite", db_path=str(tmp_path / "test.db"))

        store.execute("CREATE TABLE test (id INTEGER)")
        assert store.table_exists("test")

    def test_get_graph_store(self) -> None:
        """Test getting a graph store."""
        runtime = StorageRuntime()
        store = runtime.get_graph_store("networkx")

        node = store.add_node(["Test"], {"name": "test"})
        assert node.id is not None

    def test_store_caching(self, tmp_path: Path) -> None:
        """Test that stores are cached."""
        runtime = StorageRuntime()
        path = str(tmp_path / "blobs")

        store1 = runtime.get_blob_store("local", root_path=path)
        store2 = runtime.get_blob_store("local", root_path=path)

        assert store1 is store2

    def test_health_check_empty(self) -> None:
        """Test health check with no active stores."""
        runtime = StorageRuntime()
        health = runtime.health_check()
        assert health == {}

    def test_health_check_with_stores(self, tmp_path: Path) -> None:
        """Test health check with active stores."""
        runtime = StorageRuntime()
        runtime.get_blob_store("local", root_path=str(tmp_path / "blobs"))
        runtime.get_graph_store("networkx")

        health = runtime.health_check()
        assert len(health) == 2

    def test_unknown_backend_raises(self) -> None:
        """Test that unknown backends raise ValueError."""
        runtime = StorageRuntime()

        with pytest.raises(ValueError, match="Unknown blob backend"):
            runtime.get_blob_store("unknown")

        with pytest.raises(ValueError, match="Unknown document backend"):
            runtime.get_document_store("unknown")

        with pytest.raises(ValueError, match="Unknown SQL backend"):
            runtime.get_sql_store("unknown")

        with pytest.raises(ValueError, match="Unknown graph backend"):
            runtime.get_graph_store("unknown")

    def test_global_runtime(self) -> None:
        """Test global runtime singleton."""
        runtime1 = get_runtime()
        runtime2 = get_runtime()
        assert runtime1 is runtime2

        reset_runtime()
        runtime3 = get_runtime()
        assert runtime3 is not runtime1
