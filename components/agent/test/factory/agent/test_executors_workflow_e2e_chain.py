"""Public invoke_graph cutover from legacy execution to Workflow enrollment."""
from __future__ import annotations

import pytest

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


@pytest.mark.asyncio
async def test_invoke_graph_uses_managed_workflow_enrollment(monkeypatch) -> None:
    from factory.agent.mcp import tools as tools_module

    captured = {}

    async def managed(agent, graph_id, task, context, **kwargs):
        captured.update(
            graph_id=graph_id, task=task, context=context, kwargs=kwargs,
        )
        return {
            "success": True, "run_id": "workflow-run",
            "status": "running", "execution_mode": "managed",
        }

    monkeypatch.setattr(tools_module, "_launch_registered_graph", managed)
    agent = type("Agent", (), {})()
    catalog = ToolCatalog("agent-test")
    tools_module.register(catalog, agent)
    registered = await catalog.get_tool("invoke_graph")
    assert registered is not None
    result = await registered.fn(
        graph_id="rt-sast-scan", task="smoke",
        context={"vuln_class": "idor", "run_id": "qa-e2e"},
    )
    assert result.data.result["run_id"] == "workflow-run"
    assert captured["graph_id"] == "rt-sast-scan"
    assert captured["kwargs"] == {"launcher": "invoke_graph"}
