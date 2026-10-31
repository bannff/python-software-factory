"""Legacy compatibility and durable transfer publication regressions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.native_lightgbm_process import (
    SubprocessNativeLightGBM,
)
from factory.machine_learning.runtime.adapters.transfer_learning import (
    TransferLearningManager,
)

from .lightgbm_passport_subprocess_support import create_legacy_joblib


def _data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(29)
    X = rng.normal(size=(500, 6)).astype(np.float32)
    y = (X[:, 0] + 0.4 * X[:, 1] > 0).astype(np.int64)
    return X[:400], y[:400], X[400:], y[400:]


@pytest.mark.parametrize("raw_booster", [True, False])
def test_prechange_joblib_registry_loads_and_scores_without_parent_native_imports(
    tmp_path: Path, raw_booster: bool,
) -> None:
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules
    X, y, X_val, _ = _data()
    artifact = tmp_path / "lightgbm_iter1.pkl"
    create_legacy_joblib(artifact, X, y, raw_booster=raw_booster)
    registry = {
        "models": {"lightgbm_iter1": {
            "model_type": "lightgbm", "path": str(artifact), "iteration": 1,
            "metrics": {"auroc": 0.9},
        }},
        "iterations": [],
    }
    (tmp_path / "model_registry.json").write_text(json.dumps(registry))

    manager = TransferLearningManager(tmp_path)
    loaded = manager.load_model("lightgbm_iter1")
    probabilities = loaded.predict_proba(X_val)
    best_id, best = manager.get_best_model("lightgbm") or (None, None)

    assert probabilities.shape == (len(X_val), 2)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
    assert best_id == "lightgbm_iter1" and best.predict(X_val).shape == (len(X_val),)
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules


def test_transfer_scratch_and_continuation_preserve_round_semantics(
    tmp_path: Path,
) -> None:
    X, y, X_val, y_val = _data()
    manager = TransferLearningManager(tmp_path)

    _, scratch = manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 1)
    _, continued = manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 2)

    first = (tmp_path / "lightgbm_iter1/mlflow-model/model.lgb").read_text()
    second = (tmp_path / "lightgbm_iter2/mlflow-model/model.lgb").read_text()
    assert scratch["iterations"] == 100 and first.count("Tree=") == 100
    assert continued["iterations"] == 150 and second.count("Tree=") == 150
    assert "[max_depth: -1]" in first and "[max_depth: -1]" in second
    assert "[max_depth: 6]" not in first and "[max_depth: 6]" not in second
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules


def test_registry_failure_after_model_publication_is_reconciled_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y, X_val, y_val = _data()
    manager = TransferLearningManager(tmp_path)

    def fail_registry(*_args, **_kwargs):
        raise OSError("injected registry fsync failure")

    monkeypatch.setattr(manager._store, "commit_model", fail_registry)
    with pytest.raises(OSError, match="injected registry"):
        manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 1)

    final = tmp_path / "lightgbm_iter1"
    assert final.is_dir() and not (tmp_path / ".lightgbm_iter1.staging").exists()
    assert manager.registry["models"] == {}

    monkeypatch.undo()
    recovered = TransferLearningManager(tmp_path)
    assert "lightgbm_iter1" in recovered.registry["models"]
    model, metrics = recovered.train_with_transfer(
        "lightgbm", X, y, X_val, y_val, 1,
    )
    assert metrics["iterations"] == 100
    assert model.predict_proba(X_val).shape == (len(X_val), 2)
    assert list(tmp_path.glob(".model_registry.*.tmp")) == []


class _CountingPort:
    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()
        self._delegate = SubprocessNativeLightGBM()

    def execute(self, request):
        with self._lock:
            self.calls += 1
        return self._delegate.execute(request)


def test_same_model_publication_is_serialized_and_replayed(tmp_path: Path) -> None:
    X, y, X_val, y_val = _data()
    port = _CountingPort()
    managers = [
        TransferLearningManager(tmp_path, native_port=port),
        TransferLearningManager(tmp_path, native_port=port),
    ]

    def train(manager):
        return manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(train, managers))

    assert port.calls == 1
    assert all(item[1]["iterations"] == 100 for item in results)
    registry = json.loads((tmp_path / "model_registry.json").read_text())
    assert list(registry["models"]) == ["lightgbm_iter1"]


def test_continuation_accepts_prechange_raw_booster_registry_entry(
    tmp_path: Path,
) -> None:
    X, y, X_val, y_val = _data()
    artifact = tmp_path / "lightgbm_iter1.pkl"
    create_legacy_joblib(artifact, X, y, raw_booster=True)
    registry = {
        "models": {"lightgbm_iter1": {
            "model_type": "lightgbm", "path": str(artifact), "iteration": 1,
            "metrics": {"auroc": 0.9},
        }}, "iterations": [],
    }
    (tmp_path / "model_registry.json").write_text(json.dumps(registry))

    manager = TransferLearningManager(tmp_path)
    _, metrics = manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 2)

    model_text = (tmp_path / "lightgbm_iter2/mlflow-model/model.lgb").read_text()
    assert metrics["iterations"] == 58 and model_text.count("Tree=") == 58
    assert metrics["transfer_from"] == "lightgbm_iter1"
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules


def test_divergent_retry_removes_orphan_before_new_explicit_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y, X_val, y_val = _data()
    port = _CountingPort()
    manager = TransferLearningManager(tmp_path, native_port=port)

    def fail_registry(*_args, **_kwargs):
        raise OSError("injected registry failure")

    monkeypatch.setattr(manager._store, "commit_model", fail_registry)
    with pytest.raises(OSError, match="injected registry"):
        manager.train_with_transfer("lightgbm", X, y, X_val, y_val, 1)
    monkeypatch.undo()

    changed = X.copy()
    changed[0, 0] += 1.0
    _, metrics = manager.train_with_transfer(
        "lightgbm", changed, y, X_val, y_val, 1,
    )

    assert port.calls == 2 and metrics["iterations"] == 100
    assert "lightgbm_iter1" in manager.registry["models"]
    assert not (tmp_path / ".lightgbm_iter1.staging").exists()
