"""Contract tests for typed Graph MCP helpers."""
from __future__ import annotations

import asyncio

import pytest

from factory.graph.server import get_mcp_server
from factory.graph.runtime.runtime import reset_runtime


@pytest.fixture(autouse=True)
def reset_state():
    """Reset runtime state between tests."""
    reset_runtime()
    yield
    reset_runtime()


def _tool(name: str):
    tool = asyncio.run(get_mcp_server().get_tool(name))
    assert tool is not None
    return tool


class TestContractHelpers:
    """Contract helpers return typed ToolResult envelopes."""

    @pytest.mark.parametrize(
        ("name", "attribute"),
        [
            ("graph_get_capabilities", "name"),
            ("graph_health_check", "healthy"),
            ("graph_describe_config_schema", "properties"),
        ],
    )
    def test_no_arg_contract_helper(self, name: str, attribute: str) -> None:
        result = _tool(name).fn()
        assert result.ok
        assert result.data is not None
        assert hasattr(result.data, attribute)

    def test_dashboard_helpers_return_typed_data(self) -> None:
        add_entity = _tool("graph_add_entity")
        add_relationship = _tool("graph_add_relationship")
        add_entity.fn(entity_id="workflow:run:run-123", entity_type="WorkflowRun",
                      properties={"run_id": "run-123", "status": "running"})
        add_entity.fn(entity_id="sandbox:env:env-123", entity_type="SandboxEnvironment",
                      properties={"env_id": "env-123", "status": "running"})
        add_relationship.fn(relationship_id="rel-1", relationship_type="CORRELATED_WITH",
                            source_id="workflow:run:run-123", target_id="sandbox:env:env-123")

        summary = _tool("graph_get_dashboard_summary").fn()
        assert summary.ok and summary.data is not None
        assert summary.data.overview["nodes"] >= 2
        assert summary.data.overview["edges"] >= 1
        assert any(item["entity_type"] == "WorkflowRun" for item in summary.data.entities)

        context = _tool("graph_get_entity_context").fn(entity_id="workflow:run:run-123")
        assert context.ok and context.data is not None
        assert context.data.count >= 1
        assert any(item["entity_id"] == "sandbox:env:env-123" for item in context.data.entries)

        views = _tool("graph_get_views").fn()
        assert views.ok and views.data is not None
        assert views.data.views[0]["id"] == "graph-dashboard"
