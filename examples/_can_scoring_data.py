"""Data loading + temporal split for the CAN evaluator scoring run.

Keeps the npy I/O and the train/test partitioning out of the main
scoring script so each file stays under the 200 LOC cap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np

DEFAULT_DATA_DIR = Path("/Volumes/Crucial X9/can_data/comparison_results")
DEFAULT_TEST_FRACTION = 0.20


def load_combined(
    data_dir: Path = DEFAULT_DATA_DIR,
) -> Tuple[np.ndarray, np.ndarray]:
    """Load the combined real + synthetic windowed dataset from disk."""
    X = np.load(data_dir / "X_combined.npy", allow_pickle=False)
    y = np.load(data_dir / "y_combined.npy", allow_pickle=False)
    assert X.shape[0] == y.shape[0], "X/y length mismatch"
    assert set(np.unique(y).tolist()).issubset({0, 1}), "non-binary labels"
    return X.astype(np.float32), y.astype(np.int64)


def temporal_split(
    X: np.ndarray,
    y: np.ndarray,
    test_fraction: float = DEFAULT_TEST_FRACTION,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Hold out the last ``test_fraction`` of windows as the test set.

    The first samples become the train set; this mirrors how a real
    deployment sees past data first and only future data is unseen.
    """
    cut = int(X.shape[0] * (1 - test_fraction))
    return X[:cut], y[:cut], X[cut:], y[cut:]
