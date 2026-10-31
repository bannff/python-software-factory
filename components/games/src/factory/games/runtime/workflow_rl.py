"""Per-workflow RL loop — scores and learns after each graph completes.

Returns a complete report dict suitable for experiment run reports.
All cross-brick calls go through MCP invoker.

Stage, planning, and event helpers live in ``_rl_stages``,
``_rl_planning``, and ``_rl_events`` and are re-exported at the bottom
of this module so test patch paths such as
``factory.games.runtime.workflow_rl._collect_findings`` remain valid.
"""
from __future__ import annotations

import logging
from typing import Any

from . import event_emitter  # noqa: F401 — re-exported for test patch paths
from ._rl_events import _emit_rl_event, _phase_outcome, _rl_payload

logger = logging.getLogger(__name__)


def _get_invoker() -> Any:
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def process_workflow_rl(
    graph_id: str, run_id: str, vuln_class: str = "",
    domain_class: str = "",
    count_labels: list[str] | None = None,
    taxonomy_edges: list[dict] | None = None,
    workflow_type: str = "auto", target_app: str = "",
    session_id: str = "", emit_lifecycle: bool = True,
    match_on: list[str] | None = None,
) -> dict[str, Any]:
    """Score a completed workflow, store learnings, return report.

    Args:
        graph_id: The graph that completed.
        run_id: Run identifier for finding lookup.
        vuln_class: Vulnerability class (IDOR, XSS, etc) — security default.
        domain_class: Domain-agnostic taxonomy bucket (bd:python-factory-twxj0).
            Coalesces with vuln_class for memory-tag dual-emit; both are
            forwarded into RL events untouched per the meta-architect Q4
            dual-emit verdict.
        count_labels: Optional override for ``_collect_findings`` label set
            (bd:python-factory-qer1z + python-factory-tmlrx). ``None`` uses
            the security ``("Finding","ProvenExploit")`` default.
        taxonomy_edges: Optional override forwarded to
            ``graph_graph_get_findings_for_run`` (bd:python-factory-ecph9).
            ``None`` keeps the CWE/OCSF security default.
        workflow_type: Cosmetic label for the run (persisted in events/reports).
            Defaults to "workflow" when "auto" or unset. No longer sniffed
            from graph_id.
        target_app: Target app name for GT filtering.
        session_id: Optional UI/session correlation id.
        emit_lifecycle: Emit RL lifecycle milestones when True.
        match_on: Rubric-sourced list of match keys for GT scoring
            (e.g. ["cwe","file"]). When None, scorer uses its own default.
    """
    invoker = _get_invoker()
    if not invoker:
        return {"skipped": True, "reason": "no invoker"}

    if workflow_type == "auto":
        workflow_type = "workflow"
    if not target_app:
        parts = run_id.split("-")
        target_app = parts[1] if len(parts) >= 2 else ""

    # bd:python-factory-twxj0 — coalesce so domain agents that only set
    # ``domain_class`` and security agents that only set ``vuln_class``
    # both produce useful memory tags + planning content.
    domain = domain_class or vuln_class

    ctx = {
        "graph_id": graph_id,
        "workflow_run_id": run_id,
        "vuln_class": vuln_class,
        "domain_class": domain_class,
        "workflow_type": workflow_type,
        "target_app": target_app,
        "session_id": session_id,
    }

    def emit(event_type: str, **extra: Any) -> None:
        _emit_rl_event(event_type, _rl_payload(**ctx, **extra), emit_lifecycle)

    emit("rl.started")

    try:
        findings = _collect_findings(
            invoker, run_id,
            count_labels=count_labels, taxonomy_edges=taxonomy_edges,
        )
        gt_entries = _load_gt(target_app)
        emit(
            "rl.findings.collected",
            findings_count=len(findings),
            gt_entries_count=len(gt_entries),
        )

        scoring = _score(invoker, findings, gt_entries, match_on=match_on)
        emit(
            "rl.scored",
            precision=scoring.get("precision", 0),
            recall=scoring.get("recall", 0),
            f1=scoring.get("f1", 0),
            true_positives=scoring.get("true_positives", 0),
            false_positives=scoring.get("false_positives_count", 0),
            false_negatives=scoring.get("false_negatives", 0),
        )

        # Best-effort sqlite persistence (idempotent re-runs via doc_id).
        try:
            invoker(
                "evals_evals_persist_score",
                run_id=run_id,
                workflow_type=workflow_type,
                target_app=target_app,
                vuln_class=vuln_class,
                domain_class=domain_class,
                scoring=scoring,
            )
        except Exception as exc:
            logger.warning("score persistence failed for run=%s: %s", run_id, exc)

        blockchain = _plan_reward(scoring)
        emit(
            "rl.reward.processed",
            outcome=_phase_outcome(blockchain, "minted"),
            minted=bool(blockchain.get("minted") or blockchain.get("eligible")),
            amount=blockchain.get("amount", 0),
            error_summary=blockchain.get("error") or blockchain.get("reason", ""),
        )

        memory = _plan_learning(
            scoring, run_id, vuln_class, workflow_type, target_app,
            domain_class=domain_class,
        )
        emit(
            "rl.memory.processed",
            outcome=_phase_outcome(memory, "stored"),
            stored=bool(memory.get("stored")),
            error_summary=memory.get("error") or memory.get("reason", ""),
        )

        report = _build_report(
            graph_id=graph_id, run_id=run_id, vuln_class=vuln_class,
            domain_class=domain_class,
            workflow_type=workflow_type, target_app=target_app,
            findings=findings, gt_entries=gt_entries, scoring=scoring,
            blockchain=blockchain, memory=memory,
            per_agent=_per_agent_summary(findings),
        )
        # bd:python-factory-hx5zc — surface resolved ground-truth count so the
        # gt-findings reward source can self-gate (abstain when NO ground truth,
        # NOT when findings==0 — a scan with GT + 0 detections is recall-0 signal).
        report["gt_entries_count"] = len(gt_entries)
        emit(
            "rl.completed",
            findings_count=len(findings),
            f1=report["scoring"]["f1"],
            minted=bool(blockchain.get("minted") or blockchain.get("eligible")),
            stored=bool(memory.get("stored")),
        )
        logger.info("RL [%s] %s run=%s: F1=%.2f TP=%d FP=%d (domain=%s)",
                    workflow_type, target_app, run_id,
                    report["scoring"]["f1"],
                    report["scoring"]["true_positives"],
                    report["scoring"]["false_positives"],
                    domain or "<none>")
        return report
    except Exception as exc:
        emit("rl.failed", failed_stage="workflow", error_summary=str(exc))
        raise


# Re-exports — moved helpers MUST remain accessible at this module path
# so test patch targets like ``factory.games.runtime.workflow_rl._collect_findings``
# stay valid.  Do not remove.
from ._rl_planning import _per_agent_summary, _plan_learning, _plan_reward  # noqa: E402,F401
from ._rl_stages import (  # noqa: E402,F401
    _CHALLENGES_DIR,
    _collect_findings,
    _load_gt,
    _score,
)
from ._rl_report import build_report as _build_report  # noqa: E402,F401
