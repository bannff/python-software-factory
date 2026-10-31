"""Process-backed binary classifier view with no native parent imports."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ..native_lightgbm_contracts import (
    ArtifactPayload, InspectRequest, InspectResult, ScorePayload, ScoreRequest,
    ScoreResult,
)
from ..native_lightgbm_port import NativeLightGBMPort
from .native_lightgbm_process import SubprocessNativeLightGBM

_INSPECT_OPERATION = {"mlflow": "inspect_mlflow", "joblib": "inspect_joblib"}
_SCORE_OPERATION = {"mlflow": "score_mlflow", "joblib": "score_joblib"}


class BinaryBoosterClassifier:
    """Expose sklearn-like inference while native state lives only in children."""

    __slots__ = (
        "_files", "_importances", "_loader", "_port", "_threshold", "_width",
    )

    def __init__(
        self, *, files: dict[str, bytes], loader: str, threshold: float,
        expected_width: int | None, port: NativeLightGBMPort | None = None,
    ) -> None:
        self._files = {name: bytes(value) for name, value in files.items()}
        self._loader = loader
        self._port = port or SubprocessNativeLightGBM()
        result = self._inspect(expected_width, threshold)
        self._width = result.width
        self._threshold = result.threshold
        self._importances = np.asarray(result.importances, dtype=float)

    @classmethod
    def from_mlflow(
        cls, files: dict[str, bytes], *, expected_width: int | None = None,
        port: NativeLightGBMPort | None = None,
    ) -> "BinaryBoosterClassifier":
        return cls(
            files=files, loader="mlflow", threshold=0.5,
            expected_width=expected_width, port=port,
        )

    @classmethod
    def from_joblib(
        cls, content: bytes, *, threshold: float,
        expected_width: int | None = None,
        port: NativeLightGBMPort | None = None,
    ) -> "BinaryBoosterClassifier":
        return cls(
            files={"model.joblib": content}, loader="joblib", threshold=threshold,
            expected_width=expected_width, port=port,
        )

    @property
    def classes_(self) -> np.ndarray:
        return np.array([0, 1], dtype=np.int64)

    @property
    def n_features_in_(self) -> int:
        return self._width

    @property
    def feature_importances_(self) -> np.ndarray:
        return self._importances.copy()

    @property
    def threshold(self) -> float:
        return self._threshold

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        inputs = np.asarray(values)
        if inputs.ndim != 2 or inputs.shape[1] != self._width:
            raise ValueError("LightGBM input width disagrees with sealed metadata")
        with self._materialized() as (root, source):
            values_path = root / "values.npy"
            np.save(values_path, inputs, allow_pickle=False)
            operation = _SCORE_OPERATION[self._loader]
            result = self._port.execute(ScoreRequest(
                operation=operation,
                payload=ScorePayload(
                    source=str(source), values_uri=str(values_path),
                    expected_width=self._width, threshold=self._threshold,
                ),
            ))
        if not isinstance(result, ScoreResult):
            raise ValueError("native_process_protocol_error: score result kind")
        self._require_metadata(result)
        return np.asarray(result.probabilities, dtype=float)

    def predict(self, values: np.ndarray) -> np.ndarray:
        return np.argmax(self.predict_proba(values), axis=1).astype(np.int64)

    def _inspect(self, expected_width: int | None, threshold: float) -> InspectResult:
        with self._materialized() as (_, source):
            operation = _INSPECT_OPERATION[self._loader]
            result = self._port.execute(InspectRequest(
                operation=operation,
                payload=ArtifactPayload(
                    source=str(source), expected_width=expected_width,
                    threshold=threshold,
                ),
            ))
        if not isinstance(result, InspectResult):
            raise ValueError("native_process_protocol_error: inspect result kind")
        return result

    def _require_metadata(self, result: ScoreResult) -> None:
        if (
            result.width != self._width or result.threshold != self._threshold
            or not np.array_equal(np.asarray(result.importances), self._importances)
        ):
            raise ValueError("native LightGBM metadata changed across operations")

    def _materialized(self):
        return _ArtifactMaterialization(self._files, self._loader)


class _ArtifactMaterialization:
    def __init__(self, files: dict[str, bytes], loader: str) -> None:
        self._files, self._loader = files, loader
        self._temp: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> tuple[Path, Path]:
        self._temp = tempfile.TemporaryDirectory(prefix="ml-lightgbm-artifact-")
        root = Path(self._temp.name)
        os.chmod(root, 0o700)
        source = root / ("model" if self._loader == "mlflow" else "model.joblib")
        if self._loader == "mlflow":
            source.mkdir(mode=0o700)
            for name, content in self._files.items():
                (source / name).write_bytes(content)
        else:
            source.write_bytes(self._files["model.joblib"])
        return root, source

    def __exit__(self, *_args: Any) -> None:
        assert self._temp is not None
        self._temp.cleanup()


__all__ = ["BinaryBoosterClassifier"]
