"""Current ToolCatalog registration for Workflow-managed graph launch."""
from __future__ import annotations

import pytest

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


@pytest.mark.asyncio
async def test_invoke_graph_catalog_tool_enrolls_through_managed_facade(
    monkeypatch,
) -> None:
    from factory.agent.mcp import tools as tools_module

    captured = {}

    async def launch(agent, graph_id, task, context, **kwargs):
        captured.update(
            agent=agent, graph_id=graph_id, task=task,
            context=context, kwargs=kwargs,
        )
        return {"success": True, "run_id": "managed-run", "status": "running"}

    fake_agent = object()
    monkeypatch.setattr(tools_module, "_launch_registered_graph", launch)
    catalog = ToolCatalog("agent-test")
    tools_module.register(catalog, fake_agent)
    invocation = await catalog.get_tool("invoke_graph")
    assert invocation is not None
    result = await invocation.fn(graph_id="rt-sast-scan", task="x", context={})
    assert result.data.result["run_id"] == "managed-run"
    assert captured["graph_id"] == "rt-sast-scan"
    assert captured["kwargs"] == {"launcher": "invoke_graph"}
