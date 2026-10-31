"""Tests for blob storage adapters."""

import pytest
from pathlib import Path

from factory.storage.runtime.adapters.blob_local import LocalBlobStore


class TestLocalBlobStore:
    """Tests for LocalBlobStore adapter."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> LocalBlobStore:
        """Create a temporary blob store."""
        return LocalBlobStore(root_path=str(tmp_path / "blobs"))

    def test_put_and_get(self, store: LocalBlobStore) -> None:
        """Test storing and retrieving a blob."""
        data = b"hello world"
        meta = store.put("test.txt", data, "text/plain")

        assert meta.key == "test.txt"
        assert meta.size == len(data)
        assert meta.content_type == "text/plain"

        content, retrieved_meta = store.get("test.txt")
        assert content == data
        assert retrieved_meta.key == "test.txt"

    def test_delete(self, store: LocalBlobStore) -> None:
        """Test deleting a blob."""
        store.put("to_delete.txt", b"delete me")
        assert store.exists("to_delete.txt")

        deleted = store.delete("to_delete.txt")
        assert deleted
        assert not store.exists("to_delete.txt")

    def test_delete_nonexistent(self, store: LocalBlobStore) -> None:
        """Test deleting a nonexistent blob."""
        deleted = store.delete("nonexistent.txt")
        assert not deleted

    def test_exists(self, store: LocalBlobStore) -> None:
        """Test checking blob existence."""
        assert not store.exists("new.txt")
        store.put("new.txt", b"content")
        assert store.exists("new.txt")

    def test_list_keys(self, store: LocalBlobStore) -> None:
        """Test listing blobs."""
        store.put("a/file1.txt", b"1")
        store.put("a/file2.txt", b"2")
        store.put("b/file3.txt", b"3")

        all_blobs = store.list_keys()
        assert len(all_blobs) == 3

        a_blobs = store.list_keys(prefix="a/")
        assert len(a_blobs) == 2

    def test_list_keys_with_limit(self, store: LocalBlobStore) -> None:
        """Test listing blobs with limit."""
        for i in range(5):
            store.put(f"file{i}.txt", b"x")

        limited = store.list_keys(limit=3)
        assert len(limited) == 3

    def test_health_check(self, store: LocalBlobStore) -> None:
        """Test health check."""
        health = store.health_check()
        assert health.healthy
        assert health.backend == "local"
        assert health.latency_ms >= 0

    def test_get_nonexistent(self, store: LocalBlobStore) -> None:
        """Test getting a nonexistent blob."""
        with pytest.raises(FileNotFoundError):
            store.get("nonexistent.txt")

    def test_metadata(self, store: LocalBlobStore) -> None:
        """Test storing and retrieving metadata."""
        meta = store.put(
            "with_meta.txt",
            b"content",
            "text/plain",
            metadata={"author": "test", "version": "1"},
        )
        assert meta.metadata == {"author": "test", "version": "1"}

        _, retrieved = store.get("with_meta.txt")
        assert retrieved.metadata == {"author": "test", "version": "1"}
