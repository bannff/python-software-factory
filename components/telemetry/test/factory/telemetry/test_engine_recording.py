from __future__ import annotations

from pathlib import Path

from factory.telemetry.runtime.runtime import TelemetryRuntime


def test_recording_updates_snapshot(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        """
service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: false
  metrics_enabled: false
authoring:
  enabled: false
""".lstrip()
    )

    runtime = TelemetryRuntime(config_dir=cfg)
    runtime.initialize()

    runtime.record_llm_interaction(
        model="test-model",
        input_tokens=10,
        output_tokens=5,
        latency_ms=123.0,
        cost_usd=0.01,
        agent_id="a1",
        workflow_id="w1",
        trace_attributes={"x": "y"},
    )
    runtime.record_agent_execution(agent_id="a1", workflow_id="w1", success=True, latency_ms=5.0, trace_attributes=None)
    runtime.record_tool_invocation(tool_name="t1", workflow_id="w1", success=False, latency_ms=1.0, trace_attributes=None)

    snap = runtime.metrics_snapshot()
    assert snap["llm"]["interactions"] == 1
    assert snap["llm"]["total_tokens"] == 15
    assert snap["tools"]["invocations"] == 1
    assert snap["agent"]["executions"] == 1
    assert snap["errors"] == 1


def test_span_lifecycle(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        """
service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: false
  metrics_enabled: false
""".lstrip()
    )
    runtime = TelemetryRuntime(config_dir=cfg)
    runtime.initialize()

    res = runtime.start_span("x", {"a": 1})
    assert res["ok"] is True
    span_id = res["span_id"]
    end = runtime.end_span(span_id, error=None)
    assert end["ok"] is True
