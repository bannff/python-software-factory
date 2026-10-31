"""Pin tests for the L2 Cypher → typed-tool migration in graph_persistence.

Tracked under bd python-factory-o9l2 / epic python-factory-kzd8.

Asserts ``GraphFindingPersistence.get_findings`` calls the typed
``graph_graph_get_recent_findings`` tool (bd python-factory-j1lb), never
``graph_graph_query``, and that ``_rows_to_findings`` consumes the new
flat-row shape returned by that tool.
"""

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


# -- Negative pin: typed tool, never Cypher ---------------------------------


class TestGetFindingsTypedToolPin:

    def test_calls_typed_tool_not_cypher(self) -> None:
        agg = MagicMock()
        agg.invoke_tool.return_value = MagicMock(ok=True, data=MagicMock(rows=[]))
        with patch(_GET_AGG, return_value=agg), _patched(agg):
            GraphFindingPersistence().get_findings(severity="high", limit=25)
        agg.invoke_tool.assert_called_once()
        assert agg.invoke_tool.call_args[0][0] == "graph_graph_get_recent_findings"
        names = [c[0][0] for c in agg.invoke_tool.call_args_list]
        assert "graph_graph_query" not in names

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
        with open(mod.__file__, "r", encoding="utf-8") as fh:
            text = fh.read()
        assert "MATCH (" not in text
        assert "OPTIONAL MATCH" not in text
        assert "graph_graph_query" not in text


# -- Aggregator failure modes ------------------------------------------------


class TestGetFindingsErrorPaths:

    def test_returns_empty_list_when_aggregator_raises(self) -> None:
        with patch(_INVOKE, side_effect=RuntimeError("graph down")):
            assert GraphFindingPersistence().get_findings() == []


# -- _rows_to_findings unit tests -------------------------------------------


class TestRowsToFindingsHandlesFlatShape:

    def test_flat_typed_row_shape_is_passed_through(self) -> None:
        rows = [{
            "id": "f1", "severity": "high", "title": "t",
            "cwe_id": "CWE-79", "cwe_name": "XSS",
            "ocsf_class": "Security Finding", "ocsf_uid": 2001,
        }]
        out = _rows_to_findings(rows)
        assert len(out) == 1
        assert out[0]["id"] == "f1"
        assert out[0]["cwe_id"] == "CWE-79"
        assert out[0]["cwe_name"] == "XSS"
        assert out[0]["ocsf_class"] == "Security Finding"
        assert out[0]["ocsf_uid"] == 2001

    def test_rows_preserve_canonical_taxonomy_fields(self) -> None:
        rows = [{
            "id": "f1", "severity": "high", "cwe_id": "CWE-79",
            "cwe_name": "XSS", "ocsf_class": "Security Finding",
        }]
        out = _rows_to_findings(rows)
        assert out[0] == rows[0]

    def test_strips_embedding_fields(self) -> None:
        rows = [{
            "id": "f1", "severity": "low",
            "structural_embedding": [1.0, 2.0],
            "n2v_embedding": [3.0],
        }]
        out = _rows_to_findings(rows)
        assert "structural_embedding" not in out[0]
        assert "n2v_embedding" not in out[0]

    def test_drops_none_taxonomy_keys(self) -> None:
        rows = [{
            "id": "f1", "severity": "low",
            "cwe_id": None, "cwe_name": None,
            "ocsf_class": None, "ocsf_uid": None,
        }]
        out = _rows_to_findings(rows)
        for k in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert k not in out[0]

    def test_handles_empty_rows(self) -> None:
        assert _rows_to_findings([]) == []
