"""Tests for SageMaker runs mixin — runs, metrics, params, datasets."""

import pytest
from unittest.mock import MagicMock, patch

from factory.machine_learning.runtime.ports import Dataset, Run


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def tracker(mock_boto3):
    from factory.machine_learning.runtime.adapters.aws import SageMakerTracker

    return SageMakerTracker(region="us-west-2")


def test_start_run(tracker):
    tracker._client.create_trial.return_value = {}
    run = tracker.start_run("exp-1", name="run-1", tags={"k": "v"})
    assert run.id == "run-1"
    assert run.status == "running"
    assert run.experiment_id == "exp-1"


def test_start_run_auto_name(tracker):
    tracker._client.create_trial.return_value = {}
    run = tracker.start_run("exp-1")
    assert run.name.startswith("run-")


def test_end_run(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    ended = tracker.end_run("r1", status="completed")
    assert ended.status == "completed"
    assert ended.ended_at is not None


def test_get_run_cached(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    assert tracker.get_run("r1") is not None


def test_get_run_from_api(tracker):
    tracker._client.describe_trial.return_value = {"ExperimentName": "exp-1"}
    run = tracker.get_run("r-remote")
    assert run is not None
    assert run.experiment_id == "exp-1"


def test_get_run_not_found(tracker):
    tracker._client.describe_trial.side_effect = Exception("nope")
    assert tracker.get_run("missing") is None


def test_list_runs(tracker):
    tracker._client.list_trials.return_value = {
        "TrialSummaries": [{"TrialName": "r1"}, {"TrialName": "r2"}],
    }
    assert len(tracker.list_runs(experiment_id="exp-1")) == 2


def test_list_runs_fallback(tracker):
    tracker._client.list_trials.side_effect = Exception("fail")
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    assert len(tracker.list_runs()) == 1


def test_log_param(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    tracker.log_param("r1", "lr", 0.01)
    assert tracker._runs["r1"].params["lr"] == 0.01


def test_log_params(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    tracker.log_params("r1", {"a": 1, "b": 2})
    assert tracker._runs["r1"].params == {"a": 1, "b": 2}


def test_log_metric(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    tracker.log_metric("r1", "loss", 0.5)
    assert tracker._runs["r1"].metrics["loss"] == 0.5


def test_log_metrics(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    tracker.log_metrics("r1", {"acc": 0.9, "loss": 0.1})
    assert tracker._runs["r1"].metrics["acc"] == 0.9


def test_log_artifact(tracker):
    tracker._client.create_trial.return_value = {}
    tracker.start_run("exp-1", name="r1")
    tracker.log_artifact("r1", "/path/to/model.pt")
    assert "/path/to/model.pt" in tracker._runs["r1"].artifacts


def test_register_dataset(tracker):
    ds = tracker.register_dataset("ds1", "v1", "/data/ds1")
    assert ds.name == "ds1"
    assert ds.version == "v1"
    assert len(ds.digest) > 0


def test_get_dataset_by_version(tracker):
    tracker.register_dataset("ds1", "v1", "/data/ds1")
    assert tracker.get_dataset("ds1", version="v1") is not None


def test_get_dataset_latest(tracker):
    tracker.register_dataset("ds1", "v1", "/data/v1")
    tracker.register_dataset("ds1", "v2", "/data/v2")
    ds = tracker.get_dataset("ds1")
    assert ds is not None
    assert ds.version == "v2"


def test_get_dataset_not_found(tracker):
    assert tracker.get_dataset("nope") is None
