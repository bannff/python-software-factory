"""Workflow-owned startup reconciliation for background execution runs."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from .envelope import Envelope


def schedule_background_recovery(
    runtime: Any,
    submit: Callable[[Coroutine[Any, Any, Any]], None],
) -> tuple[str, ...]:
    """Schedule each active background run once; durable claims fence races."""
    candidates = []
    cursor = None
    while True:
        records, cursor = runtime.storage.list_runs(
            tenant_id=None, workflow_id=None, status=None,
            limit=200, cursor=cursor,
        )
        candidates.extend(
            record for record in records
            if _is_background(record) and not _completion_recorded(runtime, record.run_id)
        )
        if cursor is None:
            break
    for record in candidates:
        envelope = Envelope.model_validate(
            record.initiation_envelope.model_dump(mode="json"),
        )
        submit(_resume(runtime, record.run_id, envelope))
    return tuple(record.run_id for record in candidates)


async def _resume(runtime: Any, run_id: str, envelope: Envelope) -> None:
    await asyncio.to_thread(
        runtime.resume_run, run_id=run_id, envelope=envelope,
    )


def _is_background(record: Any) -> bool:
    metadata = record.input.get("launch_metadata", {})
    return isinstance(metadata, dict) and metadata.get("kind") == "background_subagent"


def _completion_recorded(runtime: Any, run_id: str) -> bool:
    return any(
        event.event_type == "system.background_completion_recorded"
        for event in runtime.storage.get_events_since(run_id=run_id, after_event_id=0)
    )


__all__ = ["schedule_background_recovery"]
