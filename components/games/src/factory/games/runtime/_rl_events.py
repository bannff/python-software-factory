"""RL pipeline event emission helpers.

Extracted from ``workflow_rl`` to keep that module under the 200 LOC
budget once domain-class threading lands (bd:python-factory-tmlrx).
Re-exported from ``workflow_rl`` so that test patch paths such as
``factory.games.runtime.workflow_rl._emit_rl_event`` continue to resolve.
"""
from __future__ import annotations

from typing import Any

from . import event_emitter


def _emit_rl_event(event_type: str, payload: dict[str, Any], enabled: bool) -> None:
    """Forward an RL lifecycle event onto the local event emitter."""
    if enabled:
        event_emitter.emit(event_type, payload)


def _rl_payload(
    *,
    graph_id: str,
    workflow_run_id: str,
    vuln_class: str,
    workflow_type: str,
    target_app: str,
    session_id: str = "",
    domain_class: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build the canonical RL event payload.

    ``domain_class`` (bd:python-factory-twxj0) is dual-emitted alongside
    ``vuln_class`` so security recipes (which key off ``vuln_class``) and
    domain-agnostic recipes (which key off ``domain_class``) both receive
    a fully-populated payload. The two MAY diverge — e.g.
    ``domain_class="security_idor"`` paired with ``vuln_class="IDOR"`` —
    per the meta-architect Q2 verdict; no mismatch validation here.
    """
    payload: dict[str, Any] = {
        "graph_id": graph_id,
        "workflow_run_id": workflow_run_id,
        "workflow_type": workflow_type,
        "target_app": target_app,
        "vuln_class": vuln_class,
        "domain_class": domain_class,
    }
    if session_id:
        payload["session_id"] = session_id
    payload.update(extra)
    return payload


def _phase_outcome(result: dict[str, Any], success_key: str) -> str:
    """Map a per-phase result dict to a coarse ``rl.*.processed`` outcome."""
    if result.get(success_key):
        return "completed"
    if result.get("status") == "pending_event":
        return "queued"
    if result.get("error"):
        return "failed"
    return "skipped"
