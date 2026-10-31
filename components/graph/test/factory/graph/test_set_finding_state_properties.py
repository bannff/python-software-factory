"""Concurrency/atomicity property tests for graph_set_finding_state.

Canary for bd python-factory-216ti Contract B: the atomic single-write
finding-state setter must close the r1pbn/xn0j9 read-modify-write race.
Under concurrent writers the field is never LOST (it always ends with a
real state) and the final value is exactly ONE of the writes — never a
torn/blended value.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from hypothesis import given, settings, strategies as st

from factory.graph.core import FINDING_STATES
from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity

_settings = settings(max_examples=60, deadline=None)
_states = st.sampled_from(sorted(FINDING_STATES))


def _seed_finding(graph: NetworkXGraph, finding_id: str = "f-1") -> str:
    graph.add_entity(Entity(
        id=finding_id, type="Finding",
        properties={"id": finding_id, "state": "candidate"},
    ))
    return finding_id


class TestSetFindingStateAtomicity:
    """Atomic single-write semantics under concurrency."""

    @given(writes=st.lists(_states, min_size=1, max_size=25))
    @_settings
    def test_concurrent_sets_never_lose_state(self, writes: list[str]) -> None:
        """Concurrent writers: final state is one of the writes, never lost."""
        graph = NetworkXGraph()
        fid = _seed_finding(graph)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda s: graph.set_finding_state(fid, s), writes,
            ))

        # Every write targeted an existing node → all succeed.
        assert all(results)
        final = graph.get_entity(fid).properties["state"]
        # Field is never lost and the final value is exactly one write.
        assert final in set(writes)
        assert final in FINDING_STATES

    @given(state=_states)
    @_settings
    def test_single_set_persists_exact_value(self, state: str) -> None:
        """A single set writes exactly the requested neutral state."""
        graph = NetworkXGraph()
        fid = _seed_finding(graph)
        assert graph.set_finding_state(fid, state) is True
        assert graph.get_entity(fid).properties["state"] == state

    def test_set_missing_finding_returns_false(self) -> None:
        """Setting state on an absent finding is a no-op False (no raise)."""
        graph = NetworkXGraph()
        assert graph.set_finding_state("ghost", "verified") is False

    def test_set_does_not_mutate_other_fields(self) -> None:
        """Only ``state`` changes — sibling props are untouched."""
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="f-9", type="Finding",
            properties={"id": "f-9", "state": "candidate", "severity": "high"},
        ))
        graph.set_finding_state("f-9", "verified")
        props = graph.get_entity("f-9").properties
        assert props["state"] == "verified"
        assert props["severity"] == "high"
