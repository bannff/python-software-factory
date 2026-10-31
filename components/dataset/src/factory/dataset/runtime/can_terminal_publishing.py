"""Content-addressed publication for prepared CAN tensors."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import numpy as np

from .atomic_io import atomic_write_immutable


def publish_npy(root: Path, label: str, value: np.ndarray) -> dict[str, Any]:
    stream = io.BytesIO()
    np.save(stream, value, allow_pickle=False)
    return publish_bytes(root, label, stream.getvalue(), ".npy")


def publish_bytes(
    root: Path, label: str, content: bytes, suffix: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(content).hexdigest()
    path = root / f"{label}-{digest}{suffix}"
    atomic_write_immutable(path, content)
    return {
        "uri": path.resolve().as_uri(), "sha256": digest,
        "evidence": {"sha256": digest},
    }


__all__ = ["publish_bytes", "publish_npy"]
