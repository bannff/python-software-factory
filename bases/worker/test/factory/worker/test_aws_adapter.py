"""Tests for AWS Lambda + SQS worker adapter."""

import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mock_client:
        yield mock_client


@pytest.fixture
def adapter(mock_boto3):
    from factory.worker.runtime.adapters.aws import AWSWorkerAdapter

    mock_boto3.return_value = MagicMock()
    a = AWSWorkerAdapter(
        function_name="my-func",
        queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
    )
    return a


def test_backend_type(adapter):
    assert adapter.backend_type == "aws_lambda"


def test_invalid_function_name(mock_boto3):
    from factory.worker.runtime.adapters.aws import AWSWorkerAdapter

    with pytest.raises(ValueError, match="Invalid function_name"):
        AWSWorkerAdapter(function_name="bad name!!!")


def test_invalid_queue_url(mock_boto3):
    from factory.worker.runtime.adapters.aws import AWSWorkerAdapter

    with pytest.raises(ValueError, match="Invalid queue_url"):
        AWSWorkerAdapter(function_name="good-func", queue_url="not-a-url")


def test_start_is_noop(adapter):
    adapter.start(queues=["q1"])  # should not raise


def test_health_check_healthy(adapter):
    adapter._lambda.get_function.return_value = {
        "Configuration": {"State": "Active"},
    }
    h = adapter.health_check()
    assert h.healthy is True
    assert h.backend == "aws_lambda"


def test_health_check_inactive(adapter):
    adapter._lambda.get_function.return_value = {
        "Configuration": {"State": "Inactive"},
    }
    h = adapter.health_check()
    assert h.healthy is False


def test_health_check_error(adapter):
    adapter._lambda.get_function.side_effect = Exception("boom")
    h = adapter.health_check()
    assert h.healthy is False
    assert "boom" in h.error


def test_list_tasks_with_messages(adapter):
    adapter._sqs.receive_message.return_value = {
        "Messages": [
            {"Body": json.dumps({"task_name": "do_stuff"}), "MessageId": "m1"},
        ],
    }
    tasks = adapter.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].name == "do_stuff"
    assert tasks[0].state == "PENDING"


def test_list_tasks_no_sqs():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        from factory.worker.runtime.adapters.aws import AWSWorkerAdapter

        a = AWSWorkerAdapter(function_name="f1", queue_url="")
        assert a.list_tasks() == []


def test_list_tasks_empty(adapter):
    adapter._sqs.receive_message.return_value = {"Messages": []}
    assert adapter.list_tasks() == []


def test_list_tasks_exception(adapter):
    adapter._sqs.receive_message.side_effect = Exception("sqs err")
    assert adapter.list_tasks() == []


def test_send_task(adapter):
    adapter._lambda.invoke.return_value = {
        "StatusCode": 202,
        "ResponseMetadata": {"RequestId": "req-123"},
    }
    result = adapter.send_task("my_task", args=(1, 2), kwargs={"k": "v"})
    assert result["task_id"] == "req-123"
    assert result["status"] == "dispatched"
    assert result["status_code"] == 202


def test_infrastructure_spec(adapter):
    spec = adapter.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert "lambda" in spec["services"]
    assert len(spec["resources"]) == 2


def test_infrastructure_spec_no_queue():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        from factory.worker.runtime.adapters.aws import AWSWorkerAdapter

        a = AWSWorkerAdapter(function_name="f1")
        spec = a.infrastructure_spec()
        assert len(spec["resources"]) == 1
