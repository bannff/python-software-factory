"""Pin ``_count_findings`` reads the canonical ``Finding`` label.

Properties (behavioral): the typed Graph count read receives the requested
labels, sums only those labels, and ignores stale buckets.
"""
from __future__ import annotations

from typing import Any, Callable

from hypothesis import given, settings, strategies as st

from factory.events.runtime.dispatch_args import _count_findings
from factory.graph.mcp.evidence_models import CountsData
from factory.mcp_utils.runtime.tool_result import ToolResult


def _count_result(
    *, run_id: str, labels: list[str], counts: dict[str, int],
) -> ToolResult[CountsData]:
    """Build the public envelope and DTO returned by the canonical Graph read."""
    return ToolResult(data=CountsData(
        run_id=run_id, labels=labels, counts=counts, total=sum(counts.values()),
    ))


def _recorder(handlers: dict[str, Callable[..., Any]] | None = None):
    """Return an invoker and its calls."""
    handlers = handlers or {}
    calls: list[tuple[str, dict[str, Any]]] = []

    def invoker(tool_name: str, **kwargs: Any) -> Any:
        calls.append((tool_name, kwargs))
        if tool_name in handlers:
            return handlers[tool_name](**kwargs)
        raise AssertionError(f"unexpected tool: {tool_name}")

    return invoker, calls


def test_count_findings_requests_finding_label_not_vulnerability() -> None:
    invoker, calls = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": 5, "ProvenExploit": 3},
        ),
    })
    assert _count_findings(invoker, "run-x") == 8
    assert calls == [(
        "graph_count_entities_by_run",
        {"run_id": "run-x", "labels": ["Finding", "ProvenExploit"]},
    )]


def test_count_findings_returns_zero_for_stale_vulnerability_label() -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Vulnerability": 5},
        ),
    })
    assert _count_findings(invoker, "run-x") == 0


def test_count_findings_sums_finding_plus_proven_exploit() -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": 7, "ProvenExploit": 0},
        ),
    })
    assert _count_findings(invoker, "run-y") == 7

    invoker2, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": 0, "ProvenExploit": 4},
        ),
    })
    assert _count_findings(invoker2, "run-z") == 4


def test_count_findings_no_run_id_skips_invoke() -> None:
    invoker, calls = _recorder()
    assert _count_findings(invoker, "") == 0
    assert calls == []


def test_count_findings_handles_invoker_failure() -> None:
    def boom(**_kw: Any) -> ToolResult[CountsData]:
        raise RuntimeError("graph backend down")

    invoker, _ = _recorder({"graph_count_entities_by_run": boom})
    assert _count_findings(invoker, "run-x") == 0


def test_count_findings_failed_envelope_returns_zero() -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **_kw: ToolResult(
            ok=False, data=None, error="graph unavailable",
        ),
    })
    assert _count_findings(invoker, "run-x") == 0


@settings(max_examples=50, deadline=None)
@given(
    finding=st.integers(min_value=0, max_value=500),
    proven=st.integers(min_value=0, max_value=500),
    vuln=st.integers(min_value=0, max_value=500),
)
def test_count_findings_ignores_vulnerability_in_payload(
    finding: int, proven: int, vuln: int,
) -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={
                "Finding": finding,
                "ProvenExploit": proven,
                "Vulnerability": vuln,
            },
        ),
    })
    assert _count_findings(invoker, "run-h") == finding + proven
