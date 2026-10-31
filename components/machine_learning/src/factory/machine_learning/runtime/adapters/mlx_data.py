"""NumPy <-> MLX bridge and batch iterator for the MLX time-series adapter.

Two small responsibilities:

* :func:`to_mlx` / :func:`from_mlx` convert between numpy arrays and
  ``mlx.core.array`` without ever calling ``.numpy()`` (which MLX does
  not expose — the canonical round-trip is ``.tolist()`` or
  ``mx.eval(arr)`` followed by ``np.asarray(arr)``).
* :class:`MLXDataLoader` is a minimal DataLoader equivalent: it wraps
  an in-memory ``(X, y)`` pair and yields shuffled mini-batches as
  ``(mx.array, mx.array)`` tuples. PyTorch's DataLoader is overkill for
  the small, pre-windowed arrays the time-series adapter trains on.

The numpy-side data prep (``load_array``, ``to_windows``,
``fit_scaler_transform``, ``apply_scaler``) is shared with the torch
adapter via :mod:`torch_data` — there is nothing MLX-specific about
loading ``.npy`` files or windowing.
"""

from __future__ import annotations

import math
from typing import Iterator

from .mlx_platform import require_mlx_platform

require_mlx_platform()

import mlx.core as mx  # noqa: E402
import numpy as np  # noqa: E402

__all__ = ["MLXDataLoader", "from_mlx", "to_mlx"]


def to_mlx(arr: np.ndarray) -> mx.array:
    """Convert a numpy array to ``mlx.core.array``.

    MLX arrays live on the unified memory shared with the CPU, so this
    is a zero-copy view for contiguous float32/int32 buffers and a
    single allocation otherwise. No explicit device placement is
    required on Apple Silicon — MLX binds arrays to the default
    device at construction time.
    """
    return mx.array(np.ascontiguousarray(arr))


def from_mlx(arr: mx.array) -> np.ndarray:
    """Convert an ``mlx.core.array`` back to ``numpy.ndarray``.

    ``mlx.core.array`` does not expose ``.numpy()``; the supported
    path is ``np.asarray(arr)``. The conversion triggers MLX's lazy
    evaluation graph (when ``arr`` is the result of a deferred op)
    and produces a numpy view of the underlying buffer.
    """
    # ``np.asarray`` triggers any pending MLX lazy graph and returns
    # a numpy view; ``mx.eval(arr)`` is a side-effecting materialiser
    # that returns ``None`` so we must NOT pipe its result to numpy.
    return np.asarray(arr)


class MLXDataLoader:
    """Minimal mini-batch iterator over an in-memory ``(X, y)`` pair.

    Behaves like ``torch.utils.data.DataLoader`` for the small
    pre-windowed arrays the time-series adapter handles: shuffles the
    index order per epoch, slices contiguous windows, and yields
    ``(mx.array, mx.array)`` tuples on the default MLX device.

    Args:
        X: Training array of shape ``(n_samples, ...)`` — will be
            converted to ``mlx.core.array`` lazily on the first
            iteration.
        y: Label array of shape ``(n_samples,)`` (or
            ``(n_samples, n_classes)`` for soft labels).
        batch_size: Number of samples per mini-batch.
        shuffle: If True, reshuffle the index order every time
            ``__iter__`` is called (i.e. once per epoch).
        drop_last: If True, drop the final partial batch so every
            batch is the same size.
        seed: Optional seed for the per-epoch shuffle; deterministic
            across epochs when the same seed is used.
    """

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        batch_size: int,
        shuffle: bool = True,
        drop_last: bool = False,
        seed: int | None = None,
    ) -> None:
        if len(X) != len(y):
            raise ValueError(
                f"X has {len(X)} samples but y has {len(y)} labels",
            )
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        self._X = X
        self._y = y
        self._batch_size = batch_size
        self._shuffle = shuffle
        self._drop_last = drop_last
        self._seed = seed

    def __len__(self) -> int:
        n = len(self._X)
        if self._drop_last:
            return n // self._batch_size
        return math.ceil(n / self._batch_size)

    def __iter__(self) -> Iterator[tuple[mx.array, mx.array]]:
        n = len(self._X)
        if self._shuffle:
            # MLX's RNG lives in mlx.core.random; using numpy here keeps
            # the loader independent of MLX's lazy evaluation graph
            # and yields a deterministic index order for a given seed.
            rng = np.random.default_rng(self._seed)
            order = rng.permutation(n)
        else:
            order = np.arange(n)
        for start in range(0, n, self._batch_size):
            idx = order[start:start + self._batch_size]
            if self._drop_last and len(idx) < self._batch_size:
                break
            # Slice with a list of indices so non-contiguous (shuffled)
            # batches still produce the correct rows.
            yield to_mlx(self._X[idx]), to_mlx(self._y[idx])
