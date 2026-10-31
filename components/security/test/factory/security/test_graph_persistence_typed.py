"""Typed Graph finding-read regression tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.security.runtime.adapters.graph_persistence import (
    GraphFindingPersistence,
    _rows_to_findings,
)

_INVOKE = "factory.security.runtime.adapters.graph_persistence._invoke"
_GET_AGG = "factory.security.runtime.adapters.graph_persistence._get_aggregator"


def _patched(agg: MagicMock):
    return patch(_INVOKE, side_effect=lambda tool, **kw: agg.invoke_tool(tool, **kw))


class TestGetFindingsTypedToolPin:
    def test_calls_typed_tool_not_cypher(self) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[]))
        with patch(_GET_AGG, return_value=agg), _patched(agg):
            GraphFindingPersistence().get_findings(severity="high", limit=25)
        agg.invoke_tool.assert_called_once()
        assert agg.invoke_tool.call_args[0][0] == "graph_graph_get_recent_findings"
        assert "graph_graph_query" not in [c[0][0] for c in agg.invoke_tool.call_args_list]

    def test_passes_severity_app_run_limit_kwargs(self) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[]))
        with patch(_GET_AGG, return_value=agg), _patched(agg):
            GraphFindingPersistence().get_findings(severity="critical", limit=7)
        assert agg.invoke_tool.call_args[1] == {
            "severity": "critical", "app": "", "run_id": "", "limit": 7,
        }

    def test_severity_none_becomes_empty_string(self) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[]))
        with patch(_GET_AGG, return_value=agg), _patched(agg):
            GraphFindingPersistence().get_findings()
        assert agg.invoke_tool.call_args[1]["severity"] == ""

    def test_no_cypher_strings_remain_in_module(self) -> None:
        from factory.security.runtime.adapters import graph_persistence as mod
        with open(mod.__file__, encoding="utf-8") as fh:
            text = fh.read()
        assert "MATCH (" not in text
        assert "OPTIONAL MATCH" not in text
        assert "graph_graph_query" not in text


class TestGetFindingsErrorPaths:
    def test_returns_empty_list_when_aggregator_raises(self) -> None:
        with patch(_INVOKE, side_effect=RuntimeError("graph down")):
            assert GraphFindingPersistence().get_findings() == []


class TestRowsToFindingsHandlesFlatShape:
    def test_flat_typed_row_shape_is_passed_through(self) -> None:
        rows = [{"id": "f1", "severity": "high", "cwe_id": "CWE-79"}]
        assert _rows_to_findings(rows) == rows

    def test_strips_embeddings_and_none_taxonomy(self) -> None:
        rows = [{"id": "f1", "structural_embedding": [1.0], "cwe_id": None}]
        assert _rows_to_findings(rows) == [{"id": "f1"}]

    def test_handles_empty_rows(self) -> None:
        assert _rows_to_findings([]) == []
