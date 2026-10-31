"""GT-pool pollution guard tests (bd:python-factory-pfvo9 Q5).

The pipeline-f1 baseline (improvement) and drift (convergence) handlers must
ingest ONLY ground-truth F1 rewards (gt-findings / legacy empty source_id).
Quality (llm-judge), explicit feedback (user-feedback) and penalty signals
must NOT enter the GT metric pools.
"""

from __future__ import annotations

from factory.events.runtime.learning_handlers import (
    handle_convergence_check,
    handle_workflow_improvement,
)
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ok
from factory.metrics.mcp.contracts.operational import DriftOutput, RecordOutput


def _reward_event(source_id: str, score: float = 0.8):
    return Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "r1", "workflow_run_id": "wf1",
            "target_app": "App", "workflow_type": "chat",
            "domain_class": "wine-pairing", "score": score,
            "source_id": source_id,
        },
        principal_id="kiro-agent",
    )


def _recording_invoker(calls: list):
    def _invoke(tool: str, **kwargs):
        calls.append(tool)
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "metrics_record":
            return ok(RecordOutput(
                ok=True, metric_id=kwargs["metric_id"], value=0.0, timestamp=1.0))
        if tool == "metrics_detect_drift":
            return ok(DriftOutput(metric_id="pipeline-f1", drifted=False))
        return {}
    return _invoke


def test_convergence_skips_non_gt_sources() -> None:
    for src in ("llm-judge", "user-feedback"):
        calls: list = []
        out = handle_convergence_check(_reward_event(src), _recording_invoker(calls))
        assert out["skipped"] is True
        assert "metrics_record" not in calls  # never pollutes pipeline-f1


def test_improvement_skips_non_gt_sources() -> None:
    calls: list = []
    out = handle_workflow_improvement(_reward_event("user-feedback"), _recording_invoker(calls))
    assert out["skipped"] is True
    assert "storage_doc_find" not in calls  # never reads/writes the F1 baseline


def test_convergence_processes_gt_findings() -> None:
    calls: list = []
    handle_convergence_check(_reward_event("gt-findings"), _recording_invoker(calls))
    assert "metrics_record" in calls  # GT reward DOES feed pipeline-f1


def test_convergence_processes_legacy_empty_source() -> None:
    calls: list = []
    handle_convergence_check(_reward_event(""), _recording_invoker(calls))
    assert "metrics_record" in calls  # pre-seam payloads (no source_id) still flow
