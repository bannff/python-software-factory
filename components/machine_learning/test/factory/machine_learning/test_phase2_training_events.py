"""Phase 2 (issue #80) wiring tests: events on training paths + receipts.

Covers:
- ml.training.started/completed/failed emission on the timeseries MCP tools
  (ml_train_timeseries, ml_continue_timeseries), with emit-then-reraise on
  backend failure (typed_boundary converts after tool exit — never swallowed).
- ml.training.* emission at the CAN lifecycle coordinator chokepoint with
  replay suppression (idempotent retries emit nothing).
- Best-effort cockpit receipts for CAN lifecycle TRAIN terminals
  (composition gap: lifecycle runs reached MLflow but not ml_training_runs).
- Receipt ↔ MLflow link: persist_training_run on a job whose run_id came
  from a REAL sqlite-backed MLflow tracker carries tracker_run_id.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from factory.machine_learning.interface import TrackingRuntime, create_server
from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.adapters.mlflow_adapter import MLflowTracker
from factory.machine_learning.runtime.can_lifecycle_composition import (
    CanLifecycleOperations,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import (
    CanLifecycleCoordinator,
)
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
)
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.operational import DocInsertOutput


class EventRecorder:
    """Fake tool_invoker capturing events_publish + storage_doc_insert."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.docs: dict[str, dict] = {}

    def __call__(self, tool_name: str, **kwargs):
        if tool_name == "events_publish":
            self.events.append((kwargs["event_type"], kwargs["payload"]))
            return {"published": True}
        if tool_name == "storage_doc_insert":
            key = f"{kwargs['collection']}:{kwargs['doc_id']}"
            self.docs[key] = {"id": kwargs["doc_id"], "data": kwargs["data"]}
            return {"inserted": True}
        raise AssertionError(f"unexpected tool: {tool_name}")

    def of_type(self, event_type: str) -> list[dict]:
        return [p for name, p in self.events if name == event_type]


@pytest.fixture
def recorder():
    fake = EventRecorder()
    with patch(
        "factory.mcp_utils.registry._services", {"tool_invoker": fake},
    ):
        yield fake


def _tool(name: str):
    return asyncio.run(create_server(TrackingRuntime()).get_tool(name)).fn


class _Result(BaseModel):
    """Minimal CanTrainResult-shaped result model for coordinator tests."""
    can_ids: list[str] = []
    portfolio: list[dict] = []
    evaluation_record_request: dict = {}


