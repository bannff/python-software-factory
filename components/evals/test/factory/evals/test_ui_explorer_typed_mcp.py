"""Fresh-server typed-boundary checks for Evals UI Explorer tools."""
from __future__ import annotations

import asyncio

import pytest

from factory.evals.interface import create_server
from factory.evals.mcp import ui_scenario_tools

_TOOLS = {
    "evals_ui_get_capabilities", "evals_create_ui_scenario",
    "evals_list_ui_scenarios", "evals_get_ui_scenario",
    "evals_add_scenario_action", "evals_add_scenario_assertion",
    "evals_run_ui_exploration", "evals_list_ui_findings",
}


@pytest.fixture(autouse=True)
def isolated_ui_explorer(monkeypatch):
    monkeypatch.setattr(ui_scenario_tools, "_ui_explorer", None)


def _run(name: str, arguments: dict):
    result = asyncio.run(create_server().call_tool(name, arguments))
    return result.structured_content


def test_ui_tools_publish_flat_v1_envelopes_and_share_one_explorer() -> None:
    for name in _TOOLS:
        assert asyncio.run(create_server().get_tool(name)) is not None

    created = _run("evals_create_ui_scenario", {"name": "Login", "route": "/login"})
    assert created["ok"] is True
    scenario_id = created["data"]["id"]

    action = _run("evals_add_scenario_action", {
        "scenario_id": scenario_id, "action_type": "click", "target": "submit",
    })
    assert action["ok"] is True
    assert action["data"]["action_added"]["type"] == "click"

    scenario = _run("evals_get_ui_scenario", {"scenario_id": scenario_id})
    assert scenario["ok"] is True
    assert scenario["data"]["actions"] == [action["data"]["action_added"]]

    findings = _run("evals_list_ui_findings", {"run_id": "unknown"})
    assert findings["ok"] is True
    assert findings["data"] == {"run_id": "unknown", "findings": [], "count": 0}


def test_ui_tools_return_failed_envelopes_for_legacy_top_level_errors() -> None:
    missing = _run("evals_get_ui_scenario", {"scenario_id": "missing"})
    assert missing == {
        "schema_version": "v1", "ok": False, "data": None,
        "error": "Scenario not found: missing", "idempotency_key": None,
    }
    unknown = _run("evals_add_scenario_action", {
        "scenario_id": _run("evals_create_ui_scenario", {"name": "A", "route": "/"})["data"]["id"],
        "action_type": "unknown",
    })
    assert unknown["ok"] is False
    assert unknown["data"] is None
    assert unknown["error"] == "Unknown action type: unknown"


def test_ui_boundary_rejects_unknown_flat_fields() -> None:
    with pytest.raises(Exception):
        _run("evals_create_ui_scenario", {
            "name": "Login", "route": "/login", "unexpected": True,
        })
    with pytest.raises(Exception):
        _run("evals_run_ui_exploration", {
            "scenario_id": "missing", "context": {}, "unexpected": True,
        })
