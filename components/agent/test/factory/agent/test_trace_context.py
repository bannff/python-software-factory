"""Tests for bounded native Agent trace context projection."""
from factory.agent.runtime.trace_context import trace_attributes_from_context


def test_trace_context_preserves_distinct_ids_and_adds_agent_identity() -> None:
    attrs = trace_attributes_from_context({
        "run_id": "run-1", "workflow_run_id": "legacy-run",
        "trace_id": "trace-1", "span_id": "span-1",
        "parent_span_id": "parent-1", "session_id": "session-1",
        "payload": {"secret": "not copied"},
    }, agent_id="agent-1")

    assert attrs["run.id"] == "run-1"
    assert attrs["trace.id"] == "trace-1"
    assert attrs["span.id"] == "span-1"
    assert attrs["parent.span.id"] == "parent-1"
    assert attrs["session.id"] == "session-1"
    assert attrs["gen_ai.conversation.id"] == "session-1"
    assert attrs["agent.id"] == "agent-1"
    assert "payload" not in attrs


def test_trace_context_bounds_values_and_ignores_containers() -> None:
    attrs = trace_attributes_from_context({
        "run_id": "x" * 257, "trace_id": ["not", "scalar"],
    })

    assert attrs == {}
