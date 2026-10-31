"""WAL-inclusive SQLite online backup for a prevalidated source descriptor."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .source_models import MAX_DB_BYTES, ReasonCode


class DatabaseSnapshotError(RuntimeError):
    """Content-free failure from the SQLite snapshot boundary."""

    def __init__(self, reason: ReasonCode) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _same(a: os.stat_result, b: os.stat_result) -> bool:
    return (a.st_ino, a.st_dev, a.st_size, a.st_mtime_ns) == (
        b.st_ino, b.st_dev, b.st_size, b.st_mtime_ns)


def backup_database(
    source_path: Path, destination: Path, source_fd: int, before: os.stat_result,
) -> int:
    """Include committed WAL rows, integrity-check, and reject source mutation."""
    try:
        if not _same(before, os.lstat(source_path)):
            raise DatabaseSnapshotError(ReasonCode.MUTATED)
        source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
        try:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                row = target.execute("PRAGMA integrity_check").fetchone()
                if not row or row[0] != "ok":
                    raise DatabaseSnapshotError(ReasonCode.INTEGRITY_FAILED)
            finally:
                target.close()
        finally:
            source.close()
    except DatabaseSnapshotError:
        raise
    except sqlite3.DatabaseError as exc:
        raise DatabaseSnapshotError(ReasonCode.CORRUPT_DB) from exc
    if not _same(before, os.fstat(source_fd)) or not _same(before, os.lstat(source_path)):
        raise DatabaseSnapshotError(ReasonCode.MUTATED)
    size = destination.stat().st_size
    if size > MAX_DB_BYTES:
        raise DatabaseSnapshotError(ReasonCode.SIZE_EXCEEDED)
    return size


__all__ = ["DatabaseSnapshotError", "backup_database"]
