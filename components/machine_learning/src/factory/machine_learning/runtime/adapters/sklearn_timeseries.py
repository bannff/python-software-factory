"""Unified time-series training adapter (LightGBM + dispatch to torch/TimeGAN).

Implements :class:`TimeSeriesTrainingPort` for the CAN
failure-prediction pipeline. LightGBM runs locally; LSTM and TCN are
delegated to :class:`TorchTimeSeriesAdapter`; PatchTST, Chronos, and
LNN (transformer / foundation-model / liquid architectures) are
delegated to their dedicated adapters; TimeGAN (unsupervised
generation) is delegated to :class:`TimeGANAdapter`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from ..passport_config import configured_lightgbm_root
from ..ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob, validate_model_config_for_family,
)
from .model_dispatch import (
    GENERATIVE_MODELS, TORCH_MODELS, ModelAdapterRegistry,
)
from .sklearn_lightgbm import load_array, train_lightgbm


class SklearnTimeSeriesAdapter:
    """LightGBM-backed time-series adapter with LSTM/TCN routing to torch."""

    def __init__(
        self, tracker: Any, checkpoint_store: Any = None,
        model_root: str | Path | None = None,
        lnn_model_root: str | Path | None = None,
        chronos_storage_root: str | Path | None = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        self._root = configured_lightgbm_root(model_root)
        self._models: dict[str, dict[str, Any]] = {}
        self._torch_adapter: Any = None
        self._timegan_adapter: Any = None
        # Dedicated per-model adapters (patchtst, chronos, lnn).
        self._model_registry = ModelAdapterRegistry(
            tracker=self._tracker, checkpoint_store=self._checkpoint_store,
            model_root=self._root, lnn_model_root=lnn_model_root,
            chronos_storage_root=chronos_storage_root,
        )

    @property
    def torch_adapter(self) -> Any:
        if self._torch_adapter is None:
            from .torch_timeseries import TorchTimeSeriesAdapter
            self._torch_adapter = TorchTimeSeriesAdapter(
                tracker=self._tracker, checkpoint_store=self._checkpoint_store,
                model_root=self._root,
            )
        return self._torch_adapter

    @property
    def timegan_adapter(self) -> Any:
        if self._timegan_adapter is None:
            from .timegan import TimeGANAdapter
            self._timegan_adapter = TimeGANAdapter(
                tracker=self._tracker, checkpoint_store=self._checkpoint_store,
            )
        return self._timegan_adapter

    def train(
        self,
        model_type: TimeSeriesModelType,
        X_uri: str,
        y_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        """Fit a classifier for the requested architecture and return a completed job."""
        validate_model_config_for_family(model_type, model_config)
        if model_type in GENERATIVE_MODELS:
            return self.timegan_adapter.train(
                X_uri, config=config, experiment_name=experiment_name,
            )
        if model_type in TORCH_MODELS:
            return self.torch_adapter.train(
                model_type, X_uri, y_uri, config=config, experiment_name=experiment_name,
                model_config=model_config,
            )
        if self._model_registry.has(model_type):
            return self._model_registry.get(model_type).train(
                model_type, X_uri, y_uri, config=config,
                experiment_name=experiment_name, model_config=model_config,
            )
        if model_type != TimeSeriesModelType.lightgbm:
            name = model_type.value if hasattr(model_type, "value") else model_type
            raise ValueError(f"Unknown model_type: {name}")
        cfg = config or TimeSeriesTrainingConfig()
        job, record = train_lightgbm(
            tracker=self._tracker, root=self._require_lightgbm_root(),
            x_uri=X_uri, y_uri=y_uri, config=cfg,
            experiment_name=experiment_name,
        )
        self._models[job.id] = record
        return job

    def predict(self, model_id: str, X_uri: str) -> str:
        """Run inference and persist predictions + scores to a .npz file."""
        record = self._models.get(model_id)
        if record is not None:
            return self._predict_sklearn(record, X_uri)
        try:
            return self.torch_adapter.predict(model_id, X_uri)
        except KeyError:
            pass
        # Fall through to dedicated transformer / liquid adapters.
        for adapter in self._model_registry.iter_adapters():
            try:
                return adapter.predict(model_id, X_uri)
            except KeyError:
                continue
        raise KeyError(f"Model not found: {model_id}")

    def _predict_sklearn(self, record: dict[str, Any], X_uri: str) -> str:
        from .mlflow_lightgbm import load_lightgbm_flavor, validated_probabilities
        model = load_lightgbm_flavor(record["model_path"])
        X = load_array(X_uri)
        probabilities = validated_probabilities(model, X)
        payload: dict[str, np.ndarray] = {
            "y_pred": np.argmax(probabilities, axis=1).astype(np.int64),
            "y_score": probabilities[:, 1],
        }
        pred_path = Path(record["model_path"]).parent / "predictions.npz"
        np.savez(pred_path, **payload)
        return f"file://{pred_path}"

    def _require_lightgbm_root(self) -> Path:
        if self._root is None:
            raise ValueError(
                "LightGBM deployable persistence requires model_root or "
                "ML_LIGHTGBM_MODEL_ROOT"
            )
        return self._root

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        rec = self._models.get(model_id)
        if rec is not None:
            return dict(rec)
        rec = self.torch_adapter.get_model(model_id)
        if rec is not None:
            return rec
        for adapter in self._model_registry.iter_adapters():
            rec = adapter.get_model(model_id)
            if rec is not None:
                return rec
        return None

    def list_models(self) -> list[dict[str, Any]]:
        local = [
            {"id": m["id"], "model_type": m["model_type"], "model_path": m["model_path"],
             "auroc": m["metrics"].get("auroc"), "created_at": m["created_at"]}
            for m in self._models.values()
        ]
        extras: list[dict[str, Any]] = list(self.torch_adapter.list_models())
        for adapter in self._model_registry.iter_adapters():
            extras.extend(adapter.list_models())
        return local + extras

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for model_id in model_ids:
            m = self._models.get(model_id)
            if m is None:
                m = self.torch_adapter.get_model(model_id)
            if m is None:
                for adapter in self._model_registry.iter_adapters():
                    m = adapter.get_model(model_id)
                    if m is not None:
                        break
            if m is None:
                continue
            rows.append({
                "id": model_id, "model_type": m["model_type"],
                metric: m["metrics"].get(metric),
            })
        rows.sort(key=lambda r: (r[metric] is None, -(r[metric] or 0.0)))
        return {
            "metric": metric, "models": rows,
            "best_model_id": rows[0]["id"] if rows else None,
            "count": len(rows),
        }
