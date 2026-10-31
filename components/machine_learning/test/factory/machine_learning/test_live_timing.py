"""Request-scoped live timing artifact contract tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from factory.machine_learning.runtime import live_timing
from factory.machine_learning.runtime.live_timing import (
    LiveTimingArtifactRef, load_live_timing,
)


def _ref(path: Path, digest: str | None = None) -> LiveTimingArtifactRef:
    return LiveTimingArtifactRef(
        uri=path.as_uri(),
        digest=digest or hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_live_timing_reads_exact_stat_size_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "live.npy"
    expected = np.asarray([[1, 2], [3, 4]], dtype=np.int64)
    np.save(path, expected)
    requested_sizes: list[int] = []
    original_read = live_timing.os.read

    def tracked_read(descriptor: int, size: int) -> bytes:
        requested_sizes.append(size)
        return original_read(descriptor, size)

    monkeypatch.setattr(live_timing.os, "read", tracked_read)
    actual = load_live_timing(_ref(path), (2, 2))
    assert requested_sizes == [path.stat().st_size]
    assert actual.dtype == np.float64
    np.testing.assert_array_equal(actual, expected)


def test_live_timing_rejects_one_call_short_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "live.npy"
    np.save(path, np.ones((2, 2), dtype=np.float64))
    requested_sizes: list[int] = []
    original_read = live_timing.os.read

    def short_read(descriptor: int, size: int) -> bytes:
        requested_sizes.append(size)
        return original_read(descriptor, size)[:-1]

    monkeypatch.setattr(live_timing.os, "read", short_read)
    with pytest.raises(ValueError, match="changed during exact-byte read"):
        load_live_timing(_ref(path), (2, 2))
    assert requested_sizes == [path.stat().st_size]


@pytest.mark.parametrize("values", [
    np.asarray([[1.0, np.nan]]),
    np.asarray([[1.0, 0.0]]),
    np.asarray([[1.0, -1.0]]),
    np.asarray([[1.0]], dtype=object),
])
def test_live_timing_rejects_invalid_values(tmp_path: Path, values: np.ndarray) -> None:
    path = tmp_path / "invalid.npy"
    np.save(path, values)
    with pytest.raises(ValueError, match="live timing"):
        load_live_timing(_ref(path), (1, 2))


def test_live_timing_rejects_digest_shape_format_and_remote_uri(tmp_path: Path) -> None:
    path = tmp_path / "live.npy"
    np.save(path, np.ones((2, 2), dtype=np.float64))
    with pytest.raises(ValueError, match="digest"):
        load_live_timing(_ref(path, "0" * 64), (2, 2))
    with pytest.raises(ValueError, match="exact live shape"):
        load_live_timing(_ref(path), (1, 2))
    renamed = tmp_path / "live.bin"
    renamed.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match=".npy format"):
        load_live_timing(_ref(renamed), (2, 2))
    remote = LiveTimingArtifactRef(uri="https://example.invalid/live.npy", digest="0" * 64)
    with pytest.raises(ValueError, match="local file URI"):
        load_live_timing(remote, (2, 2))
    with pytest.raises(ValidationError):
        LiveTimingArtifactRef(uri=path.as_uri(), digest="0" * 64, role="training")
