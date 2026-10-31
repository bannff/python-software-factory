"""bd python-factory-le9gu — graph_get_workflow_summary accepts new kwargs.

The MCP tool ``graph_get_workflow_summary`` now accepts ``taxonomy_edges``
and ``count_labels`` so domain-aware FE/agents can override the security
defaults without touching engine code.

Tests cover:
* Legacy callers (no kwargs) still work — back-compat preserved.
* ``taxonomy_edges`` flows into the inner ``get_findings_for_run`` call.
* ``count_labels`` flows into the inner ``count_entities_by_run`` call.
* The composed return shape stays the same.
"""

from __future__ import annotations

import asyncio

from factory.graph.runtime.runtime import reset_runtime
from factory.graph.server import create_mcp_server


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


class TestWorkflowSummaryNewKwargs:
    def setup_method(self) -> None:
        reset_runtime()
        self.server = create_mcp_server()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_legacy_call_still_works(self) -> None:
        """Calling without taxonomy_edges/count_labels keeps the security default."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"run_id": "r-legacy", "app": "a", "verdict": "tp", "severity": "high",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_workflow_summary", run_id="r-legacy")
        assert result.ok
        data = result.data
        assert data is not None
        assert data.finding_count == 1
        assert data.finding_verdicts == {"tp": 1}
        assert data.endpoints_discovered == 0

    def test_taxonomy_edges_kwarg_accepted(self) -> None:
        """Passing taxonomy_edges=[] (skip-join) does not crash."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-2", entity_type="Finding",
            properties={"run_id": "r-skip", "app": "a", "verdict": "tp", "severity": "high",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_workflow_summary", run_id="r-skip", taxonomy_edges=[])
        assert result.ok
        data = result.data
        assert data is not None
        assert data.finding_count == 1

    def test_count_labels_override(self) -> None:
        """Custom count_labels reaches count_entities_by_run."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="custom-1", entity_type="WineFinding",
            properties={"run_id": "r-wine", "app": "WineApp"},
        )
        result_default = _call_tool(self.server, "graph_get_workflow_summary", run_id="r-wine")
        result_override = _call_tool(
            self.server, "graph_get_workflow_summary", run_id="r-wine", count_labels=["WineFinding"],
        )
        assert result_default.ok and result_override.ok
        default_data = result_default.data
        override_data = result_override.data
        assert default_data is not None and override_data is not None
        assert default_data.finding_count == 0
        assert override_data.finding_count == 0

    def test_custom_taxonomy_edges_signature_accepted(self) -> None:
        """Custom taxonomy_edges shape doesn't break the call."""
        custom_edges = [{"relationship_type": "BELONGS_TO_CATEGORY", "target_label": "WineCategory",
                         "target_props": {"name": "category_name"}}]
        result = _call_tool(
            self.server, "graph_get_workflow_summary", run_id="r-empty", taxonomy_edges=custom_edges,
        )
        assert result.ok
        data = result.data
        assert data is not None
        assert data.finding_count == 0
