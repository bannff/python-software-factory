"""Fail-closed server-computed loop stop sentinel."""
from __future__ import annotations

import os
from pathlib import Path


def sentinel_exists(loop_id: str, trusted_root: Path, allowed_root: Path) -> bool:
    root = trusted_root.resolve(strict=True)
    allowed = allowed_root.resolve(strict=True)
    try:
        root.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError("loop project root is not allowed") from exc
    path = root / f".companion-loop-stop-{loop_id}"
    if path.parent != root:
        raise RuntimeError("invalid loop stop sentinel")
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError("loop stop sentinel check failed") from exc
    return True


__all__ = ["sentinel_exists"]
