"""Persisted transfer-learning manager with isolated LightGBM execution."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..durable_files import read_regular
from ..native_lightgbm_contracts import FitPayload, FitRequest, FitResult
from ..native_lightgbm_port import NativeLightGBMPort
from ..passport_tree_seal import remove_staging_tree
from ..transfer_registry import TransferRegistry
from .mlflow_lightgbm import (
    load_legacy_joblib, load_lightgbm_flavor, validate_lightgbm_flavor,
)
from .native_lightgbm_process import SubprocessNativeLightGBM
from .transfer_sklearn import train_sklearn_transfer


class TransferLearningManager:
    """Manage compounding models without loading native LightGBM in the parent."""

    def __init__(
        self, base_dir: Path, native_port: NativeLightGBMPort | None = None,
    ) -> None:
        self.base_dir = base_dir.expanduser().absolute()
        self._store = TransferRegistry(self.base_dir)
        self.registry_path = self._store.path
        self.registry = self._store.reconcile_all()
        self._native = native_port or SubprocessNativeLightGBM()

    def save_model(
        self, model_type: str, model: Any, metrics: dict, iteration: int,
    ) -> str:
        """Persist a non-LightGBM sklearn model for later iterations."""
        if model_type == "lightgbm":
            raise ValueError("LightGBM persistence is owned by the native child")
        model_id = f"{model_type}_iter{iteration}"
        model_path = self.base_dir / f"{model_id}.pkl"
        joblib.dump(model, model_path)
        self._register(model_id, model_type, model_path, metrics, iteration)
        return model_id

    def load_model(self, model_id: str) -> Any:
        self.registry = self._store.load()
        if model_id not in self.registry["models"]:
            raise KeyError(f"Model {model_id} not found")
        entry = self.registry["models"][model_id]
        path = Path(entry["path"])
        if entry["model_type"] == "lightgbm":
            if path.suffix == ".pkl":
                return load_legacy_joblib(read_regular(path), threshold=0.5)
            return load_lightgbm_flavor(path)
        return joblib.load(path)

    def get_best_model(self, model_type: str) -> tuple[str, Any] | None:
        self.registry = self._store.load()
        candidates = [
            (key, value) for key, value in self.registry["models"].items()
            if value["model_type"] == model_type
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda item: item[1]["metrics"].get("auroc", 0))
        return best[0], self.load_model(best[0])

    def train_with_transfer(
        self, model_type: str, X_train: np.ndarray, y_train: np.ndarray,
        X_val: np.ndarray, y_val: np.ndarray, iteration: int,
    ) -> tuple[Any, dict]:
        if model_type == "lightgbm":
            return self._train_lgbm_transfer(
                X_train, y_train, X_val, y_val, iteration,
            )
        if model_type in {"random_forest", "grad_boost"}:
            return train_sklearn_transfer(
                model_type, X_train, y_train, X_val, y_val, iteration,
                self.save_model,
            )
        raise ValueError(f"Unknown model type: {model_type}")

    def _train_lgbm_transfer(
        self, X_train, y_train, X_val, y_val, iteration,
    ) -> tuple[Any, dict]:
        from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

        model_id = f"lightgbm_iter{iteration}"
        with self._store.model_lock(model_id):
            self.registry = self._store.load()
            prior = self._best_entry("lightgbm", exclude=model_id)
            intent = _intent_digest(iteration, prior, X_train, y_train, X_val, y_val)
            existing = self._store.reconcile(model_id, expected_intent=intent)
            if existing is not None:
                self.registry = self._store.load()
                return self.load_model(model_id), dict(existing["metrics"])
            final = self.base_dir / model_id
            staging = self.base_dir / f".{model_id}.staging"
            remove_staging_tree(staging); staging.mkdir(mode=0o700)
            rounds = 50 if prior else 100
            try:
                result = self._fit_native(
                    staging, prior, rounds, X_train, y_train, X_val, y_val,
                )
                probabilities = np.asarray(result.probabilities)
                predicted = np.argmax(probabilities, axis=1)
                metrics = {
                    "auroc": float(roc_auc_score(y_val, probabilities[:, 1])),
                    "accuracy": float(accuracy_score(y_val, predicted)),
                    "f1": float(f1_score(y_val, predicted)),
                    "transfer_from": prior["id"] if prior else "scratch",
                    "iterations": result.iterations,
                }
                staged_path = staging / "mlflow-model"
                validate_lightgbm_flavor(staged_path)
                model = load_lightgbm_flavor(staged_path)
                entry = self._entry(
                    "lightgbm", final / "mlflow-model", metrics, iteration,
                )
                self._store.publish(
                    model_id, staging, final, entry, intent, rounds, result.iterations,
                )
                updated = self._store.commit_model(model_id, entry)
            except BaseException:
                remove_staging_tree(staging)
                raise
            self.registry = updated
            return model, metrics

    def _fit_native(self, staging, prior, rounds, X, y, X_val, y_val) -> FitResult:
        with tempfile.TemporaryDirectory(prefix="ml-transfer-input-") as directory:
            inputs = Path(directory); os.chmod(inputs, 0o700)
            paths = []
            for name, value in (
                ("X.npy", X), ("y.npy", y),
                ("X_val.npy", X_val), ("y_val.npy", y_val),
            ):
                path = inputs / name
                np.save(path, value, allow_pickle=False); paths.append(path)
            result = self._native.execute(FitRequest(
                operation="fit_predict_persist",
                payload=FitPayload(
                    x_uri=str(paths[0]), y_uri=str(paths[1]),
                    validation_x_uri=str(paths[2]), validation_y_uri=str(paths[3]),
                    destination=str(staging / "mlflow-model"),
                    init_model=prior["path"] if prior else None,
                    validation_split=0.2, seed=42, training_mode="transfer",
                    rounds=rounds,
                ),
            ))
        if not isinstance(result, FitResult):
            raise ValueError("native_process_protocol_error: fit result kind")
        return result

    def _best_entry(self, kind: str, exclude: str = "") -> dict | None:
        values = [
            {"id": key, **value} for key, value in self.registry["models"].items()
            if value["model_type"] == kind and key != exclude
        ]
        return max(values, key=lambda item: item["metrics"].get("auroc", 0)) if values else None

    @staticmethod
    def _entry(kind, path, metrics, iteration) -> dict[str, Any]:
        return {
            "model_type": kind, "path": str(path), "iteration": iteration,
            "metrics": metrics,
        }

    def _register(self, model_id, kind, path, metrics, iteration) -> None:
        entry = self._entry(kind, path, metrics, iteration)
        self.registry = self._store.commit_model(model_id, entry)

    def get_iteration_summary(self) -> list[dict]:
        self.registry = self._store.load()
        return self.registry.get("iterations", [])

    def record_iteration(self, iteration: int, results: dict) -> None:
        self.registry = self._store.append_iteration({"iteration": iteration, **results})


def _intent_digest(iteration, prior, *arrays) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps({
        "iteration": iteration,
        "prior": None if prior is None else {"id": prior["id"], "path": prior["path"]},
    }, sort_keys=True, separators=(",", ":")).encode())
    for value in arrays:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode())
        digest.update(json.dumps(array.shape).encode())
        digest.update(array.view(np.uint8))
    return digest.hexdigest()
