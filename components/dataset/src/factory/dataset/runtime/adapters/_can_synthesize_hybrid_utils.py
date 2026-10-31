"""URI / tensor-shaping helpers for the can_synthesize hybrid pipeline.

Pure data-shaping primitives: ``file://`` resolution, signal-count
matching, and time-axis resampling. Kept out of
:mod:`can_synthesize_hybrid_helpers` so that file stays under the
200-LOC factory ceiling.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np


def uri_to_path(uri: str) -> Path:
    """Convert a ``file://`` URI or plain path to a :class:`Path`."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    return Path(uri)


def resample_time(window: np.ndarray, target_frames: int) -> np.ndarray:
    """Linearly resample a ``(T, F)`` window to ``(target_frames, F)``."""
    src_frames = window.shape[0]
    if src_frames == target_frames:
        return window
    src_idx = np.linspace(0, src_frames - 1, num=target_frames)
    out = np.empty((target_frames, window.shape[1]), dtype=window.dtype)
    for j in range(window.shape[1]):
        out[:, j] = np.interp(src_idx, np.arange(src_frames), window[:, j])
    return out


def match_signals(
    window: np.ndarray, target_signals: int, rng: np.random.Generator,
) -> np.ndarray:
    """Trim or pad a ``(T, F)`` window to ``(T, target_signals)``.

    Truncation keeps the leading ``target_signals`` columns; padding
    adds Gaussian noise scaled to the window's per-signal std so the
    new columns look like additional independent signals rather than
    zeros.
    """
    T, F = window.shape
    if F >= target_signals:
        return window[:, :target_signals].copy()
    pad = target_signals - F
    tail = rng.normal(0.0, max(float(window.std()), 1e-3), size=(T, pad))
    return np.concatenate([window, tail.astype(window.dtype)], axis=1)
