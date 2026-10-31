"""Tests for the training-run persistence + dashboard pipeline.

Covers bd:python-factory-zgg1x: training_run_store persist,
training_run_reader regression enrichment, dashboard summary
aggregation, and the sklearn-default backend resolution.
Uses the same fake-invoker doc-store pattern as the evals brick tests.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from factory.machine_learning.runtime.ports import (
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
)
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.operational import (
    DocumentData,
    DocFindOutput,
    DocGetOutput,
    DocInsertOutput,
)


class FakeDocStore:
    """In-memory stand-in for storage_doc_insert/find/get."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def __call__(self, tool_name: str, **kwargs):
        if tool_name == "storage_doc_insert":
            key = f"{kwargs['collection']}:{kwargs['doc_id']}"
            self.docs[key] = {"id": kwargs["doc_id"], "data": kwargs["data"]}
            return {"inserted": True}
        if tool_name == "storage_doc_find":
            prefix = f"{kwargs['collection']}:"
            return {"documents": [
                doc for key, doc in self.docs.items() if key.startswith(prefix)
            ]}
        if tool_name == "storage_doc_get":
            return self.docs.get(
                f"{kwargs['collection']}:{kwargs['doc_id']}", {"error": "not found"},
            )
        raise AssertionError(f"unexpected tool: {tool_name}")


def _job(job_id: str, auroc: float) -> TimeSeriesTrainingJob:
    return TimeSeriesTrainingJob(
        id=job_id,
        model_type=TimeSeriesModelType.lightgbm,
        status="completed",
        config=TimeSeriesTrainingConfig(),
        metrics={"auroc": auroc, "f1": 0.5},
        model_path=f"/tmp/{job_id}/model.joblib",
    )


@pytest.fixture
def store():
    fake = FakeDocStore()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": fake}):
        yield fake


class TestPersistAndRead:
    def test_persist_then_list_roundtrip(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_store import (
            persist_training_run,
        )
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            list_training_runs,
        )
        assert persist_training_run(_job("run-1", 0.8), "exp-a", source="mcp")
        runs = list_training_runs()
        assert len(runs) == 1
        run = runs[0]
        assert run["run_id"] == "run-1"
        assert run["experiment_name"] == "exp-a"
        assert run["primary_metric"] == "auroc"
        assert run["primary_value"] == 0.8
        assert run["regression_state"] == "baseline"

    def test_persist_is_best_effort_without_invoker(self) -> None:
        from factory.machine_learning.runtime.adapters.training_run_store import (
            persist_training_run,
        )
        with patch("factory.mcp_utils.registry._services", {}):
            assert persist_training_run(_job("run-x", 0.7)) is False

    def test_get_training_run_by_id(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_store import (
            persist_training_run,
        )
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            get_training_run,
        )
        persist_training_run(_job("run-9", 0.9), "exp-a")
        record = get_training_run("run-9")
        assert record is not None and record["metrics"]["auroc"] == 0.9
        assert get_training_run("nope") is None

    def test_malformed_docs_are_skipped(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            list_training_runs,
        )
        store("storage_doc_insert", collection="ml_training_runs",
              doc_id="mlrun-bad", data={"run_id": "bad"})  # no model_type/metrics
        assert list_training_runs() == []


class TestRegressionEnrichment:
    def _persist_sequence(self, aurocs: list[float]) -> None:
        from factory.machine_learning.runtime.adapters.training_run_store import (
            persist_training_run,
        )
        for i, auroc in enumerate(aurocs):
            persist_training_run(_job(f"run-{i}", auroc), "exp-a")

    def test_improved_and_regressed_states(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            list_training_runs,
        )
        self._persist_sequence([0.6, 0.8, 0.7])
        newest_first = list_training_runs()
        by_id = {run["run_id"]: run for run in newest_first}
        assert by_id["run-0"]["regression_state"] == "baseline"
        assert by_id["run-1"]["regression_state"] == "improved"
        assert by_id["run-1"]["previous_run_id"] == "run-0"
        assert by_id["run-2"]["regression_state"] == "regressed"
        assert by_id["run-2"]["metric_delta"] == pytest.approx(-0.1)

    def test_steady_within_epsilon(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            list_training_runs,
        )
        self._persist_sequence([0.7, 0.705])
        by_id = {run["run_id"]: run for run in list_training_runs()}
        assert by_id["run-1"]["regression_state"] == "steady"


