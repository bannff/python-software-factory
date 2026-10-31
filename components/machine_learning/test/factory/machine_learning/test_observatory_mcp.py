"""MCP and five-view contract tests for the ML Observatory."""
from __future__ import annotations

import asyncio
from unittest.mock import patch
from factory.machine_learning.server import create_mcp_server


class _FineTuner:
    def list_jobs(self): return []


class _Runtime:
    def get_finetuner(self): return _FineTuner()


def _ok(data):
    return {
        "schema_version": "v1", "ok": True, "data": data,
        "error": None, "idempotency_key": None,
    }


class _Invoker:
    def __call__(self, tool_name, **kwargs):
        if tool_name == "storage_doc_find": return _ok({"documents": []})
        if tool_name == "events_query_events": return _ok({"events": []})
        raise AssertionError(tool_name)


def _data(server, name):
    result = asyncio.run(server.get_tool(name)).fn()
    assert result.ok is True
    return result.data


def test_observatory_tools_and_exact_ordered_views():
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": _Invoker()}):
        server = create_mcp_server(_Runtime())
        summary, lineage, views = (_data(server, "ml_get_observatory_summary"),
            _data(server, "ml_get_observatory_lineage"), _data(server, "ml_get_views"))
    assert summary.population_state == "empty"
    assert summary.overview["training_runs"] == 0
    assert lineage.nodes == []
    assert [view["id"] for view in views.views] == ["ml-overview", "ml-experiments", "ml-models", "ml-learning-runs", "ml-lineage"]


def test_missing_invoker_is_unknown_not_empty():
    with patch("factory.mcp_utils.registry._services", {}):
        summary = _data(create_mcp_server(_Runtime()), "ml_get_observatory_summary")
    assert summary.population_state is None
    assert "unavailable" in summary.message


def test_finetuning_failure_is_isolated_from_primary_populations():
    class BrokenRuntime:
        def get_finetuner(self): raise RuntimeError("fine tuning down")
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": _Invoker()}):
        summary = _data(create_mcp_server(BrokenRuntime()), "ml_get_observatory_summary")
    assert summary.population_state == "empty"
    assert summary.overview["fine_tuning_jobs"] is None
