"""Cross-process coordination for filesystem-backed Graph snapshots."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def cross_process_lock(store: Any, snapshot_key: str) -> Iterator[None]:
    """Serialize local writers when the BlobStore has no compare-and-swap port.

    The storage BlobStore contract only guarantees atomic replacement, not CAS.
    The local adapter exposes its root, so an advisory lock closes the
    cross-process lost-update window without introducing another state store.
    Other BlobStore implementations remain a single-writer boundary and must
    provide serialization externally until the shared port grows a CAS seam.
    """
    root = getattr(store, "_root", None)
    if root is None:
        yield
        return
    try:
        import fcntl
    except ImportError:  # pragma: no cover - supported deployment is POSIX.
        yield
        return

    lock_path = Path(root) / f".{Path(snapshot_key).name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = ["cross_process_lock"]
