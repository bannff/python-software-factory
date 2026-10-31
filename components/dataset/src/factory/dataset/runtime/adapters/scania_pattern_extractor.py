"""SCANIA APS pattern extraction for conditional TimeGAN training.

The SCANIA APS (Air Pressure System) Failure dataset is a tabular anomaly
benchmark published by Scania CV AB (2016). Each row is a single truck
snapshot with 171 anonymized operational features and a binary
``class`` label (``pos`` = APS component failure, ``neg`` = healthy /
non-APS failure). It is not a true CAN time-series, so we adapt the
"50-frame window" concept:

* For each ``pos`` failure row we construct a 50-frame "drift toward
  failure" trajectory. Frame 0 starts at the per-feature mean of the
  ``neg`` baseline distribution (a "healthy truck" reference) and frame
  49 lands exactly on the failure row's values. Intermediate frames are
  linearly interpolated.
* Signals are z-score normalized per feature (per "CAN ID" in the
  legacy terminology) using the statistics computed across
  every window in the dataset. This is the canonical input contract
  for TimeGAN / RGAN style generators.

Pure data-shaping helpers live in :mod:`_scania_helpers` to keep this
file under the 200 LOC factory ceiling.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ._scania_helpers import (
    SCANIA_BASELINE_MODE,
    SCANIA_FAILURE_MODE,
    SCANIA_HEADER_LINES,
    SCANIA_NA_SENTINELS,
    SCANIA_NEG_LABEL,
    SCANIA_POS_LABEL,
    build_trajectory,
    coerce_records,
    feature_matrix,
    zscore_normalize,
)


class ScaniaPatternExtractor:
    """Extract temporal failure signatures from SCANIA APS data.

    Pure adapter: it loads a SCANIA APS CSV, windows each row into a
    50-frame "drift-toward-failure" trajectory anchored to a healthy
    baseline, z-score normalizes per CAN ID, and writes a single
    ``(n_failures, window_size, n_signals)`` ``.npy`` tensor. Designed
    to be called from either a stage runner (passing
    ``scania_records``) or a Phase-1 driver script (passing
    ``scania_uri`` / ``output_uri``).
    """

    def __init__(self, window_size: int = 50) -> None:
        if window_size < 2:
            raise ValueError("window_size must be >= 2")
        self.window_size = int(window_size)

    def extract_failure_signatures(
        self,
        scania_records: list[dict[str, Any]] | pd.DataFrame | dict[str, Any],
        window_size: int | None = None,
    ) -> dict[str, np.ndarray]:
        """Group records by class, windowize, and z-score normalize.

        Returns a dict keyed by ``failure_mode`` whose values are
        ``(n_windows, window_size, n_signals)`` float32 arrays. The
        ``_can_ids`` entry carries the column names in matrix order.
        """
        ws = int(window_size) if window_size is not None else self.window_size
        records = coerce_records(scania_records)
        if not records:
            raise ValueError("No SCANIA records provided")

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in records:
            cls = str(r.get("class", "")).strip().lower()
            if cls == SCANIA_POS_LABEL:
                groups[SCANIA_FAILURE_MODE].append(r)
            elif cls == SCANIA_NEG_LABEL:
                groups[SCANIA_BASELINE_MODE].append(r)
        if SCANIA_FAILURE_MODE not in groups:
            raise ValueError(
                "No positive (failure) records found; cannot build training data",
            )

        neg_matrix, can_ids = feature_matrix(groups[SCANIA_BASELINE_MODE])
        baseline = neg_matrix.mean(axis=0) if neg_matrix.size else np.zeros(len(can_ids))
        pos_matrix, _ = feature_matrix(groups[SCANIA_FAILURE_MODE])

        # Joint z-score fit so the normalization envelope covers the
        # full operating regime (failure + baseline) the TimeGAN sees.
        all_trajectories = np.concatenate(
            [
                self._windowize_class(pos_matrix, baseline, ws),
                self._windowize_class(neg_matrix, baseline, ws),
            ],
            axis=0,
        )
        normalized = zscore_normalize(all_trajectories)

        n_pos = pos_matrix.shape[0]
        result: dict[str, np.ndarray] = {
            SCANIA_FAILURE_MODE: normalized[:n_pos].astype(np.float32),
        }
        if neg_matrix.size:
            result[SCANIA_BASELINE_MODE] = normalized[n_pos:].astype(np.float32)
        result["_can_ids"] = np.asarray(can_ids, dtype=object)
        return result

    def _windowize_class(
        self,
        matrix: np.ndarray,
        baseline: np.ndarray,
        window_size: int,
    ) -> np.ndarray:
        if matrix.size == 0:
            return np.empty((0, window_size, matrix.shape[1] if matrix.ndim == 2 else 0))
        out = np.empty((matrix.shape[0], window_size, matrix.shape[1]), dtype=np.float64)
        for i, row in enumerate(matrix):
            out[i] = build_trajectory(row, baseline, window_size)
        return out

    def build_training_dataset(
        self,
        scania_uri: str,
        output_uri: str,
    ) -> np.ndarray:
        """Load SCANIA CSVs, windowize failures, and persist a ``.npy`` tensor.

        ``scania_uri`` may point to a single ``aps_failure_*.csv`` or
        a directory containing one. ``output_uri`` is the destination
        ``.npy`` path. The returned array has shape
        ``(n_failures, window_size, n_signals)`` and dtype ``float32``.
        """
        df = self._load_scania_frames(scania_uri)
        if df.empty:
            raise ValueError(f"No SCANIA frames loaded from {scania_uri!r}")

        if (df["class"].str.lower() == SCANIA_POS_LABEL).sum() == 0:
            raise ValueError(f"No positive (failure) records found in {scania_uri!r}")

        feature_cols = [c for c in df.columns if c != "class"]
        records: list[dict[str, Any]] = []
        for cls_value, group in df.groupby(df["class"].str.lower()):
            for _, row in group.iterrows():
                records.append({
                    "class": cls_value,
                    "features": {c: row[c] for c in feature_cols},
                })

        signatures = self.extract_failure_signatures(records, self.window_size)
        tensor = signatures[SCANIA_FAILURE_MODE]

        out_path = Path(output_uri)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(out_path, tensor)
        return tensor

    @staticmethod
    def _load_scania_frames(scania_uri: str) -> pd.DataFrame:
        uri_path = Path(scania_uri)
        candidates: list[Path] = []
        if uri_path.is_dir():
            candidates.extend(sorted(uri_path.glob("aps_failure_*.csv")))
        elif uri_path.is_file() and uri_path.suffix == ".csv":
            candidates.append(uri_path)
        else:
            raise FileNotFoundError(f"SCANIA source not found: {scania_uri!r}")
        if not candidates:
            raise FileNotFoundError(f"No aps_failure_*.csv found under {scania_uri!r}")
        frames = [
            pd.read_csv(p, skiprows=SCANIA_HEADER_LINES, na_values=list(SCANIA_NA_SENTINELS))
            for p in candidates
        ]
        return pd.concat(frames, ignore_index=True)
