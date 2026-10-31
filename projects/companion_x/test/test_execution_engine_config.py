"""Regression tests for the M7.6 stuck-fire root cause (P1, owner smoke #2 13:29).

``factory.agent.runtime.managed_launch.launch_managed_graph`` hardcodes
``engine_id="langgraph"`` when calling ``workflow.enroll_execution``. But
Companion-X's deployment config (``projects/companion_x/config/settings.yaml``,
the file ``WORKFLOW_CONFIG_DIR`` points at in every real launch) was still
registering the pre-LangChain-migration engine id ``strands_graph``, pointing
at ``execute_strands_graph_attempt`` / ``cancel_strands_graph_attempt`` — tools
that no longer exist (the Agent brick now ships ``execute_langgraph_attempt`` /
``cancel_langgraph_attempt``).

Every scheduled/background fire that reached ``enroll_execution`` therefore hit
``ExecutionEngineRegistry.resolve("langgraph")`` -> ``ValueError: unknown
execution engine: langgraph`` -> the fire retried forever with no terminal
reason. This is a stale-config gap left over from the Strands retirement, not a
bug in the enrollment/registry mechanism itself.

The live ``settings.yaml`` is untracked deployment state (``projects/*/config/``
is gitignored, issue #34), so a fresh clone has none and the pinned contract
lives in the tracked ``settings.yaml.example`` template. Each test below drives
``WorkflowRuntime.from_config_dir`` — the exact call ``server.py`` makes — over
the template, so the registration can never regress silently in a clean
checkout; a machine-local live file is additionally checked when present.
"""
from __future__ import annotations

from pathlib import Path

import pytest

CONFIG_DIR = Path(__file__).parents[1] / "config"
LIVE_CONFIG = CONFIG_DIR / "settings.yaml"
TEMPLATE_CONFIG = CONFIG_DIR / "settings.yaml.example"


def _materialize_deployment_config(tmp_path: Path) -> Path:
    """Copy the tracked template into a scratch dir as a live ``settings.yaml``."""
    assert TEMPLATE_CONFIG.exists(), (
        f"tracked deployment template {TEMPLATE_CONFIG} is missing; it carries "
        "the langgraph engine registration this test pins (issue #34)"
    )
    scratch = tmp_path / "config"
    scratch.mkdir()
    (scratch / "settings.yaml").write_text(TEMPLATE_CONFIG.read_text())
    return scratch


def test_template_registers_the_langgraph_engine_managed_launch_calls(tmp_path):
    from factory.workflow.runtime.runtime import WorkflowRuntime

    runtime = WorkflowRuntime.from_config_dir(_materialize_deployment_config(tmp_path))
    spec = runtime.execution_engines.resolve("langgraph")

    assert spec.invoke_target.brick_name == "agent"
    assert spec.invoke_target.tool_name == "execute_langgraph_attempt"
    assert spec.cancel_target is not None
    assert spec.cancel_target.brick_name == "agent"
    assert spec.cancel_target.tool_name == "cancel_langgraph_attempt"


def test_template_no_longer_registers_the_dead_strands_engine_id(tmp_path):
    from factory.workflow.runtime.execution_engines import ExecutionEngineRegistry
    from factory.workflow.runtime.runtime import WorkflowRuntime

    runtime = WorkflowRuntime.from_config_dir(_materialize_deployment_config(tmp_path))
    try:
        runtime.execution_engines.resolve("strands_graph")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "strands_graph must not be registered — the Agent brick no "
            "longer exposes execute_strands_graph_attempt/"
            "cancel_strands_graph_attempt, so any caller of that engine id "
            "would fail exactly like the langgraph gap this test guards."
        )
    assert isinstance(runtime.execution_engines, ExecutionEngineRegistry)


@pytest.mark.skipif(
    not LIVE_CONFIG.exists(),
    reason="no machine-local settings.yaml in this checkout",
)
def test_live_settings_yaml_when_present_registers_the_langgraph_engine():
    """The file a real launch loads must stay consistent with the template."""
    from factory.workflow.runtime.runtime import WorkflowRuntime

    spec = WorkflowRuntime.from_config_dir(CONFIG_DIR).execution_engines.resolve(
        "langgraph",
    )

    assert spec.invoke_target.tool_name == "execute_langgraph_attempt"
    assert spec.cancel_target is not None
    assert spec.cancel_target.tool_name == "cancel_langgraph_attempt"


def test_invoke_target_tools_exist_on_the_real_agent_mcp_surface():
    """Belt-and-suspenders: the configured tool names must be real, callable
    Agent MCP tools today, not just plausible-looking strings in YAML."""
    from factory.agent.mcp.managed_graph_tool import register

    class _FakeMCP:
        def tool(self):
            def decorator(fn):
                self.registered.append(fn.__name__)
                return fn
            return decorator

        def __init__(self) -> None:
            self.registered: list[str] = []

    fake = _FakeMCP()
    register(fake)
    assert "execute_langgraph_attempt" in fake.registered
    assert "cancel_langgraph_attempt" in fake.registered
