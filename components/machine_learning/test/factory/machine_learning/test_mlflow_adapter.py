"""Tests for MLflow tracker adapter — mlflow module is fully mocked.

No running MLflow server or installed `mlflow` package is required.
Follows the same behavioural surface as ``TestMemoryTracker`` in
``test_runtime.py`` but uses ``unittest.mock.patch`` to inject a
synthetic mlflow module.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from factory.machine_learning.runtime.adapters.mlflow_adapter import MLflowTracker


def _build_run_mock() -> MagicMock:
    """Build a mock mlflow.entities.Run (same shape for module and client)."""
    run = MagicMock(name="mlflow.entities.Run")
    run.info.run_id = "run-1"
    run.info.experiment_id = "exp-1"
    run.info.run_name = "test-run"
    run.info.status = "FINISHED"
    run.data.params = {}
    run.data.metrics = {}
    run.data.tags = {}
    return run


def _build_client_mock() -> MagicMock:
    """Build a mock MlflowClient instance (real client signatures)."""
    client = MagicMock(name="MlflowClient instance")
    exp = MagicMock(name="mlflow.entities.Experiment")
    exp.experiment_id = "exp-1"
    exp.name = "test-exp"
    exp.tags = {"env": "test"}
    run = _build_run_mock()
    client.create_experiment.return_value = "42"
    client.get_experiment.return_value = exp
    client.get_experiment_by_name.return_value = exp
    client.search_experiments.return_value = [exp]
    client.get_run.return_value = run
    client.create_run.return_value = run
    client.search_runs.return_value = [run]
    return client


def _build_mlflow_mock() -> MagicMock:
    """Build a MagicMock that imitates the subset of mlflow we use.

    The adapter routes everything through MlflowClient: fluent
    start_run/create_experiment would honor the global tracking uri rather
    than the adapter's tracking_uri, and fluent end_run/log_param cannot
    target a run by id (real mlflow 3.16.1 behavior).
    """
    mock = MagicMock(name="mlflow")
    mock.MlflowClient.return_value = _build_client_mock()
    return mock


@pytest.fixture
def mlflow_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Inject a mock mlflow module into sys.modules and return it."""
    mock = _build_mlflow_mock()
    monkeypatch.setitem(sys.modules, "mlflow", mock)
    return mock


