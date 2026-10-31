"""Unified experiment report — metrics + per-finding detail from graph."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workflow_report_findings import build_findings_detail
from .workflow_report_graph import graph_counts
from .workflow_report_target import build_target_profile

logger = logging.getLogger(__name__)
_EXPERIMENTS_DIR = Path("projects/companion_x/challenges/experiments")


def _get_invoker() -> Any:
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


_EMPTY_GRAPH = {
    "suspected_vuln_count": 0, "finding_count": 0,
    "finding_verdicts": {}, "proven_exploit_count": 0,
    "endpoints_discovered": 0,
}


def _build_metrics(
    rl: dict, g: dict, run_id: str, wtype: str, app: str,
    vuln: str, fw: str, agents: int, models: list[str],
    dur: float, x: dict,
) -> dict[str, Any]:
    """Assemble experiment_metrics per the canonical schema."""
    s = rl.get("scoring", {})
    bc = rl.get("blockchain", {})
    vd = g.get("finding_verdicts", {})
    return {
        "meta": {
            "run_id": run_id, "workflow_type": wtype, "target_app": app,
            "vuln_class": vuln, "framework": fw,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline": rl.get("workflow_type", "unknown"),
            "tokens_source": x.get("tokens_source", "unavailable"),
        },
        "time": {
            "total_duration_seconds": dur,
            "per_phase_seconds": x.get("per_phase_seconds", {}),
            "time_to_first_finding_seconds": x.get("time_to_first_finding_seconds", 0),
            "avg_phase_duration_seconds": x.get("avg_phase_duration_seconds", 0.0),
        },
        "scale": {
            "endpoints_discovered": g.get("endpoints_discovered", 0),
            "files_scanned": x.get("files_scanned", 0),
            "lines_of_code": x.get("lines_of_code", 0),
        },
        "params": x.get("params", {"total": 0, "user_controlled": 0,
                                    "subject_derived": 0, "system": 0}),
        "taint": x.get("taint", {"traces_executed": 0, "sink_reached": 0,
                                  "auth_gap": 0, "avg_hop_count": 0.0}),
        "findings": {
            "raw_before_dedup": g.get("suspected_vuln_count", 0),
            "after_dedup": g.get("finding_count", 0),
            "confirmed": vd.get("CONFIRMED", 0),
            "needs_review": vd.get("NEEDS_REVIEW", 0),
            "rejected": vd.get("REJECTED", 0), "novel": x.get("novel_findings", 0),
            "avg_confidence_score": x.get("avg_confidence_score", 0.0),
            "with_taint_trace": x.get("with_taint_trace", 0),
            "with_attack_chain": x.get("with_attack_chain", 0),
            "with_dynamic_proof": g.get("proven_exploit_count", 0),
        },
        "scoring": {
            "precision": s.get("precision", 0.0), "recall": s.get("recall", 0.0),
            "f1": s.get("f1", 0.0), "true_positives": s.get("true_positives", 0),
            "false_positives": s.get("false_positives", 0),
            "false_negatives": s.get("false_negatives", 0),
        },
        "dynamic_verification": x.get("dynamic_verification", {
            "verified_finding": 0, "verification_failed": 0, "not_tested": 0,
            "sast_predictions_confirmed": 0, "sast_predictions_total": 0,
            "sast_correlation_rate": 0.0}),
        "tokens": x.get("tokens", {"total_tokens": 0, "input_tokens": 0,
                                    "output_tokens": 0, "per_agent_tokens": {}}),
        "tool_calls": x.get("tool_calls", {"total": 0, "per_tool": {}, "errors": 0}),
        "agents": {"agent_count": agents, "models_used": models,
                   "cycles_total": x.get("cycles_total", 0)},
        "cost": {
            "estimated_usd": x.get("estimated_usd", 0.0),
            "per_agent_usd": x.get("per_agent_usd", {}),
            "model_pricing_source": x.get("model_pricing_source", "unavailable"),
        },
        "blockchain": {"tokens_minted": bc.get("amount", 0.0),
                       "reward_reason": f"RL:{vuln}:{run_id}"},
        "memory": {
            "learnings_stored": 1 if rl.get("memory", {}).get("stored") else 0,
            "learnings_retrieved": x.get("learnings_retrieved", 0),
            "kb_queries": x.get("kb_queries", 0),
            "graph_queries": x.get("graph_queries", 0),
        },
    }


def _record_metrics(invoker: Any, metrics: dict[str, Any]) -> None:
    """Batch-record all numeric metrics via the metrics brick."""
    flat = [
        {"metric_id": f"{sec}-{k}", "value": v}
        for sec, vals in metrics.items() if sec != "meta" and isinstance(vals, dict)
        for k, v in vals.items() if isinstance(v, (int, float))
    ]
    if flat:
        try:
            result = invoker("metrics_record_batch", records=flat)
            if not getattr(result, "ok", True) or getattr(result, "data", object()) is None:
                raise RuntimeError(getattr(result, "error", "metrics record batch failed"))
        except Exception as e:
            logger.warning("metrics_record_batch failed: %s", e)


def write_experiment_report(
    rl_report: dict[str, Any], run_id: str,
    workflow_type: str = "kiro", target_app: str = "",
    vuln_class: str = "", framework: str = "",
    agent_count: int = 0, models_used: list[str] | None = None,
    duration_seconds: float = 0, extra_metrics: dict[str, Any] | None = None,
    domain_class: str = "",
    count_labels: list[str] | None = None,
    taxonomy_edges: list[dict] | None = None,
) -> dict[str, Any]:
    """Assemble, record, and persist a unified experiment report.

    ``domain_class`` (bd:python-factory-twxj0) is dual-emitted with
    ``vuln_class`` in both the report root and the metrics block per the
    meta-architect Q4 verdict. ``count_labels`` and ``taxonomy_edges``
    (bd:python-factory-tmlrx + python-factory-st587) thread through to
    ``graph_counts`` and ``build_findings_detail`` so domain agents can
    drive both label sets and Cypher-shape via per-call config.
    """
    invoker = _get_invoker()
    extra = extra_metrics or {}
    if invoker:
        graph = graph_counts(
            invoker, run_id,
            count_labels=count_labels, taxonomy_edges=taxonomy_edges,
        )
    else:
        graph = dict(_EMPTY_GRAPH)
    metrics = _build_metrics(
        rl_report, graph, run_id, workflow_type, target_app,
        vuln_class, framework, agent_count, models_used or [],
        duration_seconds, extra,
    )
    # Dual-emit domain_class onto the metrics meta block (bd:python-factory-twxj0).
    metrics["meta"]["domain_class"] = domain_class
    if invoker:
        _record_metrics(invoker, metrics)
    fd = build_findings_detail(
        invoker, run_id,
        count_labels=count_labels, taxonomy_edges=taxonomy_edges,
    ) if invoker else {}
    target_profile = build_target_profile(invoker, target_app, run_id) if invoker else {}
    report = {
        "run_id": run_id, "workflow_type": workflow_type,
        "target_app": target_app, "vuln_class": vuln_class,
        "domain_class": domain_class,
        "timestamp": metrics["meta"]["timestamp"],
        "experiment_metrics": metrics,
        "target_profile": target_profile,
        "findings": fd.get("findings", []),
        "finding_categories": fd.get("finding_categories", {}),
        "dynamic_verification_summary": fd.get(
            "dynamic_verification_summary", {}),
        "pipeline_execution_summary": extra.get(
            "pipeline_execution_summary", {}),
        "tooling_observations": extra.get("tooling_observations", []),
        "rl_report": rl_report, "graph_counts": graph,
    }
    _EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out = _EXPERIMENTS_DIR / f"{run_id}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    logger.info("Experiment report written: %s", out)
    return report
