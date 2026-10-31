import pytest

from factory.mcp_utils.context import reset_envelope, set_envelope
from factory.mcp_utils.correlation import (
    build_event_publish_input, merge_correlation_fields, normalize_correlation,
)


def test_normalize_correlation_promotes_ingress_alias_without_emitting_it() -> None:
    correlation = normalize_correlation({"workflow_run_id": "run-123", "env_id": "env-1"})
    assert correlation["run_id"] == "run-123"
    assert "workflow_run_id" not in correlation
    assert correlation["correlation_id"] == "run-123"


def test_merge_correlation_fields_uses_nested_config() -> None:
    merged = merge_correlation_fields({"game_id": "game-1", "config": {"graph_id": "graph-1", "target_app": "WebGoat"}})
    assert merged["game_id"] == "game-1"
    assert merged["graph_id"] == "graph-1"
    assert merged["target_app"] == "WebGoat"
    assert merged["correlation_id"] == "graph-1"


def test_build_event_publish_input_sets_request_id_and_attributes() -> None:
    publish_input = build_event_publish_input({"game_id": "game-1", "run_id": "run-1"})
    assert publish_input["request_id"] == "run-1"
    assert publish_input["payload"]["correlation_id"] == "run-1"
    assert publish_input["attributes"]["game_id"] == "game-1"


def test_ambient_authority_is_first_wins_for_identity_and_trace_fields() -> None:
    token = set_envelope({
        "tenant_id": "trusted", "run_id": "run-1", "trace_id": "trace-1",
        "tracestate": "vendor=trusted",
    })
    try:
        merged = merge_correlation_fields({
            "tenant_id": "attacker", "run_id": "run-1", "trace_id": "trace-2",
            "tracestate": "vendor=attacker",
        })
        assert merged["tenant_id"] == "trusted"
        assert merged["run_id"] == "run-1"
        assert merged["trace_id"] == "trace-1"
        assert merged["tracestate"] == "vendor=trusted"
    finally:
        reset_envelope(token)


def test_conflicting_run_sources_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting run_id/workflow_run_id"):
        normalize_correlation({"run_id": "run-1", "config": {"workflow_run_id": "run-2"}})


def test_explicit_run_authority_preserves_context_without_blending_caller_run() -> None:
    token = set_envelope({
        "run_id": "ambient-caller", "correlation_id": "caller-correlation",
    })
    try:
        correlation = normalize_correlation(
            {"workflow_run_id": "source-caller", "session_id": "session-1"},
            authoritative_run_id="wfr:v1:durable",
        )
    finally:
        reset_envelope(token)

    assert correlation["run_id"] == "wfr:v1:durable"
    assert correlation["correlation_id"] == "caller-correlation"
    assert correlation["session_id"] == "session-1"
    assert "workflow_run_id" not in correlation


def test_trace_id_span_id_and_tracestate_remain_distinct() -> None:
    correlation = normalize_correlation({
        "trace_id": "trace-1", "span_id": "span-1", "tracestate": "vendor=value",
        "workflow_run_id": "run-1",
    })
    assert correlation["trace_id"] == "trace-1"
    assert correlation["span_id"] == "span-1"
    assert correlation["tracestate"] == "vendor=value"
    assert correlation["run_id"] == "run-1"
    assert correlation["trace_id"] != correlation["correlation_id"]


def test_build_event_publish_input_ambient_run_owns_derived_correlation() -> None:
    token = set_envelope({"run_id": "trusted-run"})
    try:
        publish_input = build_event_publish_input({
            "correlation_id": "attacker-correlation",
            "request_id": "attacker-request",
            "config": {"request_id": "nested-attacker"},
        })
    finally:
        reset_envelope(token)

    assert publish_input["request_id"] == "trusted-run"
    assert publish_input["payload"]["correlation_id"] == "trusted-run"
    assert publish_input["payload"]["request_id"] == "trusted-run"
    assert publish_input["attributes"]["correlation_id"] == "trusted-run"
