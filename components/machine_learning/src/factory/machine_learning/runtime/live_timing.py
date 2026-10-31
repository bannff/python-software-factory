"""Ephemeral, caller-bound timing input for promoted neural inference."""
from __future__ import annotations

import hashlib
import io
import os
import stat
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator

from .passport_validation import require_digest, require_uri

_MAX_LIVE_TIMING_BYTES = 64 * 1024 * 1024
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class LiveTimingArtifactRef(BaseModel):
    """Exact request-scoped timing bytes; never passport training provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    uri: str
    digest: str

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return require_uri(value, "live timing URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "live timing digest")


def load_live_timing(
    ref: LiveTimingArtifactRef, expected_shape: tuple[int, int],
) -> np.ndarray:
    """Read local bounded ``.npy`` bytes once, then verify and decode them."""
    path = _local_npy_path(ref.uri)
    descriptor = os.open(path, _FILE_FLAGS)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("live timing artifact must be a regular file")
        if metadata.st_size <= 0 or metadata.st_size > _MAX_LIVE_TIMING_BYTES:
            raise ValueError("live timing artifact exceeds the bounded byte contract")
        raw = os.read(descriptor, metadata.st_size)
        if len(raw) != metadata.st_size:
            raise ValueError("live timing artifact changed during exact-byte read")
    finally:
        os.close(descriptor)
    if hashlib.sha256(raw).hexdigest() != ref.digest:
        raise ValueError("live timing digest does not match exact bytes")
    try:
        values = np.load(io.BytesIO(raw), allow_pickle=False)
    except (OSError, ValueError, EOFError) as exc:
        raise ValueError("live timing artifact is not a readable .npy array") from exc
    if (
        not isinstance(values, np.ndarray)
        or values.shape != expected_shape
        or values.dtype.kind not in "fiu"
        or not np.isfinite(values).all()
        or not (values > 0).all()
    ):
        raise ValueError(
            "live timing must be finite positive numeric data of exact live shape"
        )
    return np.asarray(values, dtype=np.float64)


def _local_npy_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme not in {"", "file"} or parsed.netloc not in {"", "localhost"}:
        raise ValueError("live timing requires a local file URI")
    path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(uri)
    if path.suffix.lower() != ".npy":
        raise ValueError("live timing artifact must use .npy format")
    return path


__all__ = ["LiveTimingArtifactRef", "load_live_timing"]
