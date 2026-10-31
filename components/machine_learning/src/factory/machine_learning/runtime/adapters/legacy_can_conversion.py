"""Explicit non-contract conversion for archived pre-v2 CAN windows only."""
from __future__ import annotations

from typing import Any

import numpy as np


def legacy_can_windows_to_arrays(
    records: list[dict[str, Any]], *, layout: str = "3d",
) -> tuple[np.ndarray, np.ndarray]:
    """Convert homogeneous legacy ``window_data`` records by explicit opt-in."""
    if layout not in {"2d", "3d"}:
        raise ValueError("layout must be '2d' or '3d'")
    if not records:
        raise ValueError("legacy CAN conversion requires records")
    shape: tuple[int, int] | None = None
    rows: list[list[list[float]]] = []
    labels: list[int] = []
    for index, record in enumerate(records):
        values = record.get("window_data")
        label = record.get("label")
        if not isinstance(values, list) or not values or isinstance(label, bool) \
                or label not in (0, 1):
            raise ValueError(f"invalid legacy CAN window {index}")
        current = (len(values), len(values[0]) if isinstance(values[0], list) else 0)
        if current[1] == 0 or any(not isinstance(row, list) or len(row) != current[1]
                                  for row in values):
            raise ValueError(f"inconsistent legacy CAN window {index}")
        if shape is None:
            shape = current
        elif current != shape:
            raise ValueError("legacy CAN windows must have identical shapes")
        converted: list[list[float]] = []
        for row in values:
            if any(isinstance(value, bool) or not isinstance(value, (int, float))
                   for value in row):
                raise ValueError("legacy CAN values must be numeric")
            converted.append([float(value) for value in row])
        rows.append(converted)
        labels.append(int(label))
    X = np.asarray(rows, dtype=np.float32)
    if layout == "2d":
        X = X.reshape(X.shape[0], -1)
    return X, np.asarray(labels, dtype=np.int64)


__all__ = ["legacy_can_windows_to_arrays"]
