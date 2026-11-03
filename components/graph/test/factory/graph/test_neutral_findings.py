from __future__ import annotations

import asyncio

from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_tool_catalog


def _tools():
    catalog = create_tool_catalog(GraphRuntime({"default_backend": "networkx"}))
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


def test_recorded_finding_is_listed_in_the_neutral_shape_and_filterable_by_kind() -> None:
    tools = _tools()
    rec = tools["graph_record_finding"](
        title="Slow query", severity="medium", kind="performance", category="latency",
        subject={"type": "tool", "id": "sql_query", "location": "query #3"},
        taxonomy=[{"scheme": "custom", "id": "PERF-1"}], run_id="run-1")
    assert rec.ok and rec.data.state == "candidate"
    tools["graph_record_finding"](title="Open S3", severity="high", kind="security",
                                  taxonomy=[{"scheme": "cwe", "id": "CWE-200"}])
    allf = tools["graph_get_recent_findings"]().data
    assert allf.count == 2
    perf = tools["graph_get_recent_findings"](kind="performance").data
    assert perf.count == 1
    f = perf.rows[0]["finding"]
    assert f["kind"] == "performance" and f["state"] == "candidate" and f["category"] == "latency"
    assert f["subject"] == {"type": "tool", "id": "sql_query", "location": "query #3"}
    assert {"type": "run", "id": "run-1"} in f["refs"]
    assert tools["graph_get_recent_findings"](kind="security").data.rows[0]["finding"]["taxonomy"][0]["scheme"] == "cwe"


def test_state_can_be_changed_and_legacy_rows_get_a_derived_kind() -> None:
    tools = _tools()
    fid = tools["graph_record_finding"](title="x", severity="low").data.finding_id
    assert tools["graph_set_finding_state"](finding_id=fid, state="refuted").data.success
    row = tools["graph_get_recent_findings"]().data.rows[0]
    assert row["finding"]["state"] == "refuted" and row["finding"]["kind"] == "other"


def test_unknown_backend_is_typed() -> None:
    assert _tools()["graph_record_finding"](title="x", severity="low", backend="nope").error == "unknown_backend"
