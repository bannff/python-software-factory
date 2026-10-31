"""Local filesystem blob storage adapter."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from factory.storage.runtime.ports import BlobMetadata, StorageHealth


class LocalBlobStore:
    """Local filesystem implementation of BlobStore port."""

    def __init__(self, root_path: str = "./.storage/blobs") -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> BlobMetadata:
        """Atomically replace a blob and its metadata on the local filesystem."""
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = data if isinstance(data, bytes) else data.read()
        meta_data = {
            "content_type": content_type,
            "metadata": metadata or {},
            "etag": hashlib.md5(content).hexdigest(),
        }
        self._atomic_write(path, content)
        self._atomic_write(path.with_suffix(path.suffix + ".meta"), json.dumps(meta_data).encode())
        return BlobMetadata(
            key=key,
            size=len(content),
            content_type=content_type,
            etag=meta_data["etag"],
            last_modified=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        """Write, fsync, and atomically replace a path on the same filesystem."""
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def get(self, key: str) -> tuple[bytes, BlobMetadata]:
        """Retrieve a blob from local filesystem."""
        path = self._key_to_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Blob not found: {key}")
        content = path.read_bytes()
        return content, self._load_metadata(key, path, content)

    def delete(self, key: str) -> bool:
        """Delete a blob from local filesystem."""
        path = self._key_to_path(key)
        meta_path = path.with_suffix(path.suffix + ".meta")
        if path.exists():
            path.unlink()
            if meta_path.exists():
                meta_path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if a blob exists."""
        return self._key_to_path(key).exists()

    def list_keys(self, prefix: str = "", limit: int = 1000) -> list[BlobMetadata]:
        """List blobs with optional prefix prefix."""
        results = []
        for path in self._root.rglob("*"):
            if path.is_file() and path.suffix != ".meta":
                key = str(path.relative_to(self._root))
                if key.startswith(prefix):
                    content = path.read_bytes()
                    results.append(self._load_metadata(key, path, content))
                    if len(results) >= limit:
                        break
        return results

    def health_check(self) -> StorageHealth:
        """Check local filesystem health."""
        start = time.time()
        try:
            test_file = self._root / ".health_check"
            self._atomic_write(test_file, b"ok")
            test_file.unlink()
            return StorageHealth(healthy=True, backend="local", latency_ms=(time.time() - start) * 1000)
        except Exception as exc:
            return StorageHealth(healthy=False, backend="local", message=str(exc))

    def _key_to_path(self, key: str) -> Path:
        """Convert a key to a filesystem path."""
        return self._root / key

    def _load_metadata(self, key: str, path: Path, content: bytes) -> BlobMetadata:
        meta_path = path.with_suffix(path.suffix + ".meta")
        meta_data = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        stat = path.stat()
        return BlobMetadata(
            key=key,
            size=len(content),
            content_type=meta_data.get("content_type", "application/octet-stream"),
            etag=meta_data.get("etag", hashlib.md5(content).hexdigest()),
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            metadata=meta_data.get("metadata", {}),
        )
