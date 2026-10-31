"""Public typed-boundary tests for the Evals SOP lifecycle."""
from __future__ import annotations

import asyncio

import pytest

from factory.evals.interface import create_server
from factory.evals.runtime.adapters import sop_store

_TOOLS = {
    "evals_sop_plan", "evals_sop_generate_data", "evals_sop_run",
    "evals_sop_report", "evals_sop_status", "evals_sop_list",
}


def _run(name: str, arguments: dict):
    tool = asyncio.run(create_server().get_tool(name))
    return tool.fn(**arguments).model_dump(mode="json")


@pytest.fixture
def isolated_sop_store(monkeypatch, tmp_path):
    monkeypatch.setattr(sop_store, "_STORE_PATH", tmp_path / "sessions.json")
    monkeypatch.setattr(sop_store, "_TMP_PATH", tmp_path / "sessions.json.tmp")
    monkeypatch.setattr(sop_store, "_cache", None)
    yield
    sop_store._cache = None


def test_sop_tools_publish_v1_envelopes_and_flat_data(isolated_sop_store) -> None:
    for name in _TOOLS:
        assert asyncio.run(create_server().get_tool(name)) is not None

    plan = _run("evals_sop_plan", {"agent_description": "search agent"})
    assert plan["ok"] is True
    assert plan["data"]["phase"] == "plan"
    assert plan["data"]["next_phase"] == "data"

    session_id = plan["data"]["session_id"]
    premature_run = _run("evals_sop_run", {"session_id": session_id})
    assert premature_run["ok"] is False
    assert premature_run["data"] is None
    assert "Expected phase 'eval'" in premature_run["error"]

    status = _run("evals_sop_status", {"session_id": session_id})
    assert status["ok"] is True
    assert status["data"]["phase"] == "data"

    listed = _run("evals_sop_list", {})
    assert listed["ok"] is True
    assert listed["data"]["count"] == 1
    assert listed["data"]["sessions"][0]["id"] == session_id


def test_sop_boundary_rejects_unknown_flat_fields(isolated_sop_store) -> None:
    with pytest.raises(Exception):
        _run("evals_sop_plan", {"agent_description": "agent", "unexpected": True})
    with pytest.raises(Exception):
        _run("evals_sop_status", {"session_id": "missing", "unexpected": True})
