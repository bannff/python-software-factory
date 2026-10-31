"""Tests for ECS Fargate + SQS worker adapter."""

import json
import pytest
from unittest.mock import MagicMock, patch

VALID_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mock_client:
        mock_client.return_value = MagicMock()
        yield mock_client


@pytest.fixture
def adapter(mock_boto3):
    from factory.worker.runtime.adapters.fargate_sqs import FargateSQSAdapter

    return FargateSQSAdapter(queue_url=VALID_URL)

# --- Constructor validation ---


def test_valid_queue_url(mock_boto3):
    from factory.worker.runtime.adapters.fargate_sqs import FargateSQSAdapter

    a = FargateSQSAdapter(queue_url=VALID_URL)
    assert a._queue_url == VALID_URL


@pytest.mark.parametrize("bad_url", [
    "",
    "not-a-url",
    "http://sqs.us-east-1.amazonaws.com/123456789012/q",
    "https://sqs.us-east-1.amazonaws.com/12345/q",
    "https://sqs.us-east-1.amazonaws.com/123456789012/",
])
def test_invalid_queue_url_raises(mock_boto3, bad_url):
    from factory.worker.runtime.adapters.fargate_sqs import FargateSQSAdapter

    with pytest.raises(ValueError, match="Invalid queue_url"):
        FargateSQSAdapter(queue_url=bad_url)

# --- backend_type ---


def test_backend_type(adapter):
    assert adapter.backend_type == "fargate_sqs"

# --- health_check ---


def test_health_check_healthy(adapter):
    adapter._sqs.get_queue_attributes.return_value = {
        "Attributes": {"ApproximateNumberOfMessages": "5"},
    }
    h = adapter.health_check()
    assert h.healthy is True
    assert h.backend == "fargate_sqs"
    assert h.active_tasks == 5
    assert h.queues == ["test-queue"]


def test_health_check_error(adapter):
    adapter._sqs.get_queue_attributes.side_effect = Exception("access denied")
    h = adapter.health_check()
    assert h.healthy is False
    assert h.backend == "fargate_sqs"
    assert "access denied" in h.error

# --- list_tasks ---


def test_list_tasks_returns_task_info(adapter):
    adapter._sqs.receive_message.return_value = {
        "Messages": [
            {"Body": json.dumps({"tool_name": "kb_search"}), "MessageId": "m1"},
            {"Body": json.dumps({"tool_name": "cache_get"}), "MessageId": "m2"},
        ],
    }
    tasks = adapter.list_tasks()
    assert len(tasks) == 2
    assert tasks[0].name == "kb_search"
    assert tasks[0].state == "PENDING"
    assert tasks[0].queue == "test-queue"
    adapter._sqs.receive_message.assert_called_once_with(
        QueueUrl=VALID_URL, MaxNumberOfMessages=10,
        WaitTimeSeconds=0, VisibilityTimeout=0,
    )


def test_list_tasks_empty(adapter):
    adapter._sqs.receive_message.return_value = {"Messages": []}
    assert adapter.list_tasks() == []


def test_list_tasks_no_messages_key(adapter):
    adapter._sqs.receive_message.return_value = {}
    assert adapter.list_tasks() == []


def test_list_tasks_exception(adapter):
    adapter._sqs.receive_message.side_effect = Exception("timeout")
    assert adapter.list_tasks() == []

# --- send_task ---


def test_send_task(adapter):
    adapter._sqs.send_message.return_value = {"MessageId": "msg-42"}
    result = adapter.send_task("my_tool", kwargs={"key": "val"})
    assert result["task_id"] == "msg-42"
    assert result["status"] == "queued"
    assert result["queue"] == "test-queue"
    body = json.loads(
        adapter._sqs.send_message.call_args.kwargs["MessageBody"]
    )
    assert body["tool_name"] == "my_tool"
    assert body["args"] == []
    assert body["arguments"] == {"key": "val"}


def test_send_task_preserves_positional_and_keyword_arguments(adapter):
    adapter._sqs.send_message.return_value = {"MessageId": "msg-mixed"}
    adapter.send_task("mixed", args=(1, "two"), kwargs={"flag": True})
    body = json.loads(adapter._sqs.send_message.call_args.kwargs["MessageBody"])
    assert body["args"] == [1, "two"]
    assert body["arguments"] == {"flag": True}

# --- infrastructure_spec ---


def test_infrastructure_spec(adapter):
    spec = adapter.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert "ecs" in spec["services"]
    assert "sqs" in spec["services"]
    assert len(spec["resources"]) == 2
    types = {r["type"] for r in spec["resources"]}
    assert "AWS::ECS::Service" in types
    assert "AWS::SQS::Queue" in types

# --- _process_message ---


def test_process_message_tool_action(adapter):
    """Direct tool action dispatches to execute_mcp_tool."""
    msg = {"Body": json.dumps({"action": "tool", "tool_name": "kb_search",
                                "arguments": {"q": "hi"}})}
    with patch("factory.worker.runtime.bridge.execute_mcp_tool") as mock_exec:
        mock_exec.return_value = {"ok": True}
        adapter._process_message(msg)
        mock_exec.assert_called_once_with("kb_search", {"q": "hi"})


def test_process_message_swarm_action(adapter):
    """Swarm action dispatches agent_invoke_swarm."""
    msg = {"Body": json.dumps({"action": "swarm", "swarm_id": "s1",
                                "task": "do stuff"})}
    with patch("factory.worker.runtime.bridge.execute_mcp_tool") as mock_exec:
        mock_exec.return_value = {"ok": True}
        adapter._process_message(msg)
        mock_exec.assert_called_once_with(
            "agent_invoke_swarm", {"swarm_id": "s1", "task": "do stuff"},
        )

# --- _poll_once ---


def test_poll_once_receive_process_delete(adapter):
    msg = {
        "Body": json.dumps({"action": "tool", "tool_name": "ping", "arguments": {}}),
        "ReceiptHandle": "rh-1",
        "MessageId": "m1",
    }
    adapter._sqs.receive_message.return_value = {"Messages": [msg]}
    with patch.object(adapter, "_process_message") as mock_proc:
        adapter._poll_once()
        mock_proc.assert_called_once_with(msg)
    adapter._sqs.delete_message.assert_called_once_with(
        QueueUrl=VALID_URL, ReceiptHandle="rh-1",
    )
    assert adapter._processed == 1
    assert adapter._errors == 0


def test_poll_once_error_increments_errors(adapter):
    msg = {"Body": "{}", "ReceiptHandle": "rh-2", "MessageId": "m2"}
    adapter._sqs.receive_message.return_value = {"Messages": [msg]}
    with patch.object(adapter, "_process_message", side_effect=RuntimeError("bad")):
        adapter._poll_once()
    assert adapter._errors == 1
    assert adapter._processed == 0
    adapter._sqs.delete_message.assert_not_called()


def test_process_message_forwards_positional_arguments(adapter):
    msg = {
        "Body": json.dumps({
            "action": "tool",
            "tool_name": "demo",
            "args": [1, "two"],
            "arguments": {"flag": True},
        }),
    }
    with patch("factory.worker.runtime.bridge.execute_mcp_tool") as mock_exec:
        mock_exec.return_value = {"ok": True}
        adapter._process_message(msg)
        mock_exec.assert_called_once_with(
            "demo", {"flag": True}, positional_args=[1, "two"],
        )
