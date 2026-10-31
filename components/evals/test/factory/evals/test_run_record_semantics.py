"""Trust-boundary semantics for canonical immutable Evals records."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
import pytest

from factory.evals.mcp.run_record_tools import register


def _tool(invoker):
    mcp = ToolCatalog("record-semantics")
    register(mcp)
    tool = asyncio.run(mcp.get_tool("evals_record_run"))
    def call(**kwargs):
        result = tool.fn(**kwargs).model_dump(mode="json")
        assert result["ok"] is True
        return result["data"]
    return call


def _store(calls):
    def invoker(name: str, **kwargs):
        calls.append((name, kwargs))
        return {"status": "created"}
    return invoker


def _valid(**extra):
    return {
        "run_id": "run", "experiment_name": "exp", "verdict": "FAIL",
        "pass_rate": 0.5, "avg_score": 0.5, "total_cases": 2, "passed": 1,
        "failed_cases": 1,
        "case_results": [
            {"passed": True, "score": 1.0},
            {"passed": False, "score": 0.0},
        ],
        "case_scores": [1.0, 0.0],
        **extra,
    }


def test_valid_nonempty_and_zero_case_runs_persist() -> None:
    calls = []
    invoker = _store(calls)
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        nonempty = record(**_valid())
        empty = record(
            run_id="empty", experiment_name="exp", verdict="FAIL",
            pass_rate=0.0, avg_score=0.0, total_cases=0, passed=0,
            case_results=[], case_scores=[],
        )
    assert nonempty["persisted"] and empty["persisted"]
    assert [call[1]["doc_id"] for call in calls] == ["eval-v2-run", "eval-v2-empty"]


def test_explicit_failed_zero_is_not_treated_as_omitted() -> None:
    calls = []
    invoker = _store(calls)
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = _tool(invoker)(**_valid(failed_cases=0))
    assert not result["persisted"]
    assert "passed_cases + failed_cases" in result["reason"]
    assert calls == []


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"pass_rate": 1.0}, "pass_rate"),
        ({"avg_score": 0.75}, "avg_score"),
        ({"verdict": "PASS"}, "verdict"),
        ({"case_scores": [0.0, 1.0]}, "case_scores"),
        ({"case_results": [{"passed": True, "score": 1.0}]}, "lengths"),
    ],
)
def test_inconsistent_run_is_rejected_before_storage(changes, reason) -> None:
    calls = []
    invoker = _store(calls)
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = _tool(invoker)(**_valid(**changes))
    assert not result["persisted"]
    assert result["reason"].startswith("invalid evaluation_run:")
    assert reason in result["reason"]
    assert calls == []


def test_zero_case_pass_is_rejected() -> None:
    calls = []
    invoker = _store(calls)
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = _tool(invoker)(
            run_id="empty", experiment_name="exp", verdict="PASS",
            pass_rate=0.0, avg_score=0.0, total_cases=0, passed=0,
            case_results=[], case_scores=[],
        )
    assert not result["persisted"]
    assert "verdict must be FAIL" in result["reason"]
    assert calls == []


def test_zero_population_score_projection_remains_scored_and_isolated() -> None:
    calls = []
    invoker = _store(calls)
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = _tool(invoker)(
            run_id="score", experiment_name="score:run", verdict="SCORED",
            pass_rate=0.0, avg_score=0.0, total_cases=0, passed=0,
            record_kind="evaluation_score_projection", terminal_state="scored",
            score_projection={"f1": 0.0},
        )
    assert result["persisted"]
    assert result["doc_id"] == "eval-score-v2-score"
    assert calls[0][1]["data"]["verdict"] == "SCORED"
