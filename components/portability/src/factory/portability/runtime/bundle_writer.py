"""Safe, owner-scoped write of a bundle dict to disk.

The write side has no analogue in migration (which only reads an external
tree) — this is new surface, scoped narrowly: every destination must
resolve strictly inside an operator-configured export root
(``PORTABILITY_EXPORT_ROOT``, same env-var-root convention as
``KIROCREW_IMPORT_ROOT``), the resolved path must not be or pass through a
symlink, and the final file is written atomically (temp file + rename) so
a crash mid-write never leaves a half-written, corrupt-looking bundle.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class BundleWriteError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _export_root() -> Path:
    raw = os.getenv("PORTABILITY_EXPORT_ROOT", "").strip()
    if not raw:
        raise BundleWriteError("portability_export_root_not_configured")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise BundleWriteError("portability_export_root_must_be_absolute")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve_destination(relative_name: str) -> Path:
    """Resolve a caller-supplied bundle filename strictly inside the
    configured export root. Rejects traversal and symlinks; never opens
    a path outside the root regardless of what the caller passes."""
    if not relative_name or "/" in relative_name or "\\" in relative_name or relative_name in (".", ".."):
        raise BundleWriteError("portability_export_name_invalid")
    root = _export_root()
    candidate = root / relative_name
    if candidate.exists() and candidate.is_symlink():
        raise BundleWriteError("portability_export_symlink_rejected")
    resolved_parent = candidate.parent.resolve()
    if resolved_parent != root:
        raise BundleWriteError("portability_export_path_escapes_root")
    return root / relative_name


def write_bundle(destination: Path, bundle: dict) -> int:
    """Atomically write ``bundle`` as JSON to ``destination``. Returns the
    written byte count. Never partially writes: builds in a temp file in
    the same directory, then renames (atomic on the same filesystem)."""
    payload = json.dumps(bundle, indent=2, sort_keys=True).encode("utf-8")
    fd, tmp_path = tempfile.mkstemp(dir=str(destination.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, destination)
    except OSError:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    return len(payload)


__all__ = ["BundleWriteError", "resolve_destination", "write_bundle"]
