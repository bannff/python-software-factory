"""Memory learning summary handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..learning_contracts import validate_learning_payload
from ..mcp_result import legacy_memory_record, successful_data
from ..models import Event
from ._common import _already_published, _base_payload, _publish


def handle_memory_learning(event: Event, invoker: Any) -> dict[str, Any]:
    """Persist a distilled learning summary from a computed reward."""
    payload = event.payload
    identity = payload.get("reward_identity") or (
        payload.get("workflow_run_id") or payload.get("run_id")
    )
    idempotency_key = f"memory:{identity}:workflow_rl"
    if _already_published(invoker, "memory.learning_stored", idempotency_key):
        return {
            **_base_payload(event),
            "status": "stored",
            "summary_type": "workflow_rl",
            "idempotency_key": idempotency_key,
            "deduped": True,
        }

    content = _build_learning_content(payload)
    workflow_id = payload.get("workflow_id") or payload.get("graph_id", "")
    # bd:python-factory-7ut47 — coalesce so domain agents (which set
    # ``domain_class``) and security recipes (which set ``vuln_class``) both
    # produce a useful tag prefix on the stored memory entry.
    domain = payload.get("domain_class") or payload.get("vuln_class", "")
    memory_result = invoker(
        "memory_memory_store",
        content=content,
        user_id=payload.get("principal_id") or "kiro-agent",
        memory_type="long_term",
        category="fact",
        metadata={
            "run_id": payload.get("run_id", ""),
            "workflow_run_id": payload.get("workflow_run_id", payload.get("run_id", "")),
            "graph_id": workflow_id,
            "workflow_id": workflow_id,
            "workflow_type": payload.get("workflow_type", "auto"),
            "target_app": payload.get("target_app", ""),
            "vuln_class": payload.get("vuln_class", ""),
            "domain_class": payload.get("domain_class", ""),
            # bd:python-factory-3oxx0 — verdict lets recall/audit distinguish a
            # cautionary "avoid" learning from a positive one.
            "verdict": payload.get("verdict", ""),
            "tags": [
                domain,
                f"{payload.get('workflow_type', 'auto')}-learnings",
                f"{domain}-learnings" if domain else "",
                payload.get("run_id", ""),
                payload.get("target_app", ""),
            ],
        },
        idempotency_key=idempotency_key,
    )
    memory = successful_data(memory_result, reject_data_error=False)
    stored_memory = None
    has_memory_error = isinstance(memory, Mapping) and memory.get("error") is not None
    if (
        isinstance(memory, Mapping)
        and memory.get("stored") is True
        and not has_memory_error
    ):
        stored_memory = legacy_memory_record(memory.get("memory"))
    if stored_memory is None:
        stored_memory = legacy_memory_record(memory_result)
    if stored_memory is None:
        error = getattr(memory_result, "error", None)
        if not isinstance(error, str) and isinstance(memory_result, Mapping):
            error = memory_result.get("error")
            if not isinstance(error, str):
                data = memory_result.get("data")
                error = data.get("error") if isinstance(data, Mapping) else None
        if not isinstance(error, str) and isinstance(memory, Mapping):
            error = memory.get("error")
        fallback = "memory_store_failed" if memory is None else "memory_not_stored"
        return {"skipped": True, "error": error or fallback}
    memory_id = stored_memory.get("id")
    if not isinstance(memory_id, str) or not memory_id:
        return {"skipped": True, "error": "memory_not_stored"}

    derived_payload = {
        **_base_payload(event),
        "status": "stored",
        "memory_id": memory_id,
        "summary_type": "workflow_rl",
        "idempotency_key": idempotency_key,
    }
    derived_payload = validate_learning_payload("memory.learning_stored", derived_payload)
    _publish(invoker, event, "memory.learning_stored", derived_payload)
    return derived_payload


def _build_learning_content(payload: dict[str, Any]) -> str:
    # bd:python-factory-3oxx0 — when an explicit signal carried corrective
    # SUBSTANCE (the down-voted answer text in provenance.feedback_text), store
    # it with AVOID/GOOD framing so recall semantically matches a future
    # question and the LLM self-corrects in-context. Otherwise fall back to the
    # metrics scoreboard (byte-identical for GT / workflow runs).
    prov = payload.get("provenance") or {}
    feedback_text = str(prov.get("feedback_text") or "").strip()
    if feedback_text:
        verdict = payload.get("verdict", "")
        framing = (
            "AVOID — the user down-voted this answer; do not repeat it"
            if verdict == "penalized"
            else "GOOD — the user up-voted this answer"
        )
        return f"{framing}:\n{feedback_text}"
    # bd:python-factory-7ut47 — content prefix uses domain_class with fallback
    # so domain-agnostic recipes get a meaningful summary line.
    domain = payload.get("domain_class") or payload.get("vuln_class", "")
    return (
        f"RL [{payload.get('workflow_type', 'auto')}] "
        f"{domain} {payload.get('target_app', '')} "
        f"run={payload.get('run_id', '')}: "
        f"F1={float(payload.get('score', 0) or 0):.2f} "
        f"P={float(payload.get('precision', 0) or 0):.2f} "
        f"R={float(payload.get('recall', 0) or 0):.2f} "
        f"TP={int(payload.get('true_positives', 0) or 0)} "
        f"FP={int(payload.get('false_positives', 0) or 0)} "
        f"FN={int(payload.get('false_negatives', 0) or 0)}"
    )
