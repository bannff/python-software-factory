"""C7 Canary — TimeSeriesTrainingPort creation and job lifecycle."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from factory.machine_learning.runtime.runtime import TrackingRuntime, reset_runtime
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelConfig,
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
)


class TestC7TimeSeriesTraining:
    """Verify time-series trainer can be obtained and jobs created."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_timeseries_training_creates_job(self) -> None:
        """C7 core canary: memory trainer creates a job with ID."""
        runtime = TrackingRuntime({"tracker": "memory", "finetuner": "memory"})
        trainer = runtime.get_timeseries_trainer("memory")
        job = trainer.train(
            TimeSeriesModelType.lightgbm,
            X_uri="file:///tmp/X.npy",
            y_uri="file:///tmp/y.npy",
        )
        assert job.id
        # Memory adapter completes synchronously — status is "completed"
        assert job.status == "completed"

    def test_trainer_returns_port_protocol(self) -> None:
        """get_timeseries_trainer must return a TimeSeriesTrainingPort."""
        runtime = TrackingRuntime()
        trainer = runtime.get_timeseries_trainer("memory")
        assert hasattr(trainer, "train")
        assert hasattr(trainer, "predict")
        assert hasattr(trainer, "list_models")

    def test_trainer_caches_instances(self) -> None:
        """Same backend should return the same trainer instance."""
        runtime = TrackingRuntime()
        t1 = runtime.get_timeseries_trainer("memory")
        t2 = runtime.get_timeseries_trainer("memory")
        assert t1 is t2

    def test_train_with_custom_config(self) -> None:
        """Training with explicit config should populate the job."""
        runtime = TrackingRuntime()
        trainer = runtime.get_timeseries_trainer("memory")
        config = TimeSeriesTrainingConfig(epochs=10, learning_rate=0.01)
        job = trainer.train(
            TimeSeriesModelType.lstm,
            X_uri="file:///tmp/X.npy",
            y_uri="file:///tmp/y.npy",
            config=config,
        )
        assert job.config.epochs == 10
        assert job.metrics  # should have synthetic metrics

    def test_list_models_after_training(self) -> None:
        """list_models should return the trained model."""
        runtime = TrackingRuntime()
        trainer = runtime.get_timeseries_trainer("memory")
        trainer.train(
            TimeSeriesModelType.tcn,
            X_uri="file:///tmp/X.npy",
            y_uri="file:///tmp/y.npy",
        )
        models = trainer.list_models()
        assert len(models) == 1
        assert models[0]["model_type"] == "tcn"

    @pytest.mark.parametrize(
        "model_type",
        [
            TimeSeriesModelType.lightgbm, TimeSeriesModelType.lstm,
            TimeSeriesModelType.tcn, TimeSeriesModelType.patchtst,
            TimeSeriesModelType.timegan,
        ],
    )
    def test_prior_families_preserve_none_and_reject_non_null_config(
        self, model_type: TimeSeriesModelType,
    ) -> None:
        trainer = TrackingRuntime().get_timeseries_trainer("memory")
        job = trainer.train(model_type, "file:///X.npy", "file:///y.npy", model_config=None)
        assert job.status == "completed"
        with pytest.raises(ValueError, match="model_config is not supported"):
            trainer.train(
                model_type, "file:///X.npy", "file:///y.npy",
                model_config=TimeSeriesModelConfig(),
            )

    def test_all_training_port_adapters_accept_model_config(self) -> None:
        """Every concrete/composite classifier adapter matches the additive port slot."""
        adapter_dir = Path(__file__).parents[3] / "src/factory/machine_learning/runtime/adapters"
        names = (
            "chronos_timeseries.py", "lnn_timeseries.py", "mlx_timeseries.py",
            "patchtst_timeseries.py", "sklearn_timeseries.py",
            "timeseries_training.py", "torch_timeseries.py",
        )
        for name in names:
            tree = ast.parse((adapter_dir / name).read_text())
            methods = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "train"
            ]
            assert len(methods) == 1, name
            assert "model_config" in {arg.arg for arg in methods[0].args.args}, name

    def test_unknown_backend_raises(self) -> None:
        """Unknown time-series backend should raise ValueError."""
        runtime = TrackingRuntime()
        with pytest.raises(ValueError, match="Unknown time-series backend"):
            runtime.get_timeseries_trainer("nonexistent")

    def test_unknown_backend_raises_safe_diagnostic(self) -> None:
        """create_timeseries_trainer must raise SafeDiagnostic (not a bare
        ValueError) so the MCP boundary logs the specific diagnostic instead
        of collapsing it into tool_execution_failed. resolve_timeseries_backend
        rejects the unknown name before create_timeseries_trainer is reached,
        so the env-var fallback path is exercised, not regressed."""
        runtime = TrackingRuntime()
        with pytest.raises(SafeDiagnostic) as exc_info:
            runtime.get_timeseries_trainer("nonexistent")
        assert "Unknown time-series backend: nonexistent" in str(exc_info.value)
