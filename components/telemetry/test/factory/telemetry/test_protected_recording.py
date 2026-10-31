"""Canaries for telemetry redaction at direct recording boundaries."""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.telemetry.runtime.runtime import TelemetryRuntime


@pytest.fixture
def runtime(tmp_path: Path) -> TelemetryRuntime:
    config = tmp_path / "config"
    (config / "metrics").mkdir(parents=True)
    (config / "exporters").mkdir(parents=True)
    (config / "settings.yaml").write_text(
        """service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: false
  metrics_enabled: false
  logging_enabled: false
authoring:
  enabled: false
"""
    )
    engine = TelemetryRuntime(config_dir=config)
    engine.initialize()
    return engine


def test_sanitizes_nested_body_and_subject_before_metric_and_span(
    runtime: TelemetryRuntime,
) -> None:
    metric_attributes: list[dict] = []
    span_attributes: list[dict] = []

    class Counter:
        def add(self, value, attributes):
            metric_attributes.append(attributes)

    class Span:
        def set_attribute(self, key, value):
            pass

        def set_status(self, status):
            pass

    class SpanContext:
        def __enter__(self):
            return Span()

        def __exit__(self, *args):
            return False

    class Tracer:
        def start_as_current_span(self, name, attributes):
            span_attributes.append(attributes)
            return SpanContext()

    runtime._instruments["counter_tool_invocations"] = Counter()
    runtime._tracer = Tracer()
    canary = "tool-invocation-protected@example.test"
    runtime.record_tool_invocation(
        tool_name="mail.send", workflow_id="wf-1", success=True,
        latency_ms=None,
        trace_attributes={"body": canary, "nested": {"subject": canary}},
    )

    for attributes in metric_attributes + span_attributes:
        assert attributes["body"] == "[protected]"
        assert attributes["nested"]["subject"] == "[protected]"
        assert canary not in repr(attributes)


def test_direct_tool_attributes_drop_exception_text_and_cover_aliases(
    runtime: TelemetryRuntime,
) -> None:
    captured: list[dict] = []

    class Counter:
        def add(self, value, attributes):
            captured.append(attributes)

    runtime._instruments["counter_tool_invocations"] = Counter()
    canary = "direct-telemetry-exception@example.test"
    runtime.record_tool_invocation(
        tool_name="communications.send_email", workflow_id="wf-1", success=False,
        latency_ms=None,
        trace_attributes={
            "body": canary, "subject": canary, "recipients": [canary],
            "to": canary, "cc": canary, "bcc": canary,
            "html": canary, "text": canary, "message": canary,
            "query": canary, "providerRequest": canary,
            "providerResponse": canary, "attachments": [canary],
            "recipientAddresses": [canary],
            "exceptionText": canary, "error": canary, "status": "failed",
        },
    )

    attributes = captured[0]
    for field in (
        "body", "subject", "recipients", "to", "cc", "bcc", "html", "text",
        "message", "query", "providerRequest", "providerResponse",
        "attachments", "recipientAddresses",
    ):
        assert attributes[field] == "[protected]"
    assert attributes["status"] == "failed"
    assert "exceptionText" not in attributes and "error" not in attributes
    assert canary not in repr(attributes)
