"""Reentrant process and directory authority lock for local CAN lifecycle I/O."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import fcntl
import os
import threading
from typing import Iterator

from .local_can_files import open_lock, verify_lock

_PROCESS_LOCK = threading.RLock()
_DEPTH = threading.local()


@contextmanager
def lock_authority(directory_fd: int) -> Iterator[None]:
    """Serialize threads and processes, while permitting nested effect locks."""
    with _PROCESS_LOCK:
        depth = getattr(_DEPTH, "value", 0)
        if depth:
            _DEPTH.value = depth + 1
            try:
                yield
            finally:
                _DEPTH.value -= 1
            return
        authority = os.open(
            ".", os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY,
            dir_fd=directory_fd,
        )
        try:
            fcntl.flock(authority, fcntl.LOCK_EX)
            _DEPTH.value = 1
            yield
        finally:
            _DEPTH.value = 0
            fcntl.flock(authority, fcntl.LOCK_UN)
            os.close(authority)


@contextmanager
def lock_scope(directory_fd: int, name: str, *, authority: bool) -> Iterator[None]:
    """Hold one lifecycle lock; ``authority`` also serializes on the directory.

    Skipping the authority is required for effect locks taken while the
    whole-run attempt lock already owns the process-wide authority.
    """
    descriptor = open_lock(directory_fd, name)
    try:
        guard = lock_authority(directory_fd) if authority else nullcontext()
        with guard:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            verify_lock(directory_fd, name, descriptor)
            yield
            verify_lock(directory_fd, name, descriptor)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


__all__ = ["lock_authority", "lock_scope"]
