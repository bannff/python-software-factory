"""DynamoDB run conversion and conditional-update operations."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from factory.workflow.runtime.canonical import canonical_json
from factory.mcp_utils.interface import sanitize_protected_error
from factory.workflow.runtime.models import RunRecord


def update(
    table: Any, get_run: Any, *, run_id: str, status: str,
    current_step_id: str | None, waiting_for_event_type: str | None,
    last_event_id: int | None, result: dict[str, Any] | None,
    error: str | None, now: datetime, expected_statuses: set[str] | None,
    expected_revision: int | None,
) -> RunRecord:
    parts = ["#s=:s", "updated_at=:u", "#rev=if_not_exists(#rev,:zero)+:one"]
    values: dict[str, Any] = {
        ":s": status, ":u": now.isoformat(), ":zero": 0, ":one": 1,
    }
    names = {"#s": "status", "#rev": "revision"}
    for attribute, key, value in (
        ("current_step_id", ":cs", current_step_id),
        ("waiting_for_event_type", ":we", waiting_for_event_type),
        ("last_event_id", ":le", last_event_id),
    ):
        if value is not None:
            parts.append(f"{attribute}={key}")
            values[key] = value
    if result is not None:
        parts.append("result_json=:r")
        values[":r"] = canonical_json(result)
    if error is not None:
        parts.append("#err=:e")
        values[":e"], names["#err"] = sanitize_protected_error(error), "error"
    conditions = []
    if expected_statuses:
        keys = []
        for index, expected in enumerate(sorted(expected_statuses)):
            key = f":expected_status_{index}"
            keys.append(key)
            values[key] = expected
        conditions.append(f"#s IN ({','.join(keys)})")
    if expected_revision is not None:
        values[":expected_revision"] = expected_revision
        revision_match = "#rev=:expected_revision"
        if expected_revision == 0:
            revision_match = f"(attribute_not_exists(#rev) OR {revision_match})"
        conditions.append(revision_match)
    kwargs = {
        "Key": {"PK": f"RUN#{run_id}", "SK": "META"},
        "UpdateExpression": "SET " + ",".join(parts),
        "ExpressionAttributeValues": values,
        "ExpressionAttributeNames": names,
    }
    if conditions:
        kwargs["ConditionExpression"] = " AND ".join(conditions)
    try:
        table.update_item(**kwargs)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            raise ValueError("stale run transition") from exc
        raise
    record = get_run(run_id=run_id)
    if record is None:
        raise ValueError(f"Run {run_id} not found after update")
    return record


def item_to_run(item: dict[str, Any]) -> RunRecord:
    return RunRecord(
        run_id=item["run_id"], run_key=item.get("run_key"),
        workflow_id=item["workflow_id"],
        workflow_version=int(item["workflow_version"]), status=item["status"],
        revision=int(item.get("revision", 0)),
        current_step_id=item.get("current_step_id"),
        waiting_for_event_type=item.get("waiting_for_event_type"),
        last_event_id=int(item.get("last_event_id", 0)),
        started_at=datetime.fromisoformat(item["started_at"]),
        updated_at=datetime.fromisoformat(item["updated_at"]),
        input=json.loads(item.get("input_json", "{}")),
        result=json.loads(item["result_json"]) if item.get("result_json") else None,
        error=item.get("error"), tenant_id=item.get("tenant_id") or None,
    )
