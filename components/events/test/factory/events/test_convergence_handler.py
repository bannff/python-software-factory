"""Tests for the convergence learning handler."""
from __future__ import annotations

from factory.events.runtime.learning_handlers import handle_convergence_check
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ok
from factory.metrics.mcp.contracts.operational import DriftOutput, RecordOutput


def _payload(**overrides):
    base = {
        "run_id": "run-x", "workflow_run_id": "wf-x", "graph_id": "rt-scan-idor",
        "target_app": "WebGoat", "workflow_type": "dast", "vuln_class": "IDOR",
        "score": 0.82, "precision": 0.8, "recall": 0.84, "true_positives": 4,
        "false_positives": 1, "false_negatives": 2, "reward_value": 12,
    }
    base.update(overrides)
    return base


def _record(metric_id: str) -> object:
    return ok(RecordOutput(ok=True, metric_id=metric_id, value=0.0, timestamp=1.0))


def _drift(*, drifted: bool, **values: object) -> object:
    return ok(DriftOutput(metric_id="pipeline-f1", drifted=drifted, **values))


def test_convergence_records_metrics_and_emits_when_no_drift() -> None:
    """A concrete successful ToolResult[DriftOutput] can converge."""
    published: list[tuple[str, dict]] = []
    recorded: list[str] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "metrics_record":
            recorded.append(kwargs["metric_id"])
            return _record(kwargs["metric_id"])
        if tool_name == "metrics_detect_drift":
            return _drift(drifted=False, baseline_mean=0.7, current_mean=0.71)
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-convergence"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    result = handle_convergence_check(
        Event(source="events.rewards", type="reward.computed", payload=_payload()), fake_invoker
    )

    assert result["metrics_recorded"] == 7
    assert recorded[0] == "pipeline-f1"
    assert published[0][0] == "convergence.checked"
    assert published[0][1]["converged"] is True


def test_convergence_marks_drifted_envelope_as_not_converged() -> None:
    published: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "metrics_record":
            return _record(kwargs["metric_id"])
        if tool_name == "metrics_detect_drift":
            return _drift(drifted=True, baseline_mean=0.7, current_mean=0.4)
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-convergence"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    handle_convergence_check(
        Event(source="events.rewards", type="reward.computed",
              payload=_payload(run_id="run-456", workflow_run_id="wf-456", score=0.4)),
        fake_invoker,
    )
    assert published[0][1]["converged"] is False


def test_convergence_treats_insufficient_data_envelope_as_not_converged() -> None:
    published: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "metrics_record":
            return _record(kwargs["metric_id"])
        if tool_name == "metrics_detect_drift":
            return _drift(drifted=False, reason="insufficient_data")
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-convergence"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    handle_convergence_check(
        Event(source="events.rewards", type="reward.computed", payload=_payload()), fake_invoker
    )
    assert published[0][1]["converged"] is False


def test_convergence_unwraps_drift_output_fields() -> None:
    """Drift fields are converted to a plain dict before convergence reads them."""
    published: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "metrics_record":
            return _record(kwargs["metric_id"])
        if tool_name == "metrics_detect_drift":
            return _drift(drifted=True, regression_signal="block", baseline_tag="v1.0")
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-convergence"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    handle_convergence_check(
        Event(source="events.rewards", type="reward.computed", payload=_payload()), fake_invoker
    )
    assert published[0][1]["regression_signal"] == "block"
    assert published[0][1]["baseline_tag"] == "v1.0"
    assert published[0][1]["converged"] is False


def test_metrics_detect_drift_contract_returns_drifted_key() -> None:
    """The runtime's drift payload retains the key consumed by DriftOutput."""
    from factory.metrics.interface import default_runtime

    runtime = default_runtime()
    runtime.record("test-pipeline-f1", 0.7, labels={"run_id": "test-baseline"})
    runtime.record("test-pipeline-f1", 0.71, labels={"run_id": "test-current"})
    drift = runtime.detect_drift("test-pipeline-f1", baseline_period="7d", current_period="24h")
    assert "drifted" in drift
    assert isinstance(drift["drifted"], bool)
    assert "drift_detected" not in drift
