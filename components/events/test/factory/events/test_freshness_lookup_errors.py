"""Freshness lookup contract: registered evals tool, loud failures (#408)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pydantic import BaseModel

from factory.events.runtime.freshness_handler import handle_freshness_check
from factory.events.runtime.models import Event
from factory.mcp_utils.runtime.tool_result import ToolResult


class _RunList(BaseModel):
    runs: list[dict]
    count: int = 0


def _run(target: str, epoch: float) -> dict:
    ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    return {"run_id": f"r-{int(epoch)}", "experiment_name": f"score:security-scan:{target}", "timestamp": ts}


def _runs_result(*runs: dict) -> ToolResult:
    return ToolResult(data=_RunList(runs=list(runs)))


def _make_event(event_type: str = "graph.completed") -> Event:
    return Event(type=event_type, source="test", payload={
        "run_id": "run-123", "workflow_id": "wf-abc", "target_app": "my-experiment",
        "workflow_type": "security-scan",
    })


class TestLookupSelection:
    def test_other_targets_runs_do_not_make_target_fresh(self):
        now = time.time()
        invoker = MagicMock(side_effect=lambda tool, **kw: (
            _runs_result(_run("someone-else", now - 5)) if tool == "evals_list_run_results" else None
        ))
        result = handle_freshness_check(_make_event("swarm.completed"), invoker)
        assert result["action"] == "triggered"
        assert result["last_eval_ts"] is None

    def test_newest_matching_run_wins(self):
        now = time.time()
        invoker = MagicMock(side_effect=lambda tool, **kw: (
            _runs_result(_run("my-experiment", now - 99999), _run("my-experiment", now - 30))
            if tool == "evals_list_run_results" else None
        ))
        result = handle_freshness_check(_make_event(), invoker)
        assert result["action"] == "skipped_fresh"

    def test_lookup_uses_only_registered_evals_tool(self):
        invoker = MagicMock(side_effect=lambda tool, **kw: _runs_result())
        handle_freshness_check(_make_event(), invoker)
        assert invoker.call_args_list[0][0][0] == "evals_list_run_results"


class TestLookupFailureIsLoud:
    """A failed lookup is an error, never a silent 'stale' verdict."""

    def test_failed_tool_result_reports_error_and_does_not_persist(self, caplog):
        invoker = MagicMock(side_effect=lambda tool, **kw: (
            ToolResult(ok=False, data=None, error="unavailable") if tool == "evals_list_run_results" else None
        ))
        with caplog.at_level("ERROR"):
            result = handle_freshness_check(_make_event("swarm.completed"), invoker)
        assert result["action"] == "error"
        assert "evals_list_run_results" in result["error"]
        assert not [c for c in invoker.call_args_list if c[0][0] == "evals_persist_score"]
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_unknown_tool_error_is_not_masked(self):
        def _invoker(tool, **kw):
            raise KeyError(f"unknown tool {tool}")
        result = handle_freshness_check(_make_event(), _invoker)
        assert result["action"] == "error"


class TestLookupException:
    def test_lookup_exception_reports_error_without_raising(self):
        def _invoker(tool, **kwargs):
            if tool == "evals_list_run_results":
                raise ConnectionError("timeout")
            return None

        result = handle_freshness_check(_make_event("graph.completed"), _invoker)
        assert result["action"] == "error"
        assert "timeout" in result["error"]
