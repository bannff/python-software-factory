"""Workflow run-start persistence and integration events."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .envelope import Envelope
from .event_emitter import emit as emit_workflow_event
from .graph_sync import sync_run, workflow_entity_id
from .models import WorkflowDefinition
from .ports import WorkflowStorage


def announce_start(
    storage: WorkflowStorage, workflow: WorkflowDefinition, record: Any,
    input: dict[str, Any], envelope: Envelope, now: datetime,
) -> None:
    sync_run(
        record.model_dump(mode="json"), input, envelope.model_dump(mode="json"),
        {"workflow_name": workflow.name, "workflow_type": workflow.name,
         "entity_id": workflow_entity_id(record.run_id)},
    )
    storage.append_event(
        run_id=record.run_id, event_type="system.run_started",
        payload={"workflow_id": workflow.id, "workflow_version": workflow.version,
                 "run_key": record.run_key}, envelope=envelope, now=now,
    )
    emit_workflow_event(
        "workflow.run_started",
        {"run_id": record.run_id, "run_key": record.run_key,
         "entity_id": workflow_entity_id(record.run_id),
         "workflow_id": workflow.id, "workflow_name": workflow.name,
         "workflow_version": workflow.version, "status": record.status,
         "tenant_id": envelope.tenant_id}, input, envelope.model_dump(mode="json"),
    )
