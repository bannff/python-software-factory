"""Sklearn time-series adapter — training, inference, and registry tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("joblib", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker  # noqa: E402
from factory.machine_learning.runtime.adapters.sklearn_timeseries import (  # noqa: E402
    SklearnTimeSeriesAdapter,
)
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
)


@pytest.fixture
def adapter(tmp_path: Path) -> SklearnTimeSeriesAdapter:
    return SklearnTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )


@pytest.fixture
def synthetic_data(tmp_path: Path) -> tuple[str, str, np.ndarray, np.ndarray]:
    """Build a learnable binary task and persist as .npy files."""
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 10)).astype(np.float32)
    # Signal lives in feature 0 so LightGBM can fit it.
    y = (X[:, 0] > 0).astype(int)
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(X_path, X)
    np.save(y_path, y)
    return str(X_path), str(y_path), X, y


def _make_3d_fixture(tmp_path: Path, X: np.ndarray, y: np.ndarray) -> tuple[str, str]:
    """Reshape the 2D fixture into a 3D windowed form for the torch adapter."""
    n_samples, n_features = X.shape
    window_size = 5
    X3 = X.reshape(n_samples // window_size, window_size, n_features).astype(np.float32)
    y3 = y[: n_samples // window_size].astype(np.int64)
    X3_path, y3_path = tmp_path / "X3.npy", tmp_path / "y3.npy"
    np.save(X3_path, X3)
    np.save(y3_path, y3)
    return str(X3_path), str(y3_path)


class TestSklearnTimeSeriesAdapter:
    """Verify the LightGBM adapter end-to-end on synthetic CAN-shaped data."""

    def test_train_completes_with_metrics(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """LightGBM training yields a completed job and on-disk model file."""
        X_uri, y_uri, _, _ = synthetic_data
        job = adapter.train(
            TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri,
            experiment_name="can-failure-test",
        )
        assert job.status == "completed"
        assert {"accuracy", "precision", "recall", "f1", "auroc"} <= set(job.metrics)
        assert job.model_path and Path(job.model_path).exists()
        # Synthetic data is learnable — AUROC should be well above random.
        assert job.metrics["auroc"] > 0.6

    def test_train_with_scale_pos_weight_completes(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """Passing extra={'scale_pos_weight': 5.0} trains successfully and is forwarded."""
        X_uri, y_uri, _, _ = synthetic_data
        job = adapter.train(
            TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri,
            config=TimeSeriesTrainingConfig(extra={"scale_pos_weight": 5.0}),
        )
        assert job.status == "completed"
        model_text = Path(job.model_path, "model.lgb").read_text()
        assert "[scale_pos_weight: 5]" in model_text

    def test_train_without_extra_uses_neutral_weight(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """Default training persists the neutral Booster weighting and binary objective."""
        X_uri, y_uri, _, _ = synthetic_data
        job = adapter.train(TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri)
        model_text = Path(job.model_path, "model.lgb").read_text()
        assert "[scale_pos_weight: 1]" in model_text
        assert "[objective: binary]" in model_text

    def test_model_config_none_preserves_dispatch_and_non_null_rejects(
        self, adapter: SklearnTimeSeriesAdapter, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expected = TimeSeriesTrainingJob(
            id="job", model_type=TimeSeriesModelType.lightgbm, status="completed",
        )
        monkeypatch.setattr(
            "factory.machine_learning.runtime.adapters.sklearn_timeseries.train_lightgbm",
            lambda **_kwargs: (expected, {"id": "job"}),
        )
        assert adapter.train(
            TimeSeriesModelType.lightgbm, "unused-X", "unused-y", model_config=None,
        ) is expected
        with pytest.raises(ValueError, match="model_config is not supported"):
            adapter.train(
                TimeSeriesModelType.lightgbm, "unused-X", "unused-y",
                model_config=TimeSeriesModelConfig(),
            )

    def test_predict_returns_file_uri(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """predict returns a file:// URI pointing to a .npz of predictions."""
        X_uri, y_uri, X, _ = synthetic_data
        job = adapter.train(TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri)
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        assert payload["y_pred"].shape == (X.shape[0],)
        assert payload["y_score"].shape == (X.shape[0],)

    def test_list_models_after_training(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """list_models should return one summary per trained model."""
        X_uri, y_uri, _, _ = synthetic_data
        adapter.train(TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri)
        adapter.train(TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri)
        models = adapter.list_models()
        assert len(models) == 2
        assert all(m["model_type"] == "lightgbm" for m in models)
        assert all("auroc" in m for m in models)

    def test_compare_two_models_picks_best(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple, tmp_path: Path,
    ) -> None:
        """compare_models ranks models on the chosen metric and picks the best."""
        X_uri, y_uri, X, y = synthetic_data
        j_easy = adapter.train(TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=y_uri)
        rng = np.random.default_rng(7)
        y_noisy = rng.integers(0, 2, size=len(y))
        noisy_path = tmp_path / "y_noisy.npy"
        np.save(noisy_path, y_noisy)
        j_noisy = adapter.train(
            TimeSeriesModelType.lightgbm, X_uri=X_uri, y_uri=str(noisy_path),
        )
        result = adapter.compare_models([j_easy.id, j_noisy.id], metric="auroc")
        assert result["count"] == 2
        assert result["best_model_id"] == j_easy.id
        assert result["models"][0]["id"] == j_easy.id
        assert result["models"][0]["auroc"] >= result["models"][1]["auroc"]

    def test_unknown_model_type_raises(
        self, adapter: SklearnTimeSeriesAdapter, synthetic_data: tuple,
    ) -> None:
        """Unknown model types must raise ValueError — PatchTST/Chronos/LNN
        are now implemented and routed to dedicated adapters."""
        X_uri, y_uri, _, _ = synthetic_data
        # PatchTST is now supported; we use a truly unknown string instead.
        with pytest.raises(ValueError):
            adapter.train("not_a_real_model", X_uri=X_uri, y_uri=y_uri)  # type: ignore[arg-type]

    @pytest.mark.parametrize("model_type", [TimeSeriesModelType.lstm, TimeSeriesModelType.tcn])
    def test_deep_models_route_to_torch(
        self, tmp_path: Path, synthetic_data: tuple, model_type: TimeSeriesModelType,
    ) -> None:
        """LSTM and TCN must succeed (delegated to the torch adapter) on 3D data."""
        _, _, X, y = synthetic_data
        X3_uri, y3_uri = _make_3d_fixture(tmp_path, X, y)
        adapter = SklearnTimeSeriesAdapter(
            tracker=MemoryTracker(), model_root=tmp_path / "models",
        )
        job = adapter.train(
            model_type, X_uri=X3_uri, y_uri=y3_uri,
            config=TimeSeriesTrainingConfig(
                window_size=5, batch_size=8, epochs=2, early_stopping_patience=1,
            ),
        )
        assert job.status == "completed"
        assert job.model_type == model_type
        # The model id must be discoverable through the sklearn facade.
        assert adapter.get_model(job.id) is not None
        assert any(m["model_type"] == model_type.value for m in adapter.list_models())

    def test_predict_unknown_model_raises(
        self, adapter: SklearnTimeSeriesAdapter,
    ) -> None:
        with pytest.raises(KeyError):
            adapter.predict("nonexistent-id", "file:///tmp/X.npy")
