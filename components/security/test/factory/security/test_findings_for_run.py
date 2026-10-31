"""Cross-brick integration tests for ``security_list_findings_for_run``.

The thin pass-through MUST go through the MCP aggregator and never
import the graph brick directly. These tests assert that contract by
mocking ``factory.mcp_server.interface.get_aggregator`` and verifying
the tool delegates to ``graph_graph_get_findings_for_run``.

Tracked under bd python-factory-j1lb / epic python-factory-kzd8.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from factory.mcp_utils.runtime.tool_result import fail, ok
from factory.security.runtime.adapters.mock import MockAnalyzerAdapter
from factory.security.interface import Runtime, create_server


@dataclass(frozen=True)
class _RowsData:
    rows: list[dict[str, Any]]
    count: int


@pytest.fixture(scope="module")
def mcp():
    return create_server(Runtime(MockAnalyzerAdapter()))


def _patch_aggregator(agg: MagicMock):
    """Patch the MCP server bootstrap so the tool sees our fake aggregator."""
    server_patch = patch(
        "factory.mcp_server.interface.get_server", return_value=MagicMock(),
    )
    agg_patch = patch(
        "factory.mcp_server.interface.get_aggregator", return_value=agg,
    )
    return server_patch, agg_patch


class TestSecurityListFindingsForRunDelegation:
    """Pass-through must call the graph brick tool via the aggregator."""

    def test_tool_is_registered(self, mcp) -> None:
        names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "security_list_findings_for_run" in names

    def test_delegates_to_graph_via_aggregator(self, mcp) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = ok(_RowsData(
            rows=[{"id": "f1", "run_id": "r1", "severity": "high"}],
            count=1,
        ))
        sp, ap = _patch_aggregator(agg)
        with sp, ap:
            tool = asyncio.run(
                mcp.get_tool("security_list_findings_for_run")
            )
            result = tool.fn(run_id="r1", app="webgoat", limit=25)
        agg.invoke_tool.assert_called_once_with(
            "graph_graph_get_findings_for_run",
            run_id="r1", app="webgoat", limit=25,
        )
        assert result.ok is True
        assert result.data.run_id == "r1"
        assert result.data.app == "webgoat"
        assert result.data.count == 1
        assert result.data.rows[0]["id"] == "f1"

    def test_returns_error_envelope_when_aggregator_unavailable(
        self, mcp,
    ) -> None:
        sp = patch(
            "factory.mcp_server.interface.get_server", return_value=MagicMock(),
        )
        ap = patch(
            "factory.mcp_server.interface.get_aggregator", return_value=None,
        )
        with sp, ap:
            tool = asyncio.run(
                mcp.get_tool("security_list_findings_for_run")
            )
            result = tool.fn(run_id="r1")
        assert result.ok is True
        assert result.data.error == "mcp_aggregator_unavailable"
        assert result.data.rows == []
        assert result.data.count == 0

    def test_returns_error_envelope_for_failed_graph_result(self, mcp) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = fail("graph unavailable")
        sp, ap = _patch_aggregator(agg)
        with sp, ap:
            tool = asyncio.run(
                mcp.get_tool("security_list_findings_for_run")
            )
            result = tool.fn(run_id="r1", app="webgoat", limit=25)
        assert result.ok is True
        assert result.data.error == "graph unavailable"
        assert result.data.run_id == "r1"
        assert result.data.rows == []

    def test_does_not_import_graph_brick_runtime(self) -> None:
        """No direct cross-brick import from the security operational tool."""
        import factory.security.mcp.operational as op_mod
        source = op_mod.__file__
        with open(source, "r", encoding="utf-8") as fh:
            text = fh.read()
        # Allowlisted: only references to graph brick should be by tool name.
        assert "from factory.graph" not in text
        assert "import factory.graph" not in text
        assert "graph_graph_get_findings_for_run" in text


class TestSecurityListFindingsForRunContract:
    """Bounded representative inputs preserve the cross-brick contract."""

    @pytest.mark.parametrize(
        ("run_id", "app", "limit"),
        [
            ("r1", "", 0),
            ("run-αβ42", "café", 1),
            ("RUN_9z", "app-123", 200),
        ],
    )
    def test_passes_args_through_unchanged(
        self, mcp, run_id: str, app: str, limit: int,
    ) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = ok(_RowsData(rows=[], count=0))
        sp, ap = _patch_aggregator(agg)
        with sp, ap:
            tool = asyncio.run(
                mcp.get_tool("security_list_findings_for_run")
            )
            tool.fn(run_id=run_id, app=app, limit=limit)
        agg.invoke_tool.assert_called_once_with(
            "graph_graph_get_findings_for_run",
            run_id=run_id, app=app, limit=limit,
        )
