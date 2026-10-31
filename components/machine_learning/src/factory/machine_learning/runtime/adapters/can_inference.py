"""Verified LightGBM inference through Dataset ref-only v2 windowing."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ..can_feature_contract import CanFeatureContract, load_can_feature_contract
from ..can_inference_contracts import CanPredictionSuccess
from ..can_keystone_helpers import write_sampled_jsonl
from ..can_keystone_runner import run_keystone_stage
from ..can_materializer import materialize_can_windows
from .jsonl_to_npy import load_jsonl_windows

_ALERT_BANDS = ((0.3, "warning"), (0.7, "critical"))


class CanInferenceBridge:
    """Bind one verified LightGBM/joblib artifact to one exact contract."""

    def __init__(
        self, *, model_id: str, model_path: str, model_digest: str,
        model_type: str, loader_id: str, contract_uri: str,
        contract_digest: str, can_id: str, required_shape: tuple[int, int],
        required_width: int, threshold: float = 0.5,
        storage_root: str | None = None,
    ) -> None:
        if model_type != "lightgbm" or loader_id not in {"joblib", "mlflow.lightgbm"}:
            raise ValueError("live CAN inference supports LightGBM native flavor or legacy joblib")
        path = Path(model_path)
        joblib_content: bytes | None = None
        if loader_id == "joblib":
            joblib_content = path.read_bytes()
            if hashlib.sha256(joblib_content).hexdigest() != model_digest:
                raise ValueError("model artifact digest mismatch")
        else:
            if not storage_root:
                raise ValueError("MLflow LightGBM loading requires passport storage root")
            from ..passport_trees import mlflow_lightgbm_artifact_ref
            exact = mlflow_lightgbm_artifact_ref("model", path, storage_root)
            if exact.digest != model_digest:
                raise ValueError("model flavor tree digest mismatch")
        self.model_id = model_id
        self.model_digest = model_digest
        self.contract_uri = contract_uri
        self.contract: CanFeatureContract = load_can_feature_contract(contract_uri)
        if self.contract.digest != contract_digest or self.contract.can_id != can_id:
            raise ValueError("registry and contract identity disagree")
        if tuple(required_shape) != self.contract.required_shape:
            raise ValueError("registry input shape disagrees with contract")
        if required_width != self.contract.required_width:
            raise ValueError("registry model width disagrees with contract")
        self.required_shape = self.contract.required_shape
        self.required_width = self.contract.required_width
        self.threshold = float(threshold)
        from .mlflow_lightgbm import load_legacy_joblib, load_lightgbm_flavor
        if loader_id == "joblib":
            assert joblib_content is not None
            self._model = load_legacy_joblib(
                joblib_content, threshold=self.threshold,
                expected_width=self.required_width,
            )
        else:
            self._model = load_lightgbm_flavor(
                path, expected_width=self.required_width,
            )
            if self.threshold != self._model.threshold:
                raise ValueError("bridge threshold disagrees with sealed model threshold")
        model_width = getattr(self._model, "n_features_in_", None)
        if model_width is None or int(model_width) != self.required_width:
            raise ValueError("model width disagrees with registry binding")
        importances = getattr(self._model, "feature_importances_", None)
        if importances is not None and len(importances) != self.required_width:
            raise ValueError("feature_importances width disagrees with model input")

    def predict_window(
        self, records: list[dict[str, Any]], *, request_digest: str,
    ) -> CanPredictionSuccess:
        if request_digest != self.contract.digest:
            raise ValueError("request and registry contract digests disagree")
        if not records:
            raise ValueError("inference requires non-empty raw records")
        if any(str(record.get("arbitration_id")) != self.contract.can_id for record in records):
            raise ValueError("raw records contain a different CAN-ID")
        with tempfile.TemporaryDirectory(prefix="can-inference-") as directory:
            root = Path(directory)
            snapshots = root / "snapshots"
            raw_uri = write_sampled_jsonl(records, snapshots, "inference")
            stage = run_keystone_stage(
                "inference_window", "recipe://local/can-window@2", [
                    raw_uri, self.contract.prior_data_policy_ref.uri,
                    self.contract.signal_schema_ref.uri,
                ], self._window_config(), snapshots, root,
                f"inference:{self.model_id}:{self.contract.digest}",
                input_roles=[
                    "primary_dataset", "prior_data_policy",
                    f"signal_schema:{self.contract.can_id}",
                ], poll_interval_s=0.01, poll_timeout_s=60.0,
            )
            if "error" in stage:
                raise ValueError(stage["error"])
            windows = load_jsonl_windows(stage["dataset_uri"])
        batch = materialize_can_windows(windows, self.contract, flatten=True)
        if batch.X.shape[1:] != (self.required_width,):
            raise ValueError("materialized inference width disagrees with registry")
        score = self._score(batch.X)
        return CanPredictionSuccess(
            model_id=self.model_id, contract_digest=self.contract.digest,
            can_id=self.contract.can_id, anomaly_score=round(score, 6),
            prediction="anomaly" if score > self.threshold else "normal",
            confidence=round(max(score, 1.0 - score), 6),
            alert_level=_score_to_alert(score), top_signals=tuple(self._top_signals()),
            window_size=int(batch.X.shape[0]), input_shape=tuple(batch.X.shape),
        )

    def _window_config(self) -> dict[str, Any]:
        contract = self.contract
        return {
            "window_size_ms": contract.window_size_ms,
            "step_size_ms": contract.step_size_ms,
            "grid_resolution_ms": contract.grid_resolution_ms,
            "observation_cutoff_ms": contract.observation_cutoff_ms,
            "label_horizon_ms": contract.label_horizon_ms,
        }

    def _score(self, X: np.ndarray) -> float:
        from .mlflow_lightgbm import validated_probabilities
        scores = validated_probabilities(self._model, X)
        score = float(np.mean(scores[:, 1]))
        return max(0.0, min(1.0, score))

    def _top_signals(self) -> list[dict[str, Any]]:
        importances = getattr(self._model, "feature_importances_", None)
        if importances is None:
            return []
        pairs = sorted(
            zip(_model_columns(self.contract, self.required_width), map(float, importances)),
            key=lambda pair: pair[1], reverse=True,
        )
        return [{"signal": name, "importance": value} for name, value in pairs[:5]]


def _model_columns(contract: CanFeatureContract, width: int) -> list[str]:
    columns = list(contract.ordered_columns)
    if width == len(columns):
        return columns
    return [f"t{step}:{column}" for step in range(contract.num_timesteps) for column in columns]


def _score_to_alert(score: float) -> str:
    level = "normal"
    for threshold, label in _ALERT_BANDS:
        if score >= threshold:
            level = label
    return level


__all__ = ["CanInferenceBridge"]
