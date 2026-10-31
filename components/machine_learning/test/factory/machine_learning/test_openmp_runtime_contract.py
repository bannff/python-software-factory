"""Darwin arm64 Torch-parent / LightGBM-child OpenMP ownership contract."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import platform
import sys

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
from factory.machine_learning.runtime.adapters.sklearn_timeseries import SklearnTimeSeriesAdapter
from factory.machine_learning.runtime.ports import TimeSeriesModelType

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or platform.machine() != "arm64",
    reason="Darwin arm64 OpenMP ownership contract",
)
_REPETITIONS = 5
_PRODUCTION_IMPORTS = (
    "factory.dataset.runtime.adapters.can_synthesize_hybrid_helpers",
    "factory.machine_learning.runtime.adapters._peft_training_loop",
    "factory.machine_learning.runtime.adapters.lnn_models",
    "factory.machine_learning.runtime.adapters.lnn_timespans",
    "factory.machine_learning.runtime.adapters.patchtst_models",
    "factory.machine_learning.runtime.adapters.timegan",
    "factory.machine_learning.runtime.adapters.timegan_conditional",
    "factory.machine_learning.runtime.adapters.transformer_training",
)


def _torch_backward() -> None:
    import torch
    value = torch.randn(64, 64, requires_grad=True)
    (value @ value).sum().backward()
    assert value.grad is not None


def test_torch_parent_then_repeated_subprocess_fit_persist_predict(tmp_path: Path) -> None:
    _torch_backward()
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules
    rng = np.random.default_rng(9)
    X = rng.normal(size=(80, 4)).astype(np.float32)
    y = (X[:, 0] > 0).astype(np.int64)
    x_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(x_path, X); np.save(y_path, y)
    adapter = SklearnTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )
    for _ in range(_REPETITIONS):
        job = adapter.train(TimeSeriesModelType.lightgbm, str(x_path), str(y_path))
        payload = np.load(adapter.predict(job.id, str(x_path)).removeprefix("file://"))
        assert payload["y_score"].shape == (len(X),)
        assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules


def test_production_imports_do_not_mutate_openmp_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    for module_name in _PRODUCTION_IMPORTS:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)
    assert "KMP_DUPLICATE_LIB_OK" not in os.environ
    assert "OMP_NUM_THREADS" not in os.environ
