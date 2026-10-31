"""AWS DynamoDB + Step Functions adapter for workflow brick."""
from __future__ import annotations

import json, re
from datetime import datetime
from typing import Any

from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import EventRecord, RunRecord
from . import aws_runs

def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        raise ImportError("pip install boto3 — required for AWS workflow adapter")

_ARN_RE = re.compile(r"^arn:aws:states:[\w-]+:\d{12}:stateMachine:[\w-]+$")
_TABLE_RE = re.compile(r"^[A-Za-z0-9._-]{3,255}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,255}$")

def _validate_id(value: str, label: str = "identifier") -> str:
    if not _SAFE_ID.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value

class AWSWorkflowStorage:
    """DynamoDB + Step Functions adapter for WorkflowStorage port."""

    def __init__(self, state_machine_arn: str = "", table_name: str = "factory-workflow-runs",
                 region: str = "us-east-1", **kwargs: Any) -> None:
        _require_boto3()
        if state_machine_arn and not _ARN_RE.match(state_machine_arn):
            raise ValueError(f"Invalid state_machine_arn: {state_machine_arn!r}")
        if not _TABLE_RE.match(table_name):
            raise ValueError(f"Invalid table_name: {table_name!r}")
        import boto3
        self._ddb = boto3.resource("dynamodb", region_name=region)
        self._sfn = boto3.client("stepfunctions", region_name=region)
        self._table_name = table_name
        self._sfn_arn = state_machine_arn
        self._region = region
        self._table = self._ddb.Table(table_name)

    def init_schema(self) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        try:
            self._table.table_status
            return {"ok": True, "backend": "aws", "table": self._table_name}
        except Exception:
            return {"ok": False, "backend": "aws"}

    def create_run(
        self, *, run_id: str, workflow_id: str, workflow_version: int,
        tenant_id: str | None, input: dict[str, Any], envelope: Envelope, now: datetime,
        run_key: str | None = None, workflow_version_id: str | None = None,
        run_execution_id: str | None = None,
    ) -> RunRecord:
        _validate_id(run_id, "run_id")
        _validate_id(workflow_id, "workflow_id")
        iso = now.isoformat()
        item = {
            "PK": f"RUN#{run_id}", "SK": "META",
            "run_id": run_id, "workflow_id": workflow_id,
            "workflow_version": workflow_version, "status": "pending",
            "tenant_id": tenant_id or "", "input_json": canonical_json(input),
            "started_at": iso, "updated_at": iso, "last_event_id": 0,
            "revision": 0, "run_key": run_key,
        }
        self._table.put_item(Item=item)
        return RunRecord(
            run_id=run_id, run_key=run_key, workflow_id=workflow_id,
            workflow_version=workflow_version, status="pending",
            started_at=now, updated_at=now, input=input, tenant_id=tenant_id,
        )

    def get_run(self, *, run_id: str) -> RunRecord | None:
        _validate_id(run_id, "run_id")
        resp = self._table.get_item(Key={"PK": f"RUN#{run_id}", "SK": "META"})
        item = resp.get("Item")
        if not item:
            return None
        return aws_runs.item_to_run(item)

    def update_run(
        self, *, run_id: str, status: str, current_step_id: str | None,
        waiting_for_event_type: str | None, last_event_id: int | None,
        result: dict[str, Any] | None, error: str | None, now: datetime,
        expected_statuses: set[str] | None = None,
        expected_revision: int | None = None,
    ) -> RunRecord:
        return aws_runs.update(
            self._table, self.get_run, run_id=run_id, status=status,
            current_step_id=current_step_id,
            waiting_for_event_type=waiting_for_event_type,
            last_event_id=last_event_id, result=result, error=error, now=now,
            expected_statuses=expected_statuses,
            expected_revision=expected_revision,
        )

    def list_runs(
        self, *, tenant_id: str | None, workflow_id: str | None,
        status: str | None, limit: int, cursor: str | None,
    ) -> tuple[list[RunRecord], str | None]:
        kw: dict[str, Any] = {
            "FilterExpression": "SK = :sk",
            "ExpressionAttributeValues": {":sk": "META"}, "Limit": limit}
        if cursor:
            kw["ExclusiveStartKey"] = json.loads(cursor)
        resp = self._table.scan(**kw)
        runs = [aws_runs.item_to_run(i) for i in resp.get("Items", [])]
        for attr, val in [("tenant_id", tenant_id), ("workflow_id", workflow_id), ("status", status)]:
            if val:
                runs = [r for r in runs if getattr(r, attr) == val]
        nxt = json.dumps(resp["LastEvaluatedKey"]) if resp.get("LastEvaluatedKey") else None
        return runs, nxt

    def append_event(
        self, *, run_id: str, event_type: str, payload: dict[str, Any],
        envelope: Envelope, now: datetime,
    ) -> EventRecord:
        _validate_id(run_id, "run_id")
        _validate_id(event_type, "event_type")
        last_id = self.get_last_event_id(run_id=run_id)
        new_id = last_id + 1
        self._table.put_item(Item={
            "PK": f"RUN#{run_id}", "SK": f"EVT#{new_id:010d}",
            "id": new_id, "run_id": run_id, "event_type": event_type,
            "payload_json": canonical_json(payload), "created_at": now.isoformat(),
        })
        return EventRecord(
            id=new_id, run_id=run_id, event_type=event_type,
            payload=payload, created_at=now,
        )

    def get_events_since(self, *, run_id: str, after_event_id: int) -> list[EventRecord]:
        _validate_id(run_id, "run_id")
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND SK > :sk",
            ExpressionAttributeValues={
                ":pk": f"RUN#{run_id}", ":sk": f"EVT#{after_event_id:010d}",
            },
        )
        return [self._item_to_event(i) for i in resp.get("Items", [])]

    def get_last_event_id(self, *, run_id: str) -> int:
        _validate_id(run_id, "run_id")
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": f"RUN#{run_id}", ":prefix": "EVT#"},
            ScanIndexForward=False, Limit=1,
        )
        items = resp.get("Items", [])
        return int(items[0]["id"]) if items else 0

    def infrastructure_spec(self) -> dict[str, Any]:
        return {"provider": "aws", "services": ["dynamodb", "stepfunctions"], "resources": [
            {"type": "AWS::DynamoDB::Table", "properties": {
                "TableName": self._table_name,
                "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"},
                               {"AttributeName": "SK", "KeyType": "RANGE"}]}},
            {"type": "AWS::StepFunctions::StateMachine",
             "properties": {"StateMachineArn": self._sfn_arn}}]}

    @staticmethod
    def _item_to_event(item: dict) -> EventRecord:
        return EventRecord(
            id=int(item["id"]), run_id=item["run_id"], event_type=item["event_type"],
            payload=json.loads(item.get("payload_json", "{}")),
            created_at=datetime.fromisoformat(item["created_at"]))
