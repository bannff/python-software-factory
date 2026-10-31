"""Durable Workflow dispatch of one attested dev-loop cycle reward."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from factory.mcp_utils.interface import get_service, protected_canonical_json

_EVENT = "system.dev_loop_reward_dispatched"


def dispatch_cycle_reward(store: Any, loop: Any, cycle: Any, run: Any) -> bool:
    if any(event.event_type == _EVENT for event in store.get_events_since(
        run_id=run.run_id, after_event_id=0,
    )):
        return True
    output = cycle.summary or f"Cycle {cycle.cycle} completed without a summary."
    cycle_id = f"{loop.loop_id}:{cycle.cycle}"
    report_digest = hashlib.sha256(protected_canonical_json({
        "cycle_id": cycle_id, "disposition": str(cycle.disposition.value),
        "summary": output, "run_id": run.run_id,
    })).hexdigest()
    material = {
        "loop_id": loop.loop_id, "cycle_id": cycle_id,
        "workflow_run_id": run.run_id, "report_digest": report_digest,
        "input_summary": loop.objective, "output_summary": output,
    }
    payload_digest = hashlib.sha256(protected_canonical_json(material)).hexdigest()
    binding = {
        "tenant_id": loop.tenant_id, "owner_id": loop.owner_id,
        "event_type": "dev_loop.cycle.completed", "subject_id": cycle_id,
        "revision": cycle.revision, "payload_digest": payload_digest,
    }
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        return False
    raw = invoke(
        {"brick_name": "events", "tool_name": "events_score_dev_loop_cycle"},
        arguments={**binding, **material},
        idempotency_key=f"dev-loop-reward:{cycle_id}:{cycle.revision}",
        envelope=loop.initiation_envelope.model_dump(mode="json"),
        projection=binding,
    )
    structured = raw.get("result", {}).get("structured_content") \
        if isinstance(raw, dict) else None
    data = structured.get("data") \
        if isinstance(structured, dict) and structured.get("ok") else None
    if not isinstance(data, dict):
        return False
    reward = data.get("reward") if isinstance(data.get("reward"), dict) else {}
    receipt = hashlib.sha256(protected_canonical_json({
        "cycle_id": cycle_id, "scored": bool(data.get("scored")),
        "reward_key": reward.get("idempotency_key", ""),
        "error": data.get("error", ""),
    })).hexdigest()
    store.append_event(
        run_id=run.run_id, event_type=_EVENT,
        payload={"cycle_id": cycle_id, "receipt_digest": receipt},
        envelope=run.initiation_envelope, now=datetime.now(timezone.utc),
    )
    return True


def reconcile_cycle_rewards(store: Any, limit: int = 100) -> tuple[str, ...]:
    dispatched = []
    from .loop_models import CycleState
    for cycle in store.list_cycles(CycleState.SETTLED, limit):
        loop = store.get_loop(cycle.tenant_id, cycle.owner_id, cycle.loop_id)
        run = store.get_run(run_id=cycle.workflow_run_id or "")
        if loop is not None and run is not None \
                and dispatch_cycle_reward(store, loop, cycle, run):
            dispatched.append(run.run_id)
    return tuple(dispatched)


__all__ = ["dispatch_cycle_reward", "reconcile_cycle_rewards"]
