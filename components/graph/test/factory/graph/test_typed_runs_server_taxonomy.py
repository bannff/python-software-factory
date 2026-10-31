"""MCP-server-level tests for the ``taxonomy_edges`` parameter.

Pins the wire-shape contract added under bd python-factory-ecph9 (epic
python-factory-hadbi). Adapter-level invariants live in
``test_typed_runs_taxonomy_edges.py``; this file asserts the FastMCP
tool accepts the param as a list of dicts and produces the expected
row shape end-to-end.
"""

from __future__ import annotations

import asyncio

from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import reset_runtime


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


class TestTaxonomyEdgesViaMCP:
    """Wire-level tests for ``graph_get_findings_for_run``."""

    def setup_method(self) -> None:
        reset_runtime()
        self.server = create_mcp_server()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_findings_for_run_accepts_taxonomy_edges_dicts(self) -> None:
        """MCP tool accepts edge specs as raw dicts on the wire."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"id": "finding-1", "run_id": "r1", "severity": "high", "title": "x",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        _call_tool(
            self.server, "graph_add_entity", entity_id="varietal-1", entity_type="Varietal",
            properties={"id": "v-1", "name": "Pinot Noir"},
        )
        _call_tool(
            self.server, "graph_add_relationship", source_id="finding-1", target_id="varietal-1",
            relationship_type="TASTED_AS", relationship_id="rel-1",
        )
        result = _call_tool(
            self.server, "graph_get_findings_for_run", run_id="r1",
            taxonomy_edges=[{"relationship_type": "TASTED_AS", "target_label": "Varietal",
                             "target_props": {"id": "varietal_id", "name": "varietal_name"}}],
        )
        assert result.ok
        data = result.data
        assert data is not None
        assert data.count == 1
        row = data.rows[0]
        assert row["varietal_id"] == "v-1"
        assert row["varietal_name"] == "Pinot Noir"
        for key in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert key not in row

    def test_findings_for_run_empty_edges_drops_taxonomy_columns(self) -> None:
        """``taxonomy_edges=[]`` produces rows without any taxonomy keys."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"id": "finding-1", "run_id": "r1", "severity": "high",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_findings_for_run", run_id="r1", taxonomy_edges=[])
        assert result.ok
        data = result.data
        assert data is not None
        row = data.rows[0]
        for key in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert key not in row

    def test_findings_for_run_default_keeps_security_keys(self) -> None:
        """``taxonomy_edges`` omitted = back-compat default produces CWE/OCSF cols."""
        _call_tool(
            self.server, "graph_add_entity", entity_id="finding-1", entity_type="Finding",
            properties={"id": "finding-1", "run_id": "r1", "severity": "high",
                        "created_at": "2026-01-01T00:00:00Z"},
        )
        result = _call_tool(self.server, "graph_get_findings_for_run", run_id="r1")
        assert result.ok
        data = result.data
        assert data is not None
        row = data.rows[0]
        for key in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert key in row
            assert row[key] is None
