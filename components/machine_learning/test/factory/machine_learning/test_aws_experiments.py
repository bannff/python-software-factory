"""Tests for SageMaker experiment tracker — experiment + health methods."""

import pytest
from unittest.mock import MagicMock, patch

from factory.machine_learning.runtime.ports import Experiment, TrackerHealth


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def tracker(mock_boto3):
    from factory.machine_learning.runtime.adapters.aws import SageMakerTracker

    return SageMakerTracker(region="us-west-2")


def test_create_experiment_valid(tracker):
    tracker._client.create_experiment.return_value = {}
    exp = tracker.create_experiment("exp-1", description="test")
    assert exp.id == "exp-1"
    assert exp.name == "exp-1"
    tracker._client.create_experiment.assert_called_once()


def test_create_experiment_invalid_name(tracker):
    with pytest.raises(ValueError, match="Invalid experiment name"):
        tracker.create_experiment("bad name!!!")


def test_get_experiment_found(tracker):
    tracker._client.describe_experiment.return_value = {
        "ExperimentName": "exp-1", "Description": "desc",
    }
    exp = tracker.get_experiment("exp-1")
    assert exp is not None
    assert exp.description == "desc"


def test_get_experiment_not_found(tracker):
    tracker._client.describe_experiment.side_effect = Exception("not found")
    assert tracker.get_experiment("nope") is None


def test_get_experiment_by_name(tracker):
    tracker._client.describe_experiment.return_value = {
        "ExperimentName": "exp-1",
    }
    assert tracker.get_experiment_by_name("exp-1") is not None


def test_list_experiments(tracker):
    tracker._client.list_experiments.return_value = {
        "ExperimentSummaries": [
            {"ExperimentName": "e1"}, {"ExperimentName": "e2"},
        ],
    }
    assert len(tracker.list_experiments()) == 2


def test_list_experiments_error(tracker):
    tracker._client.list_experiments.side_effect = Exception("fail")
    assert tracker.list_experiments() == []


def test_health_check_ok(tracker):
    tracker._client.list_experiments.return_value = {}
    h = tracker.health_check()
    assert h.healthy is True
    assert h.backend == "sagemaker"


def test_health_check_error(tracker):
    tracker._client.list_experiments.side_effect = Exception("fail")
    h = tracker.health_check()
    assert h.healthy is False
    assert "fail" in h.message


def test_infrastructure_spec(tracker):
    spec = tracker.infrastructure_spec()
    assert spec["service"] == "sagemaker"
    assert "experiment_tracking" in spec["props"]["features"]
