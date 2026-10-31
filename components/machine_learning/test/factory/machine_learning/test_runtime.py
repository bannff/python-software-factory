"""Tests for machine_learning runtime."""

import pytest

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from factory.machine_learning.runtime.finetuning_factory import create_finetuner
from factory.machine_learning.runtime.runtime import (
    TrackingRuntime,
    get_runtime,
    reset_runtime,
)


class TestTrackingRuntime:
    """Tests for TrackingRuntime factory."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_available_backends(self) -> None:
        """Should list available backends."""
        backends = TrackingRuntime.available_backends()
        assert "memory" in backends
        assert "mlflow" in backends

    def test_get_runtime_singleton(self) -> None:
        """Should return same runtime instance."""
        r1 = get_runtime()
        r2 = get_runtime()
        assert r1 is r2

    def test_reset_runtime(self) -> None:
        """Should reset runtime instance."""
        r1 = get_runtime()
        reset_runtime()
        r2 = get_runtime()
        assert r1 is not r2

    def test_unknown_backend_raises(self) -> None:
        """Should raise for unknown backend."""
        runtime = TrackingRuntime()
        with pytest.raises(ValueError, match="Unknown tracker backend"):
            runtime.get_tracker("unknown")

    def test_unknown_tracker_backend_raises_safe_diagnostic(self) -> None:
        """Should raise SafeDiagnostic (not a bare ValueError) with the
        specific diagnostic message preserved, so the MCP boundary can log
        it verbatim instead of collapsing it into tool_execution_failed."""
        runtime = TrackingRuntime()
        with pytest.raises(SafeDiagnostic) as exc_info:
            runtime.get_tracker("bogus")
        assert "Unknown tracker backend: bogus" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_unknown_finetuning_backend_raises_safe_diagnostic(self) -> None:
        """create_finetuner must raise SafeDiagnostic for an unknown backend,
        preserving the diagnostic instead of collapsing to a bare failure."""
        runtime = TrackingRuntime()
        with pytest.raises(SafeDiagnostic) as exc_info:
            create_finetuner("bogus", runtime.get_checkpoint_store(), {})
        assert "Unknown finetuning backend: bogus" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_get_tracker_memory(self) -> None:
        """Should create memory tracker."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")
        assert tracker is not None

    def test_env_resolved_backend_mlflow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ML_TRACKER_BACKEND=mlflow must drive get_tracker() default
        resolution (production path — MCP tools pass no backend arg)."""
        monkeypatch.setenv("ML_TRACKER_BACKEND", "mlflow")
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:////tmp/issue80-test.db")
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker()
        assert type(tracker).__name__ == "MLflowTracker"

    def test_health_check_empty(self) -> None:
        """Should return empty health when no trackers active."""
        runtime = TrackingRuntime()
        health = runtime.health_check()
        assert health == {}


class TestMemoryTracker:
    """Tests for memory tracker adapter."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_create_and_get_experiment(self) -> None:
        """Should create and retrieve experiment."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        exp = tracker.create_experiment("test-exp", "A test experiment")
        assert exp.name == "test-exp"

        result = tracker.get_experiment(exp.id)
        assert result is not None
        assert result.name == "test-exp"

    def test_get_experiment_by_name(self) -> None:
        """Should get experiment by name."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        tracker.create_experiment("my-experiment")
        result = tracker.get_experiment_by_name("my-experiment")
        assert result is not None
        assert result.name == "my-experiment"

    def test_list_experiments(self) -> None:
        """Should list all experiments."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        tracker.create_experiment("exp1")
        tracker.create_experiment("exp2")

        exps = tracker.list_experiments()
        assert len(exps) == 2

    def test_start_and_end_run(self) -> None:
        """Should start and end run."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        exp = tracker.create_experiment("test-exp")
        run = tracker.start_run(exp.id, "test-run")

        assert run.experiment_id == exp.id
        assert run.status == "running"

        ended = tracker.end_run(run.id)
        assert ended.status == "completed"
        assert ended.ended_at is not None

    def test_log_params(self) -> None:
        """Should log parameters to run."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        exp = tracker.create_experiment("test-exp")
        run = tracker.start_run(exp.id)

        tracker.log_params(run.id, {"lr": 0.01, "batch_size": 32})

        result = tracker.get_run(run.id)
        assert result.params["lr"] == 0.01
        assert result.params["batch_size"] == 32

    def test_log_metrics(self) -> None:
        """Should log metrics to run."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        exp = tracker.create_experiment("test-exp")
        run = tracker.start_run(exp.id)

        tracker.log_metrics(run.id, {"accuracy": 0.95, "loss": 0.05})

        result = tracker.get_run(run.id)
        assert result.metrics["accuracy"] == 0.95
        assert result.metrics["loss"] == 0.05

    def test_log_artifact(self) -> None:
        """Should log artifact to run."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        exp = tracker.create_experiment("test-exp")
        run = tracker.start_run(exp.id)

        tracker.log_artifact(run.id, "/path/to/model.pkl")

        result = tracker.get_run(run.id)
        assert "/path/to/model.pkl" in result.artifacts

    def test_register_and_get_dataset(self) -> None:
        """Should register and retrieve dataset."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        dataset = tracker.register_dataset(
            name="training-data",
            version="1.0.0",
            path="/data/train.csv",
            metadata={"rows": 10000},
        )

        assert dataset.name == "training-data"
        assert dataset.version == "1.0.0"

        result = tracker.get_dataset("training-data", "1.0.0")
        assert result is not None
        assert result.path == "/data/train.csv"

    def test_get_latest_dataset_version(self) -> None:
        """Should get latest dataset version when version not specified."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")

        tracker.register_dataset("data", "1.0.0", "/v1")
        tracker.register_dataset("data", "2.0.0", "/v2")

        result = tracker.get_dataset("data")
        assert result is not None
        assert result.version == "2.0.0"

    def test_health_check(self) -> None:
        """Should return healthy status."""
        runtime = TrackingRuntime()
        tracker = runtime.get_tracker("memory")
        health = tracker.health_check()
        assert health.healthy is True
        assert health.backend == "memory"
