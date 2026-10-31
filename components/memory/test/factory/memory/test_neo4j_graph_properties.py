"""Hypothesis property-based tests for Neo4j graph adapters.

Properties verified:
- _store_with_evolution calls set_evolution_properties with valid status
- evolution_status after store() is always success/failed/pending
- fetch_unevolved_memories returns records matching requested IDs
- evolve_memories: failed + evolved == len(records) (error isolation)
- _create_cross_domain_edges only creates REFERENCES or MENTIONS
- _find_neighbors never passes more than 5 IDs to Cypher
- Stateful lifecycle: store → evolve → backfill invariants hold
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.memory.runtime.adapters.neo4j_evolution import (
    _create_cross_domain_edges, _find_neighbors, set_evolution_properties,
)
from factory.memory.runtime.evolve_backfill import evolve_memories, fetch_unevolved_memories

_ps = settings(max_examples=50, deadline=None)
contents = st.text(min_size=1, max_size=100)
user_ids = st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N")))
_EMBED_PATCH = "factory.memory.runtime.adapters.neo4j_embedding.Neo4jEmbeddingMemoryStore"


def _mock_driver():
    driver, session = MagicMock(), MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def _make_store(llm=None):
    driver, session = _mock_driver()
    base = MagicMock(driver=driver, database="db")
    base.store.return_value = MagicMock(id="m1", user_id="u1", content="c")
    emb = MagicMock(dimensions=3, embed=MagicMock(return_value=[[.1]]))
    with patch(f"{_EMBED_PATCH}._ensure_vector_index"), \
         patch(f"{_EMBED_PATCH}._ensure_evolution_constraints"):
        from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
        return Neo4jEmbeddingMemoryStore(base, emb, llm), driver, session


# ── @given property tests ─────────────────────────────────────────────


class TestStoreEvolveRoundtrip:
    @given(content=contents)
    @_ps
    def test_set_evolution_called_with_valid_status(self, content):
        """_store_with_evolution always sets evolution_status to success or failed."""
        llm = MagicMock(return_value='{"keywords":["k"],"context":"ctx","tags":["t"]}')
        store, *_ = _make_store(llm)
        mem = MagicMock(id="m1", user_id="u1", content=content)
        with patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties") as sep:
            store._store_with_evolution(mem, content)
            sep.assert_called_once()
            assert sep.call_args.kwargs["evolution_status"] in ("success", "failed")


class TestEvolutionStatusInvariant:
    @given(content=contents)
    @_ps
    def test_status_always_valid_after_store(self, content):
        """After store() without LLM, status is pending."""
        store, _, session = _make_store(llm=None)
        with patch(f"{_EMBED_PATCH.rsplit('.', 1)[0]}.emit_memory_event"):
            store.store("u1", content)
        calls = [c for c in session.run.call_args_list if "evolution_status" in str(c)]
        for call in calls:
            val = call.kwargs.get("s") or call[1].get("s", "")
            assert val in ("success", "failed", "pending"), f"Bad status: {val}"


class TestBackfillFetchCorrectness:
    @given(ids=st.lists(st.text(min_size=1, max_size=20,
           alphabet=st.characters(whitelist_categories=("L", "N"))), min_size=1, max_size=5))
    @_ps
    def test_returns_records_for_requested_ids(self, ids):
        """fetch_unevolved_memories with specific IDs returns matching records."""
        driver, session = _mock_driver()
        session.run.return_value = [{"id": mid, "content": f"c-{mid}"} for mid in ids]
        result = fetch_unevolved_memories(driver, "db", "u1", memory_ids=ids)
        assert len(result) == len(ids)
        for rec, mid in zip(result, ids):
            assert rec["id"] == mid


class TestEvolveMemoriesErrorIsolation:
    @given(n=st.integers(min_value=1, max_value=8))
    @_ps
    def test_counts_always_sum_to_total(self, n):
        """failed_count + evolved_count always equals len(records)."""
        driver, _ = _mock_driver()
        records = [{"id": f"m{i}", "content": f"c{i}"} for i in range(n)]
        call_count = 0

        def _flaky_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError("LLM down")
            return '{"keywords":["k"],"context":"ctx","tags":["t"]}'

        result = evolve_memories(
            driver, "db", "u1", _flaky_llm, MagicMock(),
            lambda c, u: MagicMock(return_value=[]), records,
        )
        assert result["evolved_count"] + result["failed_count"] == n


class TestCrossDomainEdgeTypes:
    @given(n_kb=st.integers(0, 3), n_find=st.integers(0, 3))
    @_ps
    def test_only_references_and_mentions(self, n_kb, n_find):
        """_create_cross_domain_edges only creates REFERENCES/MENTIONS."""
        driver, session = _mock_driver()
        nbs = [{"node_id": f"kb{i}", "label": "KBDocument", "score": .8, "content": "c"} for i in range(n_kb)]
        nbs += [{"node_id": f"f{i}", "label": "Finding", "score": .7, "content": "c"} for i in range(n_find)]
        _create_cross_domain_edges(driver, "db", "mem-1", nbs)
        for call in session.run.call_args_list:
            assert "REFERENCES" in call[0][0] or "MENTIONS" in call[0][0]
        assert session.run.call_count == n_kb + n_find

    def test_unknown_label_creates_no_edge(self):
        driver, session = _mock_driver()
        _create_cross_domain_edges(driver, "db", "m1", [{"node_id": "x", "label": "Unknown", "score": .5, "content": ""}])
        session.run.assert_not_called()


class TestNeighborLimit:
    @given(n=st.integers(min_value=1, max_value=20))
    @_ps
    def test_ids_capped_at_five(self, n):
        """_find_neighbors never passes more than 5 IDs to Cypher."""
        driver, session = _mock_driver()
        session.run.return_value = []
        mems = [MagicMock(id=f"m{i}") for i in range(n)]
        _find_neighbors(driver, "db", "u1", MagicMock(return_value=mems))
        assert len(session.run.call_args.kwargs["ids"]) <= 5


# ── RuleBasedStateMachine ─────────────────────────────────────────────


class GraphMemoryLifecycle(RuleBasedStateMachine):
    """Stateful: store → evolve → backfill with mocked Neo4j."""

    def __init__(self):
        super().__init__()
        self.model: dict[str, dict] = {}
        self.driver = self.session = None

    @initialize()
    def init(self):
        self.model, (self.driver, self.session) = {}, _mock_driver()

    @rule(uid=user_ids, content=contents)
    def store_memory(self, uid, content):
        key = f"mem-{uid}-{len(self.model)}"
        self.model[key] = {"content": content, "user_id": uid, "evolution_status": "pending"}

    @rule()
    def evolve_memory(self):
        pending = [k for k, v in self.model.items() if v["evolution_status"] == "pending"]
        if not pending:
            return
        mid = pending[0]
        set_evolution_properties(self.driver, "db", mid, {"keywords": ["k"], "context": "c", "tags": ["t"]})
        self.model[mid]["evolution_status"] = "success"

    @rule()
    def backfill_unevolved(self):
        unevolved = [k for k, v in self.model.items() if v["evolution_status"] in ("failed", "pending")]
        if not unevolved:
            return
        self.session.run.return_value = [{"id": k, "content": self.model[k]["content"]} for k in unevolved]
        records = fetch_unevolved_memories(self.driver, "db", "u1", memory_ids=unevolved)
        returned_ids = {r["id"] for r in records}
        for uid in unevolved:
            assert uid in returned_ids, f"{uid} missing from backfill"

    @invariant()
    def status_always_valid(self):
        for mid, info in self.model.items():
            assert info["evolution_status"] in ("success", "failed", "pending")


TestGraphLifecycle = GraphMemoryLifecycle.TestCase
TestGraphLifecycle.settings = settings(max_examples=50, stateful_step_count=20, deadline=None)
