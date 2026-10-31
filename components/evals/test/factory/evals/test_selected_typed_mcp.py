"""Fresh-server envelope checks for the selected Evals typed boundary batch."""
from __future__ import annotations

import asyncio

import pytest

from factory.evals.interface import create_server
from factory.evals.runtime.runtime import reset_runtime

_SELECTED = {
    "get_capabilities", "health_check", "describe_config_schema", "evals_get_suite",
    "evals_list_suites", "evals_get_run", "evals_list_runs", "evals_score_gt",
    "evals_create_suite", "evals_delete_suite", "evals_add_case", "evals_persist_score",
    "evals_record_run", "evals_verify_record_pointer",
}


@pytest.fixture(autouse=True)
def reset_state():
    reset_runtime()
    yield
    reset_runtime()


def _run(name: str, arguments: dict):
    server = create_server()
    result = asyncio.run(server.call_tool(name, arguments))
    return result.structured_content


def test_selected_tools_publish_v1_envelopes_from_a_fresh_server() -> None:
    for name in _SELECTED:
        tool = asyncio.run(create_server().get_tool(name))
        assert tool is not None
    result = _run("evals_get_suite", {"suite_id": "missing"})
    assert result == {"schema_version": "v1", "ok": True, "data": {"found": False, "id": None, "name": None, "description": None, "case_count": None}, "error": None, "idempotency_key": None}


def test_selected_boundary_rejects_unknown_flat_fields() -> None:
    with pytest.raises(Exception):
        _run("evals_list_suites", {"unexpected": True})


def test_pointer_schema_version_remains_a_domain_integer() -> None:
    result = _run("evals_verify_record_pointer", {
        "collection": "eval_results", "doc_id": "run-1",
        "record_kind": "evaluation_run", "schema_version": 2,
        "revision": "v2", "content_hash": "0" * 64,
    })
    assert result["ok"] is True
    assert result["data"]["pointer"]["schema_version"] == 2
    with pytest.raises(Exception):
        _run("evals_verify_record_pointer", {
            "collection": "eval_results", "doc_id": "run-1",
            "record_kind": "evaluation_run", "schema_version": "2",
            "revision": "v2", "content_hash": "0" * 64,
        })


def test_representative_family_direct_ingress_rejects_scalar_coercion() -> None:
    invalid_calls = (
        ("evals_evaluate", {
            "input_text": 1, "output_text": "result", "evaluator_name": "output",
        }),
        ("evals_add_scenario_action", {
            "scenario_id": "scenario", "action_type": "click", "timeout_ms": "5",
        }),
        ("evals_sop_generate_data", {"session_id": "session", "num_cases": "1"}),
    )
    server = create_server()
    for name, arguments in invalid_calls:
        tool = asyncio.run(server.get_tool(name))
        with pytest.raises(Exception):
            tool.fn(**arguments)
