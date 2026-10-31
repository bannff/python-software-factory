"""Tests for AWS DynamoDB + Step Functions workflow storage adapter."""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from botocore.exceptions import ClientError

from factory.workflow.runtime.envelope import Envelope


@pytest.fixture
def mock_boto3():
    with patch("boto3.resource") as mr, patch("boto3.client") as mc:
        table = MagicMock()
        mr.return_value.Table.return_value = table
        yield {"resource": mr, "client": mc, "table": table}


@pytest.fixture
def storage(mock_boto3):
    from factory.workflow.runtime.storage.aws import AWSWorkflowStorage

    return AWSWorkflowStorage(
        state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:my-sm",
        table_name="wf-runs",
    )


@pytest.fixture
def envelope():
    return Envelope()


@pytest.fixture
def now():
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_invalid_arn(mock_boto3):
    from factory.workflow.runtime.storage.aws import AWSWorkflowStorage

    with pytest.raises(ValueError, match="Invalid state_machine_arn"):
        AWSWorkflowStorage(state_machine_arn="bad-arn")


def test_invalid_table_name(mock_boto3):
    from factory.workflow.runtime.storage.aws import AWSWorkflowStorage

    with pytest.raises(ValueError, match="Invalid table_name"):
        AWSWorkflowStorage(table_name="a")  # too short


def test_init_schema_noop(storage):
    storage.init_schema()  # should not raise


def test_health_check_ok(storage, mock_boto3):
    type(mock_boto3["table"]).table_status = PropertyMock(return_value="ACTIVE")
    h = storage.health_check()
    assert h["ok"] is True


def test_health_check_error(storage, mock_boto3):
    type(mock_boto3["table"]).table_status = PropertyMock(side_effect=Exception("no table"))
    h = storage.health_check()
    assert h["ok"] is False
    assert h["backend"] == "aws"


def test_create_run(storage, mock_boto3, envelope, now):
    run = storage.create_run(
        run_id="r1", workflow_id="wf1", workflow_version=1,
        tenant_id="t1", input={"x": 1}, envelope=envelope, now=now,
    )
    assert run.run_id == "r1"
    assert run.status == "pending"
    mock_boto3["table"].put_item.assert_called_once()


def test_get_run_found(storage, mock_boto3):
    mock_boto3["table"].get_item.return_value = {"Item": {
        "run_id": "r1", "workflow_id": "wf1", "workflow_version": 1,
        "status": "running", "started_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00", "input_json": "{}",
    }}
    run = storage.get_run(run_id="r1")
    assert run is not None
    assert run.run_id == "r1"


def test_get_run_not_found(storage, mock_boto3):
    mock_boto3["table"].get_item.return_value = {}
    assert storage.get_run(run_id="r1") is None


def test_append_event(storage, mock_boto3, envelope, now):
    mock_boto3["table"].query.return_value = {"Items": []}
    ev = storage.append_event(
        run_id="r1", event_type="step_done",
        payload={"step": "s1"}, envelope=envelope, now=now,
    )
    assert ev.id == 1
    assert ev.event_type == "step_done"


def test_get_events_since(storage, mock_boto3):
    mock_boto3["table"].query.return_value = {"Items": [
        {"id": 2, "run_id": "r1", "event_type": "done",
         "payload_json": "{}", "created_at": "2024-01-01T00:00:00+00:00"},
    ]}
    events = storage.get_events_since(run_id="r1", after_event_id=1)
    assert len(events) == 1
    assert events[0].id == 2


def test_list_runs(storage, mock_boto3):
    mock_boto3["table"].scan.return_value = {
        "Items": [{
            "run_id": "r1", "workflow_id": "wf1", "workflow_version": 1,
            "status": "pending", "started_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00", "input_json": "{}",
        }],
    }
    runs, cursor = storage.list_runs(
        tenant_id=None, workflow_id=None, status=None, limit=10, cursor=None,
    )
    assert len(runs) == 1


def test_list_runs_with_filter(storage, mock_boto3):
    mock_boto3["table"].scan.return_value = {
        "Items": [{
            "run_id": "r1", "workflow_id": "wf1", "workflow_version": 1,
            "status": "pending", "started_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00", "input_json": "{}",
        }],
    }
    runs, _ = storage.list_runs(
        tenant_id=None, workflow_id=None, status="running", limit=10, cursor=None,
    )
    assert len(runs) == 0  # filtered out


def test_infrastructure_spec(storage):
    spec = storage.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert "dynamodb" in spec["services"]
    assert len(spec["resources"]) == 2


def test_update_run_enforces_status_and_revision_cas(storage, mock_boto3, now):
    mock_boto3["table"].get_item.return_value = {"Item": {
        "run_id": "r1", "workflow_id": "wf1", "workflow_version": 1,
        "status": "cancelled", "revision": 2,
        "started_at": now.isoformat(), "updated_at": now.isoformat(),
        "input_json": "{}",
    }}
    result = storage.update_run(
        run_id="r1", status="succeeded", current_step_id="task",
        waiting_for_event_type=None, last_event_id=None, result={"ok": True},
        error=None, now=now, expected_statuses={"running"}, expected_revision=1,
    )
    kwargs = mock_boto3["table"].update_item.call_args.kwargs
    assert "ConditionExpression" in kwargs
    assert "#s IN" in kwargs["ConditionExpression"]
    assert "#rev=:expected_revision" in kwargs["ConditionExpression"]
    assert result.status == "cancelled"


def test_update_run_reports_conditional_cas_failure(storage, mock_boto3, now):
    mock_boto3["table"].update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "stale"}},
        "UpdateItem",
    )
    with pytest.raises(ValueError, match="stale run transition"):
        storage.update_run(
            run_id="r1", status="failed", current_step_id="task",
            waiting_for_event_type=None, last_event_id=None, result=None,
            error="late", now=now, expected_statuses={"running"},
            expected_revision=1,
        )


def test_aws_sinks_reject_artifact_bound_inline_content(storage, mock_boto3, envelope, now):
    artifact = {"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "fingerprint": "a" * 64,
                "descriptor": {"classification": "business", "purpose": "email", "tenant_id": "t",
                               "owner_principal_id": "o", "artifact_kind": "email"}}
    payload = {"artifact": artifact, "body": "aws-business-canary@example.test"}
    with pytest.raises(ValueError, match="protected inline content is forbidden"):
        storage.create_run(run_id="r1", workflow_id="wf1", workflow_version=1,
                           tenant_id="t1", input=payload, envelope=envelope, now=now)
    with pytest.raises(ValueError, match="protected inline content is forbidden"):
        storage.append_event(run_id="r1", event_type="sent", payload=payload,
                             envelope=envelope, now=now)
    for call in mock_boto3["table"].put_item.call_args_list:
        assert "aws-business-canary@example.test" not in repr(call)


def test_update_run_redacts_protected_error_before_dynamodb_write(storage, mock_boto3, now):
    mock_boto3["table"].get_item.return_value = {"Item": {
        "run_id": "r1", "workflow_id": "wf1", "workflow_version": 1,
        "status": "failed", "started_at": now.isoformat(),
        "updated_at": now.isoformat(), "input_json": "{}",
    }}
    canary = "workflow-aws-protected@example.test"
    storage.update_run(
        run_id="r1", status="failed", current_step_id="task",
        waiting_for_event_type=None, last_event_id=None, result=None,
        error=f"subject={canary}", now=now,
    )
    values = mock_boto3["table"].update_item.call_args.kwargs[
        "ExpressionAttributeValues"
    ]
    assert values[":e"] == "subject=[protected]"
    assert canary not in repr(values)