class TestMLflowTracker:
    """Tests for the MLflow adapter with mlflow fully mocked."""

    def test_create_experiment(self, mlflow_mock: MagicMock) -> None:
        """create_experiment should return an Experiment with id and name."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        exp = tracker.create_experiment("my-exp", description="d", tags={"a": "b"})

        assert exp.id == "42"
        assert exp.name == "my-exp"
        assert exp.description == "d"
        assert exp.tags == {"a": "b"}
        client.create_experiment.assert_called_once_with("my-exp", tags={"a": "b"})

    def test_get_experiment(self, mlflow_mock: MagicMock) -> None:
        """get_experiment should return Experiment when found, None otherwise."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        exp = tracker.get_experiment("exp-1")
        assert exp is not None
        assert exp.id == "exp-1"
        assert exp.name == "test-exp"
        client.get_experiment.assert_called_once_with("exp-1")

        # get_experiment() returns None when the client raises (not found)
        client.get_experiment.side_effect = Exception("not found")
        assert tracker.get_experiment("missing") is None

    def test_list_experiments(self, mlflow_mock: MagicMock) -> None:
        """list_experiments should return list of Experiment objects."""
        tracker = MLflowTracker()

        exps = tracker.list_experiments()

        assert len(exps) == 1
        assert exps[0].id == "exp-1"
        assert exps[0].name == "test-exp"
        mlflow_mock.MlflowClient.return_value.search_experiments.assert_called_once()

    def test_start_run(self, mlflow_mock: MagicMock) -> None:
        """start_run should call client.create_run and return a Run."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value
        client.create_run.return_value.info.run_id = "new-run-id"

        run = tracker.start_run("exp-1", "my-run", tags={"t": "v"})

        assert run.id == "new-run-id"
        assert run.experiment_id == "exp-1"
        assert run.name == "my-run"
        assert run.status == "running"
        assert run.tags == {"t": "v"}
        client.create_run.assert_called_once_with(
            "exp-1", run_name="my-run", tags={"t": "v"}
        )

    def test_end_run(self, mlflow_mock: MagicMock) -> None:
        """end_run must terminate the specific run via MlflowClient."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.end_run("run-1", status="completed")

        # Real mlflow 3.16.1: fluent end_run takes no run_id; the client's
        # set_terminated is the only way to target a specific run.
        client.set_terminated.assert_called_once_with("run-1", status="FINISHED")

    def test_end_run_failed(self, mlflow_mock: MagicMock) -> None:
        """end_run maps any non-completed status to FAILED."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.end_run("run-1", status="failed")

        client.set_terminated.assert_called_with("run-1", status="FAILED")

    def test_get_run(self, mlflow_mock: MagicMock) -> None:
        """get_run should read through MlflowClient."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        run = tracker.get_run("run-1")

        assert run is not None
        assert run.id == "run-1"
        assert run.status == "completed"
        client.get_run.assert_called_once_with("run-1")

    def test_log_param(self, mlflow_mock: MagicMock) -> None:
        """log_param must call client.log_param(run_id, key, value)."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.log_param("run-1", "lr", 0.01)

        client.log_param.assert_called_once_with("run-1", "lr", 0.01)

    def test_log_params(self, mlflow_mock: MagicMock) -> None:
        """log_params must call client.log_param per param."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.log_params("run-1", {"lr": 0.01, "bs": 32})

        assert client.log_param.call_count == 2
        client.log_param.assert_any_call("run-1", "lr", 0.01)
        client.log_param.assert_any_call("run-1", "bs", 32)

    def test_log_metric(self, mlflow_mock: MagicMock) -> None:
        """log_metric must call client.log_metric(run_id, key, value, step=)."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.log_metric("run-1", "loss", 0.5, step=10)

        client.log_metric.assert_called_once_with("run-1", "loss", 0.5, step=10)

    def test_log_metrics(self, mlflow_mock: MagicMock) -> None:
        """log_metrics must call client.log_metric per metric."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        tracker.log_metrics("run-1", {"a": 0.1, "b": 0.2}, step=5)

        assert client.log_metric.call_count == 2
        client.log_metric.assert_any_call("run-1", "a", 0.1, step=5)
        client.log_metric.assert_any_call("run-1", "b", 0.2, step=5)

    def test_list_runs(self, mlflow_mock: MagicMock) -> None:
        """list_runs should search via client, scoped to experiment when given."""
        tracker = MLflowTracker()
        client = mlflow_mock.MlflowClient.return_value

        runs = tracker.list_runs("exp-1")

        assert len(runs) == 1
        assert runs[0].id == "run-1"
        assert runs[0].status == "completed"
        client.search_runs.assert_called_once_with(experiment_ids=["exp-1"])

    def test_health_check(self, mlflow_mock: MagicMock) -> None:
        """health_check should report healthy when mlflow is importable."""
        tracker = MLflowTracker()

        health = tracker.health_check()

        assert health.healthy is True
        assert health.backend == "mlflow"
        assert health.latency_ms >= 0

    def test_health_check_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """health_check should report unhealthy when mlflow import fails."""
        # Setting sys.modules[name] = None causes import to raise ImportError,
        # matching the real-world "mlflow not installed" case.
        monkeypatch.setitem(sys.modules, "mlflow", None)

        tracker = MLflowTracker()
        health = tracker.health_check()

        assert health.healthy is False
        assert health.backend == "mlflow"
        assert health.message  # error message is populated


class TestMLflowTrackerRealIntegration:
    """Real end-to-end test against a sqlite-backed mlflow (no mocks)."""

    def test_end_to_end_sqlite(self, tmp_path):  # type: ignore[no-untyped-def]
        """Full lifecycle against real mlflow + sqlite tracking store."""
        mlflow = pytest.importorskip("mlflow")

        tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
        tracker = MLflowTracker(tracking_uri=tracking_uri)

        exp = tracker.create_experiment("e2e-exp", tags={"env": "test"})
        run = tracker.start_run(exp.id, "e2e-run", tags={"phase": "smoke"})

        tracker.log_params(run.id, {"lr": 0.01, "epochs": 3})
        tracker.log_metrics(run.id, {"loss": 0.42, "acc": 0.91}, step=1)

        ended = tracker.end_run(run.id, status="completed")

        assert ended is not None
        assert ended.status == "completed"

        # Readback through a fresh tracker against the same store.
        readback = tracker.get_run(run.id)
        assert readback is not None
        assert readback.status == "completed"
        assert readback.params == {"lr": "0.01", "epochs": "3"}
        assert readback.metrics["loss"] == 0.42
        assert readback.metrics["acc"] == 0.91

        runs = tracker.list_runs(exp.id)
        assert [r.id for r in runs] == [run.id]
        assert runs[0].status == "completed"

        # Sanity: the fluent module's tracking uri was never mutated globally.
        assert mlflow.get_tracking_uri() != tracking_uri
