"""Legacy score projections preserve the domain-class contract."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult
from factory.evals.mcp.contracts.durable import RecordRunOutput
from factory.evals.runtime._persist_score import persist_score_result


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, tool: str, **kwargs: Any) -> ToolResult[RecordRunOutput]:
        self.calls.append((tool, kwargs))
        return ToolResult(data=RecordRunOutput(persisted=True, status="created", run_id=kwargs["run_id"]))


def _score(recorder: _Recorder, run_id: str, vuln_class: str = "", domain_class: str = "") -> None:
    assert persist_score_result(
        recorder, run_id=run_id, workflow_type="dast", target_app="WineApp",
        vuln_class=vuln_class, scoring={"f1": 0.7, "precision": 0.7, "recall": 0.7},
        domain_class=domain_class,
    )


def test_persist_score_routes_to_isolated_canonical_projection() -> None:
    recorder = _Recorder()
    _score(recorder, "run-WineApp-1", domain_class="wine")

    tool, kwargs = recorder.calls[0]
    assert tool == "evals_record_run"
    assert kwargs["record_kind"] == "evaluation_score_projection"
    assert kwargs["terminal_state"] == "scored"
    assert kwargs["score_projection"]["domain_class"] == "wine"
    assert kwargs["score_projection"]["vuln_class"] == ""


def test_persist_score_preserves_default_and_distinct_domain_class() -> None:
    recorder = _Recorder()
    _score(recorder, "run-WebGoat-1", vuln_class="IDOR")
    _score(recorder, "run-X-1", vuln_class="IDOR", domain_class="security_idor")

    default, distinct = [call[1]["score_projection"] for call in recorder.calls]
    assert default["domain_class"] == ""
    assert default["vuln_class"] == "IDOR"
    assert distinct["domain_class"] == "security_idor"
    assert distinct["vuln_class"] == "IDOR"


def test_persist_score_returns_false_on_empty_run_id() -> None:
    recorder = _Recorder()
    assert not persist_score_result(
        recorder, run_id="", workflow_type="dast", target_app="X", vuln_class="", scoring={},
        domain_class="wine",
    )
    assert recorder.calls == []
