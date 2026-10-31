"""Focused typed-boundary tests for the evaluator/session/CAN tool family."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.evals.interface import create_server
from factory.evals.mcp.session_tools import register
from factory.evals.runtime.runtime import reset_runtime

_NAMES = {
    "evals_evaluate", "evals_evaluate_multi", "evals_evaluate_computational",
    "evals_evaluate_can_model", "evals_evaluate_can_model_evidence",
    "evals_evaluate_session",
}


@pytest.fixture(autouse=True)
def reset_state():
    reset_runtime()
    yield
    reset_runtime()


def _run(name: str, arguments: dict):
    tool = asyncio.run(create_server().get_tool(name))
    return tool.fn(**arguments).model_dump(mode="json")


def test_family_tools_publish_strict_typed_models() -> None:
    server = create_server()
    for name in _NAMES:
        tool = asyncio.run(server.get_tool(name))
        assert tool is not None
        assert tool.fn._mcp_input_model.model_json_schema()["additionalProperties"] is False


def test_can_metrics_and_computational_errors_use_v1_envelopes() -> None:
    metrics = _run("evals_evaluate_can_model", {
        "y_true": [0, 1], "y_pred": [0, 1], "y_score": [0.2, 0.8],
    })
    assert metrics["ok"] is True
    assert metrics["data"]["accuracy"] == 1.0
    failed = _run("evals_evaluate_computational", {
        "evaluator_name": "unknown", "y_true": [], "y_pred": [], "scores": [],
    })
    assert failed["ok"] is False
    assert failed["data"] is None
    assert "Unknown computational evaluator" in failed["error"]


def test_session_evaluator_preserves_per_evaluator_rows_as_data() -> None:
    class Runtime:
        def evaluate_with_real_session(self, *_args, **_kwargs):
            return {
                "results": [{
                    "evaluator": "output", "score": 0.0, "test_pass": False,
                    "reason": "SDK unavailable", "label": "error", "detailed_results": [],
                }],
                "summary": {
                    "avg_score": 0.0, "pass_rate": 0.0, "total_evaluators": 1,
                    "error_count": 1, "aggregation_policy": "all_requested",
                },
            }

    server = ToolCatalog("session")
    register(server, Runtime)
    tool = asyncio.run(server.get_tool("evals_evaluate_session"))
    result = tool.fn(
        input_text="input", output_text="output", evaluator_names=["output"],
    ).model_dump(mode="json")
    assert result["ok"] is True
    assert result["data"]["results"][0]["label"] == "error"


def test_family_rejects_unknown_flat_arguments() -> None:
    with pytest.raises(Exception):
        _run("evals_evaluate_can_model", {
            "y_true": [0], "y_pred": [0], "unexpected": True,
        })
