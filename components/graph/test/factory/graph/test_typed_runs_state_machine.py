"""RuleBasedStateMachine: run-scoping invariant for typed graph reads.

Adding entities under arbitrary run_ids must always partition under
each typed read. Tracked under bd python-factory-j1lb.
"""

from __future__ import annotations

from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity

from ._typed_runs_fixtures import (
    LABELS, STATE_SETTINGS, apps, run_ids,
)


class RunScopingStateMachine(RuleBasedStateMachine):
    """Whatever the sequence of adds, typed reads must partition by run_id."""

    def __init__(self) -> None:
        super().__init__()
        self.graph: NetworkXGraph | None = None
        # model: {(label, run_id): set_of_entity_ids}
        self.model: dict[tuple[str, str], set[str]] = {}

    @initialize()
    def init_graph(self) -> None:
        self.graph = NetworkXGraph()
        self.model = {}

    @rule(
        run_id=run_ids,
        label=st.sampled_from(LABELS),
        suffix=st.integers(min_value=0, max_value=99),
        app=apps,
    )
    def add_run_scoped_entity(
        self, run_id: str, label: str, suffix: int, app: str,
    ) -> None:
        eid = f"{label.lower()}-{run_id}-{suffix}"
        if eid in self.model.get((label, run_id), set()):
            return  # idempotent under our model
        self.graph.add_entity(Entity(
            id=eid, type=label,
            properties={
                "id": eid, "run_id": run_id, "app": app,
                "severity": "high", "verdict": "true_positive",
                "created_at": f"2026-01-01T00:00:{suffix:02d}Z",
                # bd python-factory-ttq8: SAST code-evidence fields.
                "file": f"{label.lower()}-{suffix}.java",
                "function": f"fn_{suffix}",
                "line_start": suffix, "line_end": suffix + 1,
                "agent_id": f"agent-{suffix}",
                "vuln_class": "IDOR",
            },
        ))
        self.model.setdefault((label, run_id), set()).add(eid)

    @invariant()
    def findings_partition_correctly(self) -> None:
        for run_id in ("run-a", "run-b", "run-c"):
            expected = self.model.get(("Finding", run_id), set())
            rows = list(self.graph.get_findings_for_run(
                run_id, limit=10_000,
            ).raw or [])
            ids = {str(r.get("id")) for r in rows}
            assert ids == expected, (
                f"Finding partition mismatch for {run_id}: {ids} != {expected}"
            )
            # bd python-factory-ttq8: SAST code-evidence fields must
            # always be in the projection — even on Finding rows the
            # state machine never opted them in (None projects None,
            # but key must be present so SAST scorer key tuple is built).
            for r in rows:
                for key in ("file", "function", "line_start", "line_end",
                            "agent_id", "vuln_class"):
                    assert key in r, f"missing {key} in projected row"

    @invariant()
    def counts_match_model(self) -> None:
        labels = list(LABELS)
        for run_id in ("run-a", "run-b", "run-c"):
            counts = self.graph.count_entities_by_run(run_id, labels)
            for label in labels:
                expected = len(self.model.get((label, run_id), set()))
                assert counts[label] == expected, (
                    f"{label}/{run_id}: got {counts[label]} != {expected}"
                )

    @invariant()
    def tool_invocations_filter_by_run(self) -> None:
        # The rule never creates ToolInvocation nodes, so the typed
        # query must always return zero rows. Guards against accidental
        # cross-label leakage in the implementation.
        for run_id in ("run-a", "run-b", "run-c"):
            rows = list(self.graph.get_tool_invocations_for_run(
                run_id, limit=10_000,
            ).raw or [])
            assert rows == []


_RECENT_TOOL_NAMES = (
    "agent_reason", "kb_search", "graph_get_findings_for_run",
    "memory_retrieve", "security_scan",
)


class RecentInvocationsStateMachine(RuleBasedStateMachine):
    """bd python-factory-c39g: list_recent always sorts DESC, honours limit."""

    def __init__(self) -> None:
        super().__init__()
        self.graph: NetworkXGraph | None = None
        self.timestamps: list[str] = []

    @initialize()
    def init_graph(self) -> None:
        self.graph = NetworkXGraph()
        self.timestamps = []

    @rule(
        run_id=run_ids,
        tool=st.sampled_from(_RECENT_TOOL_NAMES),
        suffix=st.integers(min_value=0, max_value=999),
    )
    def add_invocation(self, run_id: str, tool: str, suffix: int) -> None:
        ts = f"2026-01-{(suffix % 28) + 1:02d}T{(suffix % 24):02d}:00:00Z"
        eid = f"inv-{tool}-{run_id}-{suffix}"
        self.graph.add_entity(Entity(
            id=eid, type="ToolInvocation",
            properties={
                "tool_name": tool, "workflow_run_id": run_id,
                "created_at": ts, "success": True, "latency_ms": 1,
            },
        ))
        self.timestamps.append(ts)

    @invariant()
    def list_recent_is_sorted_desc(self) -> None:
        for limit in (1, 5, 50):
            rows = list(
                self.graph.list_recent_tool_invocations(limit).raw or [],
            )
            assert len(rows) <= limit
            timestamps = [str(r.get("created_at", "")) for r in rows]
            assert timestamps == sorted(timestamps, reverse=True), (
                f"list_recent rows not DESC: {timestamps}"
            )


TestRunScopingStateful = RunScopingStateMachine.TestCase
TestRunScopingStateful.settings = STATE_SETTINGS

TestRecentInvocationsStateful = RecentInvocationsStateMachine.TestCase
TestRecentInvocationsStateful.settings = STATE_SETTINGS
