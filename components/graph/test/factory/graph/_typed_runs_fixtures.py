"""Shared Hypothesis strategies and helpers for typed-runs tests.

Used by ``test_typed_runs_properties.py`` (round-trip / filter / sort /
limit invariants) and ``test_typed_runs_state_machine.py`` (run-scoping
RuleBasedStateMachine). Tracked under bd python-factory-j1lb.
"""

from __future__ import annotations

from hypothesis import settings, strategies as st

from factory.graph.runtime.ports import Entity


SETTINGS = settings(max_examples=75, deadline=None)
STATE_SETTINGS = settings(
    max_examples=40, stateful_step_count=30, deadline=None,
)

run_ids = st.sampled_from(["run-a", "run-b", "run-c"])
apps = st.sampled_from(["app1", "app2", "app3"])
severities = st.sampled_from(["critical", "high", "medium", "low", "info"])
created_at = st.builds(
    lambda i: f"2026-01-01T00:00:{i:02d}Z",
    st.integers(min_value=0, max_value=59),
)
LABELS = (
    "SuspectedVuln", "Finding", "ProvenExploit",
    "EndpointInventory", "TargetApp",
)


def make_finding(
    fid: str, run_id: str, app: str = "", severity: str = "high",
    created: str = "2026-01-01T00:00:00Z", verdict: str = "true_positive",
) -> Entity:
    return Entity(
        id=fid, type="Finding",
        properties={
            "id": fid, "run_id": run_id, "app": app,
            "severity": severity, "created_at": created,
            "verdict": verdict, "title": fid,
        },
    )
