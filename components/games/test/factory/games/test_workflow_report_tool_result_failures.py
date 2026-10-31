"""Regression coverage for failed canonical Graph ToolResult report reads."""
from __future__ import annotations

from typing import Any

from factory.games.runtime.workflow_report_findings import build_findings_detail
from factory.games.runtime.workflow_report_graph import graph_counts
from factory.mcp_utils.runtime.tool_result import ToolResult


def _failed_graph_result(_tool_name: str, **_kwargs: Any) -> ToolResult[Any]:
    return ToolResult(ok=False, data=None, error="graph unavailable")


def test_failed_tool_results_preserve_empty_workflow_report_fallbacks() -> None:
    assert graph_counts(_failed_graph_result, run_id="run-failed") == {
        "suspected_vuln_count": 0,
        "finding_count": 0,
        "finding_verdicts": {},
        "proven_exploit_count": 0,
        "endpoints_discovered": 0,
    }
    assert build_findings_detail(_failed_graph_result, run_id="run-failed")["findings"] == []
