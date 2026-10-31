"""Telemetry → reward handler tests (bd:python-factory-hv5rv).

Runs the REAL learning runtime (telemetry source) behind the handler; only
events_query/publish are stubbed.
"""

from __future__ import annotations

from factory.events.runtime.telemetry_handler import handle_telemetry_reward
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult, set_service
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.adapters.telemetry import TelemetryRewardSource


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def _invoker(published: list):
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(TelemetryRewardSource())
    runtime = LearningRuntime(reg)

    def _invoke(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            run_ctx = {
                "graph_id": kwargs.get("graph_id", ""),
                "run_id": kwargs.get("run_id", ""),
                "domain_class": kwargs.get("domain_class", ""),
                "workflow_type": kwargs.get("workflow_type", "auto"),
                "tool_error_rate": kwargs.get("tool_error_rate"),
            }
            return ToolResult(
                ok=True, data=runtime.compute(run_ctx, None),
            ).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    return _invoke


def _metrics_event(error_rate, run_id="run-1", domain="idor"):
    return Event(
        source="events.auto-metrics", type="metrics.record",
        payload={"run_id": run_id, "workflow_run_id": run_id,
                 "domain_class": domain, "tool_error_rate": error_rate},
        principal_id="kiro-agent",
    )


def test_telemetry_penalizes_a_failing_run() -> None:
    published: list = []
    result = handle_telemetry_reward(_metrics_event(0.5), _invoker(published))
    reward = result["reward"]
    assert reward["source_id"] == "telemetry"
    assert reward["verdict"] == "penalized"
    assert reward["reward_value"] == 0.0           # never mints
    et, payload = published[0]
    assert et == "reward.computed"
    # Source-scoped idempotency key avoids colliding with the gt reward.
    assert payload["idempotency_key"].endswith(":telemetry")
    assert payload["domain_class"] == "idor"       # tags {idor}-learnings


def test_telemetry_clean_run_abstains() -> None:
    published: list = []
    result = handle_telemetry_reward(_metrics_event(0.0), _invoker(published))
    assert result["skipped"] is True
    assert published == []


def test_telemetry_missing_rate_skips() -> None:
    published: list = []
    result = handle_telemetry_reward(_metrics_event(None), _invoker(published))
    assert result["skipped"] is True
    assert published == []