class TestDashboardSummary:
    def test_summary_shape_and_regression_count(self, store: FakeDocStore) -> None:
        from factory.machine_learning.runtime.adapters.training_run_store import (
            persist_training_run,
        )
        from factory.machine_learning.runtime.adapters.training_run_reader import (
            list_training_runs,
        )
        from factory.machine_learning.mcp.dashboard_summary import (
            _build_dashboard_summary,
        )
        persist_training_run(_job("run-0", 0.8), "exp-a")
        persist_training_run(_job("run-1", 0.6), "exp-a")
        persist_training_run(_job("run-2", 0.9), "exp-b")
        summary = _build_dashboard_summary(list_training_runs())
        assert summary["overview"]["runs"] == 3
        assert summary["overview"]["experiments"] == 2
        assert summary["overview"]["regressions"] == 1
        # Regressed experiment sorts first.
        assert summary["experiments"][0]["experiment_name"] == "exp-a"
        exp_a = summary["experiments"][0]
        assert exp_a["recent_values"] == [0.8, 0.6]
        assert exp_a["best_value"] == 0.8
        assert len(summary["series"]) == 3


class TestBackendResolution:
    def test_default_is_sklearn(self, monkeypatch) -> None:
        from factory.machine_learning.runtime.timeseries_factory import (
            resolve_timeseries_backend,
        )
        monkeypatch.delenv("ML_TIMESERIES_BACKEND", raising=False)
        assert resolve_timeseries_backend(None) == "sklearn"
        assert resolve_timeseries_backend("memory") == "memory"

    def test_env_override_and_unknown_rejected(self, monkeypatch) -> None:
        from factory.machine_learning.runtime.timeseries_factory import (
            resolve_timeseries_backend,
        )
        monkeypatch.setenv("ML_TIMESERIES_BACKEND", "memory")
        assert resolve_timeseries_backend(None) == "memory"
        with pytest.raises(ValueError):
            resolve_timeseries_backend("nope")

    def test_none_and_resolved_share_cache_entry(self, monkeypatch) -> None:
        from factory.machine_learning.runtime.runtime import TrackingRuntime
        monkeypatch.setenv("ML_TIMESERIES_BACKEND", "memory")
        runtime = TrackingRuntime()
        assert runtime.get_timeseries_trainer() is runtime.get_timeseries_trainer("memory")

    def test_views_expose_ml_models_first(self) -> None:
        from factory.machine_learning.mcp.views_models import training_runs, trend_chart
        from factory.machine_learning.mcp.views_learning import learning_view
        assert trend_chart()["props"]["data_tool"] == "ml_get_dashboard_summary"
        assert training_runs()["props"]["data_tool"] == "ml_list_training_runs"
        assert learning_view()["id"] == "ml-learning-runs"


def test_real_storage_tool_results_are_consumed_and_fail_best_effort() -> None:
    from factory.machine_learning.runtime.adapters.training_run_reader import (
        get_training_run,
        list_training_runs,
    )
    from factory.machine_learning.runtime.adapters.training_run_store import persist_training_run

    record = {
        "run_id": "run-real", "experiment_name": "exp-a", "model_type": "lightgbm",
        "status": "completed", "metrics": {"auroc": 0.8}, "timestamp": "2026-01-01T00:00:00Z",
    }

    def successful(tool_name: str, **_kwargs):
        if tool_name == "storage_doc_insert":
            return ToolResult(data=DocInsertOutput(id="mlrun-run-real", collection="ml_training_runs"))
        if tool_name == "storage_doc_find":
            return ToolResult(data=DocFindOutput(documents=[DocumentData(id="mlrun-run-real", data=record)]))
        if tool_name == "storage_doc_get":
            return ToolResult(data=DocGetOutput(found=True, id="mlrun-run-real", collection="ml_training_runs", data=record))
        raise AssertionError(tool_name)

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": successful}):
        assert persist_training_run(_job("run-real", 0.8), "exp-a") is True
        assert [run["run_id"] for run in list_training_runs()] == ["run-real"]
        assert get_training_run("run-real") == record

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": lambda *_args, **_kwargs: ToolResult(ok=False, error="down")}):
        assert persist_training_run(_job("run-failed", 0.8), "exp-a") is False
        assert list_training_runs() == []
        assert get_training_run("run-failed") is None
