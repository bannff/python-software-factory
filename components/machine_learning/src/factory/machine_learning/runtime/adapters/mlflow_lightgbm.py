"""Parent-safe validation and subprocess-backed LightGBM flavor loading."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .lightgbm_binary_view import BinaryBoosterClassifier
from ..lightgbm_flavor_contract import (
    ALLOWED_FILES, lightgbm_metadata, validate_lightgbm_flavor,
)


def load_lightgbm_flavor(
    source: str | Path, expected_width: int | None = None,
) -> BinaryBoosterClassifier:
    """Capture a validated flavor and inspect it only in a fresh interpreter."""
    path = Path(source).expanduser().absolute()
    metadata = validate_lightgbm_flavor(path)
    if expected_width is not None and expected_width != metadata["feature_width"]:
        raise ValueError("loaded LightGBM feature width disagrees with passport")
    files = {name: (path / name).read_bytes() for name in sorted(ALLOWED_FILES)}
    return BinaryBoosterClassifier.from_mlflow(files, expected_width=expected_width)


def load_legacy_joblib(
    content: bytes, *, threshold: float = 0.5,
    expected_width: int | None = None,
) -> BinaryBoosterClassifier:
    """Inspect captured legacy bytes only in a fresh interpreter."""
    return BinaryBoosterClassifier.from_joblib(
        bytes(content), threshold=threshold, expected_width=expected_width,
    )


def validated_probabilities(model: Any, values: np.ndarray) -> np.ndarray:
    """Return one child-validated finite binary probability matrix."""
    probabilities = np.asarray(model.predict_proba(values), dtype=float)
    if (
        probabilities.shape != (len(values), 2) or not np.isfinite(probabilities).all()
        or np.any((probabilities < 0.0) | (probabilities > 1.0))
        or not np.allclose(probabilities.sum(axis=1), 1.0, rtol=0, atol=1e-9)
    ):
        raise ValueError("LightGBM probabilities are not finite binary scores")
    return probabilities


__all__ = [
    "lightgbm_metadata", "load_legacy_joblib", "load_lightgbm_flavor",
    "validate_lightgbm_flavor", "validated_probabilities",
]
