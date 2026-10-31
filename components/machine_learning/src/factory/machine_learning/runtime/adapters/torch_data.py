"""Data loading, windowing, and scaling helpers for the torch time-series
adapter.

Provides three small, dependency-light utilities shared by the
torch-based time-series training pipeline:

* ``load_array`` — loads a 1D/2D ``.npy`` or ``.parquet`` array from a
  ``file://`` URI or a bare filesystem path. Behaviour mirrors the
  sklearn adapter helper so the two adapters stay interchangeable from
  the caller's point of view.
* ``to_windows`` — converts a flat ``(timesteps, features)`` array into
  the ``(windows, window_size, features)`` shape that torch sequence
  models expect. If the input is already 3D, it is returned unchanged
  so callers can pass either layout without branching.
* ``fit_scaler_transform`` / ``apply_scaler`` — train-time / inference
  helpers around ``sklearn.preprocessing.StandardScaler`` so the model
  sees zero-mean unit-variance inputs. The scaler is fit on the
  training windows only and its ``mean_`` / ``scale_`` are returned
  alongside the scaled array so they can be persisted in the
  checkpoint and reapplied at inference.

All helpers raise ``ValueError`` on unsupported inputs rather than
silently coercing data, so training jobs fail loudly on bad inputs.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

__all__ = ["apply_scaler", "fit_scaler_transform", "load_array", "to_windows"]


def load_array(uri: str) -> np.ndarray:
    """Load a 1D/2D array from a ``.npy`` or ``.parquet`` URI or path.

    Strips an optional ``file://`` scheme via :func:`urllib.parse.urlparse`
    so callers can pass either a filesystem path or a fully-qualified
    URI interchangeably. Mirrors the sklearn adapter's load helper so
    the same dataset URIs can be reused across backends.

    Args:
        uri: Filesystem path or ``file://`` URI pointing at a ``.npy``
            or ``.parquet`` file.

    Returns:
        The loaded array as a ``numpy.ndarray``.

    Raises:
        ValueError: If the extension is not ``.npy`` or ``.parquet``.
    """
    # urlparse is cheap; we re-parse twice below rather than caching to
    # keep the helper readable and avoid a one-line ``if/else`` dance.
    if urlparse(uri).scheme == "file":
        path = urlparse(uri).path
    else:
        path = uri
    if path.endswith(".npy"):
        # allow_pickle=False blocks a known pickle-RCE vector: a malicious
        # .npy could embed an object whose __reduce__ runs arbitrary code
        # at load time. The torch time-series pipeline only ever writes
        # plain numeric arrays, so disallow pickle for free.
        return np.load(path, allow_pickle=False)
    if path.endswith(".parquet"):
        return pd.read_parquet(path).to_numpy()
    raise ValueError(f"Unsupported data extension: {path}")


def to_windows(X: np.ndarray, window_size: int) -> np.ndarray:
    """Reshape a 2D time-series array into non-overlapping windows.

    Accepts two layouts:

    * ``X.ndim == 3`` — already windowed, returned unchanged so the
      caller can pass either form without branching.
    * ``X.ndim == 2`` — reshaped from ``(timesteps, features)`` to
      ``(timesteps // window_size, window_size, features)``.

    The reshape is non-overlapping and requires ``timesteps`` to be an
    exact multiple of ``window_size``; partial trailing windows are
    rejected rather than dropped to keep the mapping lossless and
    audit-friendly.

    Args:
        X: Input array, either ``(timesteps, features)`` or
            ``(windows, window_size, features)``.
        window_size: Number of timesteps per window.

    Returns:
        Array with shape ``(windows, window_size, features)``.

    Raises:
        ValueError: If ``X.ndim`` is not 2 or 3, or if the 2D input
            length is not divisible by ``window_size``.
    """
    if X.ndim == 3:
        return X
    if X.ndim != 2:
        raise ValueError(
            f"to_windows expects a 2D or 3D array, got ndim={X.ndim}"
        )
    timesteps, features = X.shape
    if timesteps % window_size != 0:
        raise ValueError(
            f"timesteps={timesteps} is not divisible by window_size={window_size}"
        )
    # NumPy can do this in one reshape because (timesteps, features) is
    # already C-contiguous; the result is a view, not a copy.
    return X.reshape(timesteps // window_size, window_size, features)


def fit_scaler_transform(
    X: np.ndarray, n_train_windows: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit a ``StandardScaler`` on the training windows and transform all.

    Unnormalised inputs make LSTM/TCN training unstable: the recurrent
    gates and conv kernels see raw feature scales and gradients explode
    or vanish. Fitting on the train windows only (and reusing those
    stats for the validation windows) keeps the validation metrics
    honest — if we fit on the full series the val windows would leak
    their own statistics into the scaler.

    Args:
        X: 3D array of shape ``(n_samples, window_size, n_features)``.
        n_train_windows: Number of leading windows that belong to the
            training split. Must be in ``[1, n_samples]``.

    Returns:
        A 3-tuple ``(X_scaled, mean_, scale_)`` where ``X_scaled`` is
        the full input array rescaled in-place shape, and ``mean_`` /
        ``scale_`` are the per-feature scaler statistics (1D arrays of
        length ``n_features``) that must be persisted alongside the
        model so inference inputs are normalised identically.
    """
    n_features = X.shape[-1]
    window_size = X.shape[1]
    X_flat = X.reshape(-1, n_features)
    scaler = StandardScaler()
    # The first n_train_windows * window_size rows correspond to train
    # windows in row-major flattening — fit strictly on those.
    scaler.fit(X_flat[: n_train_windows * window_size])
    X_scaled = scaler.transform(X_flat).reshape(X.shape).astype(np.float32)
    return X_scaled, scaler.mean_, scaler.scale_


def apply_scaler(X: np.ndarray, mean: Any, scale: Any) -> np.ndarray:
    """Reapply a saved scaler to a new array (inference-time normalisation).

    Accepts ``mean`` / ``scale`` as a numpy array, a torch tensor (the
    common case — we save them as ``torch.from_numpy(...)`` so the
    checkpoint stays ``weights_only=True``-safe), or a plain Python
    list. Anything ``numpy.asarray`` can coerce works.

    Args:
        X: 3D array of shape ``(n_samples, window_size, n_features)``.
        mean: Per-feature mean of length ``n_features``.
        scale: Per-feature std of length ``n_features``.

    Returns:
        The rescaled array, same shape as ``X`` and ``float32`` dtype.
    """
    n_features = X.shape[-1]
    X_flat = X.reshape(-1, n_features)
    mean_arr = mean.numpy() if hasattr(mean, "numpy") else np.asarray(mean)
    scale_arr = scale.numpy() if hasattr(scale, "numpy") else np.asarray(scale)
    return ((X_flat - mean_arr) / scale_arr).reshape(X.shape).astype(np.float32)