class _StubTrainer:
    """Timeseries trainer stub: succeeds, or explodes on demand."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def train(self, **_kwargs) -> TimeSeriesTrainingJob:
        if self._error is not None:
            raise self._error
        return TimeSeriesTrainingJob(
            id="stub-job-1", model_type=TimeSeriesModelType.lightgbm,
            status="completed", run_id="stub-run-1",
            config=TimeSeriesTrainingConfig(), metrics={"auroc": 0.8},
        )


def _runtime_with_trainer(error: Exception | None = None) -> TrackingRuntime:
    runtime = TrackingRuntime()
    patch.object(
        runtime, "get_timeseries_trainer", return_value=_StubTrainer(error),
    ).start()
    return runtime


def _tool_on(runtime: TrackingRuntime, name: str):
    return asyncio.run(create_server(runtime).get_tool(name)).fn


class TestTimeseriesTrainingEvents:
    def test_train_emits_started_and_completed(self, recorder: EventRecorder) -> None:
        runtime = _runtime_with_trainer()
        result = _tool_on(runtime, "ml_train_timeseries")(
            model_type="lightgbm",
            X_uri="file:///features.npy", y_uri="file:///labels.npy",
            experiment_name="exp-a",
        )
        assert result.ok is True
        started = recorder.of_type("ml.training.started")
        completed = recorder.of_type("ml.training.completed")
        assert len(started) == 1 and len(completed) == 1
        assert started[0]["experiment_name"] == "exp-a"
        assert completed[0]["status"] == "completed"
        assert completed[0]["job_id"] == "stub-job-1"
        assert completed[0]["run_id"] == "stub-run-1"
        assert completed[0]["metrics"] == {"auroc": 0.8}

    def test_train_emits_failed_then_reraises(
        self, recorder: EventRecorder,
    ) -> None:
        runtime = _runtime_with_trainer(RuntimeError("backend exploded"))
        # The backend exception propagates out of the tool body (emit-then-
        # reraise); typed_boundary converts it to a failed envelope after exit.
        result = _tool_on(runtime, "ml_train_timeseries")(
            model_type="lightgbm",
            X_uri="file:///features.npy", y_uri="file:///labels.npy",
            experiment_name="exp-a",
        )
        assert result.ok is False
        failed = recorder.of_type("ml.training.failed")
        assert len(failed) == 1
        assert "backend exploded" in failed[0]["error"]
        assert recorder.of_type("ml.training.completed") == []

    def test_continue_emits_started_and_completed(
        self, recorder: EventRecorder,
    ) -> None:
        runtime = TrackingRuntime()
        timegan = _StubTrainer()
        timegan.continue_train = (  # type: ignore[method-assign]
            lambda **_kwargs: TimeSeriesTrainingJob(
                id="stub-job-2", model_type=TimeSeriesModelType.timegan,
                status="completed", run_id="stub-run-2",
                config=TimeSeriesTrainingConfig(), metrics={"g_loss": 0.1},
            )
        )
        patch.object(runtime, "_timegan_adapter", timegan).start()
        result = _tool_on(runtime, "ml_continue_timeseries")(
            model_id="parent", X_uri="file:///windows.npy",
            experiment_name="exp-b",
        )
        assert result.ok is True
        started = recorder.of_type("ml.training.started")
        completed = recorder.of_type("ml.training.completed")
        assert len(started) == 1 and len(completed) == 1
        assert started[0]["parent_model_id"] == "parent"
        assert completed[0]["job_id"] == "stub-job-2"


class TestCanCoordinatorEvents:
    def test_completed_and_failed_terminals_emit(self, tmp_path: Path) -> None:
        recorder = EventRecorder()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": recorder},
        ):
            coordinator = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path))
            ok = coordinator.run(
                "ml.train-can-portfolio@v1", {"attempt_id": "a1"},
                {}, lambda _ctx: {"can_ids": ["c1"]}, _Result,
            )
            assert ok["status"] == "completed"
            bad = coordinator.run(
                "ml.train-can-portfolio@v1", {"attempt_id": "a2"},
                {}, lambda _ctx: (_ for _ in ()).throw(ValueError("nope")), _Result,
            )
            assert bad["status"] == "failed"
        started = recorder.of_type("ml.training.started")
        completed = recorder.of_type("ml.training.completed")
        failed = recorder.of_type("ml.training.failed")
        assert [s["attempt_id"] for s in started] == ["a1", "a2"]
        assert len(completed) == 1 and completed[0]["attempt_id"] == "a1"
        assert len(failed) == 1 and "nope" in failed[0]["error"]
        # Idempotent-consumption keys ride on every terminal payload.
        assert completed[0]["request_sha256"] == ok["request_sha256"]

    def test_replayed_terminal_emits_nothing(self, tmp_path: Path) -> None:
        recorder = EventRecorder()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": recorder},
        ):
            coordinator = CanLifecycleCoordinator(LocalCanLifecycleStore(tmp_path))
            request = {"attempt_id": "a1"}
            first = coordinator.run(
                "ml.train-can-portfolio@v1", request, {},
                lambda _ctx: {"can_ids": ["c1"]}, _Result,
            )
            first_count = len(recorder.events)
            replay = coordinator.run(
                "ml.train-can-portfolio@v1", request, {},
                lambda _ctx: (_ for _ in ()).throw(
                    AssertionError("runner must not re-execute on replay"),
                ), _Result,
            )
            assert replay["status"] == first["status"] == "completed"
        # Replay short-circuit: no new events for the same attempt.
        assert len(recorder.events) == first_count


class TestCanLifecycleReceipts:
    def test_train_terminal_persists_portfolio_receipts(
        self, tmp_path: Path, recorder: EventRecorder,
    ) -> None:
        row = {
            "rank": 1, "can_id": "c1", "model_family": "lightgbm",
            "job_id": "job-c1", "model_path": "/tmp/c1/model",
            "metrics": {"auroc": 0.9, "noise": "drop-me"},
            "training_config": {"seed": 42},
        }
        operations = CanLifecycleOperations(
            root=tmp_path, runtime=object(), store=LocalCanLifecycleStore(tmp_path),
            invoker=lambda *_args, **_kwargs: None, passport_service=object(),
        )
        terminal = operations.coordinator.run(
            "ml.train-can-portfolio@v1",
            {"attempt_id": "a1", "experiment_name": "exp-c"},
            {}, lambda _ctx: {
                "can_ids": ["c1"], "portfolio": [row],
                "evaluation_record_request": {"experiment_name": "exp-c"},
            }, _Result,
        )
        from factory.machine_learning.runtime.can_lifecycle_receipts import (
            persist_portfolio_receipts,
        )
        persist_portfolio_receipts(terminal)
        doc = recorder.docs["ml_training_runs:mlrun-job-c1"]["data"]
        assert doc["run_id"] == "job-c1"
        assert doc["source"] == "can_lifecycle"
        assert doc["metrics"] == {"auroc": 0.9}
        assert doc["experiment_name"] == "exp-c"

    def test_failed_terminal_persists_nothing(self, tmp_path: Path) -> None:
        recorder = EventRecorder()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": recorder},
        ):
            operations = CanLifecycleOperations(
                root=tmp_path, runtime=object(),
                store=LocalCanLifecycleStore(tmp_path),
                invoker=lambda *_args, **_kwargs: None,
                passport_service=object(),
            )
            terminal = operations.coordinator.run(
                "ml.train-can-portfolio@v1", {"attempt_id": "a1"}, {},
                lambda _ctx: (_ for _ in ()).throw(ValueError("nope")), _Result,
            )
            from factory.machine_learning.runtime.can_lifecycle_receipts import (
                persist_portfolio_receipts,
            )
            persist_portfolio_receipts(terminal)
        assert recorder.docs == {}


class TestReceiptMlflowLink:
    def test_receipt_links_to_real_mlflow_run(self, tmp_path: Path) -> None:
        """End-to-end: tracker run_id -> job -> receipt carries the link."""
        pytest.importorskip("mlflow")
        from factory.machine_learning.runtime.adapters.training_run_store import (
            build_run_record, persist_training_run,
        )

        tracker = MLflowTracker(tracking_uri=f"sqlite:///{tmp_path}/mlflow.db")
        experiment = tracker.create_experiment("link-exp")
        run = tracker.start_run(experiment.id, name="link-run")
        tracker.end_run(run.id, status="completed")

        job = TimeSeriesTrainingJob(
            id="job-link-1",
            model_type=TimeSeriesModelType.lightgbm,
            status="completed",
            experiment_id=experiment.id,
            run_id=run.id,
            config=TimeSeriesTrainingConfig(),
            metrics={"auroc": 0.83},
            model_path="/tmp/job-link-1/model.joblib",
        )
        record = build_run_record(job, experiment_name="link-exp", source="mcp")
        assert record["tracker_run_id"] == run.id
        assert record["tracker_experiment_id"] == experiment.id

        fake = EventRecorder()
        with patch(
            "factory.mcp_utils.registry._services", {"tool_invoker": fake},
        ):
            assert persist_training_run(job, "link-exp", source="mcp") is True
        stored = fake.docs["ml_training_runs:mlrun-job-link-1"]["data"]
        assert stored["tracker_run_id"] == run.id

        # The link resolves back to the real MLflow run through the port.
        readback = tracker.get_run(stored["tracker_run_id"])
        assert readback is not None and readback.id == run.id
