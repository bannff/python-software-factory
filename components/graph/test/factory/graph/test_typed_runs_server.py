"""MCP-server-level sanity checks for typed run-scoped graph tools.

Tracked under bd python-factory-j1lb / epic python-factory-kzd8.
Property tests for the underlying Protocol methods live in
``test_typed_runs_properties.py``; this file asserts the FastMCP
registration and request-shape contract.
"""

import asyncio

from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import reset_runtime


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


class TestTypedRunScopedTools:
    """Sanity checks for typed run-scoped tools."""

    def setup_method(self) -> None:
        reset_runtime()
        self.server = create_mcp_server()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_all_six_typed_tools_registered(self) -> None:
        """L0 contract: 7 graph tools must be visible on the MCP server."""
        names = [t.name for t in asyncio.run(self.server.list_tools())]
        for tool in (
            "graph_get_findings_for_run", "graph_count_entities_by_run",
            "graph_get_workflow_summary", "graph_get_recent_findings",
            "graph_get_target_app", "graph_get_tool_invocations_for_run",
            "graph_list_recent_tool_invocations",
        ):
            assert tool in names, f"missing typed tool: {tool}"

    def test_findings_for_run_returns_taxonomy_keys(self) -> None:
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"id": "finding-1", "run_id": "r1", "app": "a", "severity": "high",
                        "title": "x", "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_findings_for_run", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        assert data.count == 1
        row = data.rows[0]
        for key in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert key in row

    def test_workflow_summary_composes(self) -> None:
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"run_id": "r1", "app": "a", "verdict": "tp", "severity": "high",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        _call_tool(
            self.server, "graph_add_entity", entity_id="suspected-1", entity_type="SuspectedVuln",
            properties={"run_id": "r1", "app": "a"},
        )
        result = _call_tool(self.server, "graph_get_workflow_summary", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        assert data.finding_count == 1
        assert data.suspected_count == 1
        assert data.finding_verdicts.get("tp") == 1
        assert data.target_app == "a"

    def test_count_entities_by_run_default_labels(self) -> None:
        _call_tool(
            self.server, "graph_add_entity", entity_id="exploit-1", entity_type="ProvenExploit",
            properties={"run_id": "r1"},
        )
        result = _call_tool(self.server, "graph_count_entities_by_run", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        assert data.counts["ProvenExploit"] == 1
        assert data.counts["Finding"] == 0
        assert data.total == 1

    def test_target_app_singleton(self) -> None:
        _call_tool(
            self.server, "graph_add_entity", entity_id="app-x", entity_type="TargetApp",
            properties={"app": "x", "name": "x", "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_target_app", target_app="x")
        assert result.ok
        data = result.data
        assert data is not None
        assert data.found is True
        assert data.entity is not None
        assert data.entity["id"] == "app-x"

    def test_tool_invocations_returns_ordered_rows(self) -> None:
        for sequence in (2, 0, 1):
            _call_tool(
                self.server, "graph_add_entity", entity_id=f"inv-{sequence}",
                entity_type="ToolInvocation", properties={"workflow_run_id": "r1", "sequence": sequence,
                                                           "tool_name": f"t{sequence}"},
            )
        result = _call_tool(self.server, "graph_get_tool_invocations_for_run", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        assert [row["sequence"] for row in data.rows] == [0, 1, 2]

    def test_recent_findings_descending(self) -> None:
        for ts in ("2026-01-01T00:00:01Z", "2026-01-01T00:00:03Z", "2026-01-01T00:00:02Z"):
            _call_tool(
                self.server, "graph_add_entity", entity_id=f"finding-{ts}", entity_type="Finding",
                properties={"run_id": "r1", "created_at": ts, "severity": "high"},
            )
        result = _call_tool(self.server, "graph_get_recent_findings", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        timestamps = [row["created_at"] for row in data.rows]
        assert timestamps == sorted(timestamps, reverse=True)
