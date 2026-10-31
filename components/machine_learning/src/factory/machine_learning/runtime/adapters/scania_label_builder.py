"""SCANIA failure-mode label builder for the conditional TimeGAN.

The Phase-1 ``scania_failures.npy`` is a ``(N, T, F)`` tensor of raw
failure windows all tagged as the single mode ``aps_failure``. For the
Phase-2 conditional TimeGAN we need a parallel ``scania_labels.npy`` of
shape ``(N, n_modes)`` (one-hot) and a list of human-readable mode
names. The current SCANIA release has no per-row mode labels, so we
infer three coarse failure archetypes from the per-window signal
statistics:

* ``amplitude_spike`` — windows whose peak amplitude is in the top
  quartile. These are the loudest failures, the ones a downstream
  classifier would flag first.
* ``signal_drift`` — windows whose terminal-frame mean is far from the
  initial-frame mean (monotonic drift). These look like slow leak or
  sensor-fouling failures.
* ``aps_failure`` — everything else; the generic catch-all.

Three modes is the smallest number that exercises the conditional
path (the discriminator can learn at least one mode boundary) while
keeping the per-mode class balance large enough (~450 windows each)
to train a stable GAN.

This is an offline one-shot utility: run it once after the Phase-1
extractor, then point :class:`ConditionalTimeGANAdapter.train` at the
``scania_labels.npy`` it produces. Re-running with a different
``n_modes`` will overwrite the file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

_logger = logging.getLogger(__name__)

# Default mode vocabulary used by the helper and the adapter. Kept in
# one place so tests and CLI drivers reference the same string tokens.
DEFAULT_MODE_NAMES: tuple[str, ...] = (
    "amplitude_spike",
    "signal_drift",
    "aps_failure",
)


def _percentile_rank(values: np.ndarray) -> np.ndarray:
    """Return the per-element percentile rank in [0, 1]."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.linspace(0.0, 1.0, num=values.size)
    return ranks


def assign_failure_modes(
    X: np.ndarray, mode_names: tuple[str, ...] | list[str] = DEFAULT_MODE_NAMES,
) -> tuple[np.ndarray, list[str]]:
    """Assign each window in ``X`` to one of ``mode_names`` (one-hot Y).

    The assignment is rule-based (no clustering) so the output is
    deterministic and reproducible across runs. The two special modes
    (``amplitude_spike``, ``signal_drift``) are reserved for windows
    meeting their signal-statistic criteria; the rest fall into the
    catch-all ``aps_failure`` mode. ``mode_names`` must be a 3-tuple in
    ``(amplitude_spike, signal_drift, aps_failure)`` order — anything
    else collapses to the catch-all.

    Returns ``(Y, mode_names)``: ``Y`` is a ``(N, 3)`` one-hot array;
    ``mode_names`` is the canonical mode list (in fixed order so the
    integers map stably across the train/sample path).
    """
    if X.ndim != 3:
        raise ValueError(f"Expected 3D window tensor (N, T, F); got ndim={X.ndim}")
    names = list(mode_names)
    if len(names) != 3:
        raise ValueError(
            f"assign_failure_modes expects exactly 3 mode names; got {len(names)}: {names}",
        )
    peak_per_window = X.max(axis=(1, 2))           # (N,)
    drift_per_window = np.abs(X[:, -1, :].mean(axis=1) - X[:, 0, :].mean(axis=1))
    peak_rank = _percentile_rank(peak_per_window)
    drift_rank = _percentile_rank(drift_per_window)
    # Reserve the top quartile of each statistic for its dedicated mode.
    # Overlap is allowed: a window can be both a spike and a drift, in
    # which case the spike wins (it's the more diagnostic signal).
    n_samples = X.shape[0]
    Y = np.zeros((n_samples, 3), dtype=np.float32)
    spike_mask = peak_rank >= 0.75
    drift_mask = (~spike_mask) & (drift_rank >= 0.75)
    fallback_mask = ~(spike_mask | drift_mask)
    Y[spike_mask, 0] = 1.0
    Y[drift_mask, 1] = 1.0
    Y[fallback_mask, 2] = 1.0
    # Edge case: if any branch is empty (extreme input), rebalance by
    # promoting the highest-ranked unassigned window so every mode has
    # at least one training example.
    for col in range(3):
        if Y[:, col].sum() == 0:
            # Pick the highest-rank candidate not already pinned.
            if col == 0 and peak_per_window.size:
                idx = int(np.argmax(peak_per_window))
            elif col == 1 and drift_per_window.size:
                idx = int(np.argmax(drift_per_window))
            else:
                idx = 0
            Y[idx] = 0.0
            Y[idx, col] = 1.0
    counts = Y.sum(axis=0).astype(int).tolist()
    _logger.info("Failure-mode assignment: %s -> %s", names, counts)
    return Y, names


def build_scaria_labels(
    X_uri: str, output_uri: str,
    mode_names: tuple[str, ...] | list[str] = DEFAULT_MODE_NAMES,
) -> tuple[np.ndarray, list[str]]:
    """Load ``X_uri`` (``.npy``) and write ``scania_labels.npy`` next to it.

    The input must be a 3D ``(N, T, F)`` window tensor — the same
    shape produced by the Phase-1 ``ScaniaPatternExtractor``. The
    output is a ``(N, n_modes)`` float32 one-hot ``.npy``.
    """
    in_path = Path(X_uri)
    X = np.load(in_path, allow_pickle=False)
    Y, names = assign_failure_modes(X, mode_names)
    out_path = Path(output_uri)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(out_path, Y.astype(np.float32))
    return Y, names


if __name__ == "__main__":  # pragma: no cover - driver CLI
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("X_uri", help="Path to scania_failures.npy")
    parser.add_argument("output_uri", help="Path to write scania_labels.npy")
    parser.add_argument("--mode-names", nargs=3, default=list(DEFAULT_MODE_NAMES))
    args = parser.parse_args()
    Y, names = build_scaria_labels(args.X_uri, args.output_uri, args.mode_names)
    print(json.dumps({
        "labels_shape": list(Y.shape),
        "mode_names": names,
        "per_mode_counts": Y.sum(axis=0).astype(int).tolist(),
        "output_uri": args.output_uri,
    }, indent=2))
