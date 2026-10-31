"""Workflow reconciliation of scheduled loop cycles and child outcomes."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import get_service, protected_canonical_json

from .loop_models import (
    CycleDisposition, CycleState, LoopCycleReport, LoopState,
)
from .loop_sentinel import sentinel_exists

_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


async def reconcile_cycles(
    store: Any, allowed_root: Path, limit: int = 100,
) -> tuple[str, ...]:
    settled = []
    for cycle in store.list_cycles(CycleState.SCHEDULED, limit):
        loop = store.get_loop(cycle.tenant_id, cycle.owner_id, cycle.loop_id)
        if loop is None or loop.state is not LoopState.ACTIVE:
            continue
        fire = await _scheduler_fire(loop, cycle)
        run_id = fire.get("workflow_run_id") if isinstance(fire, dict) else None
        if isinstance(run_id, str):
            store.set_cycle_state(cycle, CycleState.RUNNING, run_id, cycle.revision)
    for cycle in store.list_cycles(CycleState.RUNNING, limit):
        loop = store.get_loop(cycle.tenant_id, cycle.owner_id, cycle.loop_id)
        run = store.get_run(run_id=cycle.workflow_run_id or "")
        if loop is None or run is None or run.status not in _TERMINAL:
            continue
        _verify_child(loop, cycle, run)
        disposition, summary, blocker_digest = _outcome(loop, run)
        stopped = sentinel_exists(loop.loop_id, Path(loop.project_root), allowed_root)
        settlement = store.settle_cycle(
            loop, cycle, disposition, summary, blocker_digest, stopped,
        )
        if settlement is not None:
            _updated_loop, settled_cycle, _following_cycle = settlement
            from .projection_events import emit_run_projection
            emit_run_projection(
                tenant_id=loop.tenant_id, owner_id=loop.owner_id,
                run_id=cycle.workflow_run_id or "",
                session_id=loop.origin_session_id,
                revision=settled_cycle.revision, status=disposition.value,
                envelope=loop.initiation_envelope.model_dump(mode="json"),
            )
            from .dev_loop_reward import dispatch_cycle_reward
            dispatch_cycle_reward(store, loop, settled_cycle, run)
            settled.append(cycle.workflow_run_id or "")
    from .loop_observability import project_blockers
    await project_blockers(store, limit)
    from .dev_loop_reward import reconcile_cycle_rewards
    reconcile_cycle_rewards(store, limit)
    return tuple(settled)


async def _scheduler_fire(loop: Any, cycle: Any) -> dict[str, Any]:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("workflow Scheduler MCP unavailable")
    envelope = loop.initiation_envelope.model_dump(mode="json")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "scheduler", "tool_name": "scheduler_get_fire"},
        arguments={
            "schedule_id": cycle.schedule_id, "fire_sequence": 1,
            "envelope": envelope,
        }, idempotency_key=f"workflow-loop-fire:{loop.loop_id}:{cycle.cycle}",
        envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    fire = data.get("fire") if isinstance(data, dict) else None
    return fire if isinstance(fire, dict) else {}


def _verify_child(loop: Any, cycle: Any, run: Any) -> None:
    envelope = run.initiation_envelope
    metadata = run.input.get("launch_metadata", {})
    valid = (
        run.tenant_id == loop.tenant_id
        and envelope.tenant_id == loop.tenant_id
        and envelope.principal_id == loop.owner_id
        and isinstance(metadata, dict)
        and metadata.get("kind") == "workflow_loop_cycle"
        and metadata.get("loop_id") == loop.loop_id
        and metadata.get("loop_cycle") == str(cycle.cycle)
    )
    if not valid:
        raise RuntimeError("loop child authority mismatch")


def _outcome(loop: Any, run: Any) -> tuple[CycleDisposition, str, str | None]:
    if run.status != "succeeded":
        return CycleDisposition.FAILED, (run.error or f"child {run.status}")[:32_768], None
    value = ((run.result or {}).get("task_result") or {}).get("result")
    outputs = value.get("structured_outputs") if isinstance(value, dict) else None
    payload = outputs.get(loop.agent_id) if isinstance(outputs, dict) else None
    try:
        report = LoopCycleReport.model_validate(payload)
    except Exception:
        return CycleDisposition.FAILED, "loop child structured report invalid", None
    disposition = CycleDisposition(report.disposition)
    digest = None
    if disposition is CycleDisposition.BLOCKED:
        digest = hashlib.sha256(protected_canonical_json({
            "summary": report.summary, "blocker": report.blocker or "",
        })).hexdigest()
    return disposition, report.summary, digest


__all__ = ["reconcile_cycles"]
