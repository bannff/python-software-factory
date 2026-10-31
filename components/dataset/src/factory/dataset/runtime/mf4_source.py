"""Secure, descriptor-backed MF4 source streams."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BufferedReader, DEFAULT_BUFFER_SIZE
import os
from pathlib import Path
import stat

from .atomic_io import open_file_no_follow


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _require_regular(metadata: os.stat_result, path: Path) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"MF4 source is not a regular file: {path}")


def _open_checked_descriptor(path: Path) -> int:
    initial = os.stat(path, follow_symlinks=False)
    _require_regular(initial, path)
    descriptor = open_file_no_follow(path, os.O_RDONLY)
    try:
        opened = os.fstat(descriptor)
        current = os.stat(path, follow_symlinks=False)
        _require_regular(opened, path)
        _require_regular(current, path)
        expected = _identity(initial)
        if _identity(opened) != expected or _identity(current) != expected:
            raise ValueError(f"MF4 source changed while opening: {path}")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


@contextmanager
def open_mf4_stream(path: Path) -> Iterator[BufferedReader]:
    """Yield one buffered stream owning a pinned, regular-file descriptor."""
    source = Path(path)
    try:
        descriptor = _open_checked_descriptor(source)
    except Exception as error:
        raise ValueError(f"Failed to open MF4 file {source}: {error}") from error
    try:
        stream = os.fdopen(descriptor, "rb", buffering=DEFAULT_BUFFER_SIZE)
    except Exception:
        os.close(descriptor)
        raise
    try:
        yield stream
    finally:
        stream.close()


__all__ = ["open_mf4_stream"]
