"""Tests for span recording functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.telemetry.runtime.runtime import TelemetryRuntime


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a minimal config directory for testing."""
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
  logging_enabled: false
authoring:
  enabled: false
""".lstrip()
    )
    return cfg


@pytest.fixture
def runtime(config_dir: Path) -> TelemetryRuntime:
    """Create an initialized TelemetryRuntime."""
    eng = TelemetryRuntime(config_dir=config_dir)
    eng.initialize()
    return eng


class TestRecordLLMInteraction:
    """Tests for record_llm_interaction functionality."""

    def test_record_basic_interaction(self, runtime: TelemetryRuntime) -> None:
        """Test recording a basic LLM interaction."""
        result = runtime.record_llm_interaction(
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            latency_ms=None,
            cost_usd=None,
            agent_id=None,
            workflow_id=None,
            trace_attributes=None,
        )
        
        assert result["ok"] is True
        assert result["recorded"] == "llm_interaction"

    def test_updates_snapshot(self, runtime: TelemetryRuntime) -> None:
        """Test that recording updates metrics snapshot."""
        runtime.record_llm_interaction(
            model="claude-3",
            input_tokens=200,
            output_tokens=100,
            latency_ms=500.0,
            cost_usd=0.05,
            agent_id="agent-1",
            workflow_id="wf-1",
            trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["llm"]["interactions"] == 1
        assert snap["llm"]["input_tokens"] == 200
        assert snap["llm"]["output_tokens"] == 100
        assert snap["llm"]["total_tokens"] == 300
        assert snap["llm"]["cost_usd"] == 0.05

    def test_accumulates_tokens(self, runtime: TelemetryRuntime) -> None:
        """Test that multiple interactions accumulate tokens."""
        runtime.record_llm_interaction(
            model="gpt-4", input_tokens=100, output_tokens=50,
            latency_ms=None, cost_usd=None, agent_id=None,
            workflow_id=None, trace_attributes=None,
        )
        runtime.record_llm_interaction(
            model="gpt-4", input_tokens=200, output_tokens=100,
            latency_ms=None, cost_usd=None, agent_id=None,
            workflow_id=None, trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["llm"]["interactions"] == 2
        assert snap["llm"]["total_tokens"] == 450


class TestRecordAgentExecution:
    """Tests for record_agent_execution functionality."""

    def test_record_successful_execution(self, runtime: TelemetryRuntime) -> None:
        """Test recording a successful agent execution."""
        result = runtime.record_agent_execution(
            agent_id="agent-1",
            workflow_id="wf-1",
            success=True,
            latency_ms=100.0,
            trace_attributes=None,
        )
        
        assert result["ok"] is True
        assert result["recorded"] == "agent_execution"

    def test_updates_snapshot(self, runtime: TelemetryRuntime) -> None:
        """Test that recording updates metrics snapshot."""
        runtime.record_agent_execution(
            agent_id="agent-1",
            workflow_id="wf-1",
            success=True,
            latency_ms=100.0,
            trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["agent"]["executions"] == 1

    def test_failed_execution_increments_errors(self, runtime: TelemetryRuntime) -> None:
        """Test that failed execution increments error count."""
        runtime.record_agent_execution(
            agent_id="agent-1",
            workflow_id="wf-1",
            success=False,
            latency_ms=50.0,
            trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["errors"] == 1


class TestRecordToolInvocation:
    """Tests for record_tool_invocation functionality."""

    def test_record_successful_invocation(self, runtime: TelemetryRuntime) -> None:
        """Test recording a successful tool invocation."""
        result = runtime.record_tool_invocation(
            tool_name="search",
            workflow_id="wf-1",
            success=True,
            latency_ms=50.0,
            trace_attributes=None,
        )
        
        assert result["ok"] is True
        assert result["recorded"] == "tool_invocation"

    def test_updates_snapshot(self, runtime: TelemetryRuntime) -> None:
        """Test that recording updates metrics snapshot."""
        runtime.record_tool_invocation(
            tool_name="search",
            workflow_id=None,
            success=True,
            latency_ms=None,
            trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["tools"]["invocations"] == 1

    def test_failed_invocation_increments_errors(self, runtime: TelemetryRuntime) -> None:
        """Test that failed invocation increments error count."""
        runtime.record_tool_invocation(
            tool_name="failing_tool",
            workflow_id=None,
            success=False,
            latency_ms=10.0,
            trace_attributes=None,
        )
        
        snap = runtime.metrics_snapshot()
        assert snap["errors"] == 1
