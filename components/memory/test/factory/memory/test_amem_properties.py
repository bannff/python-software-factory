"""Hypothesis property-based tests for AMemStore (ChromaDB) adapter.

Tests CRUD correctness without LLM evolution (llm_complete=None).
Mirrors test_memory_properties.py patterns adapted for ChromaDB:
- @given property tests for single-operation invariants
- RuleBasedStateMachine for random operation sequences
"""

from __future__ import annotations

import tempfile

chromadb = __import__("pytest").importorskip("chromadb")

from hypothesis import given, settings, strategies as st, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

# ChromaDB PersistentClient has disk I/O — disable deadline checks
_amem_settings = settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])

from factory.memory.core import MemoryCategory
from factory.memory.runtime.adapters.amem import AMemStore

# ── Strategies ──────────────────────────────────────────────────────────

user_ids = st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N")))
contents = st.text(min_size=1, max_size=100)
memory_types = st.sampled_from(["short_term", "long_term", "episodic"])
categories = st.sampled_from(["preference", "fact", "summary", "context", "custom"])


def _make_store() -> AMemStore:
    _release_chromadb_cache()
    return AMemStore(storage_path=tempfile.mkdtemp(), llm_complete=None)


def _release_chromadb_cache() -> None:
    """Release ChromaDB system cache to avoid OS resource exhaustion."""
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


# ── @given property tests ─────────────────────────────────────────────


class TestAMemProperties:
    """Property-based tests for individual AMemStore operations."""

    @given(user_id=user_ids, content=contents, cat=categories, mtype=memory_types)
    @_amem_settings
    def test_store_then_get_roundtrip(self, user_id, content, cat, mtype):
        """Stored memory is retrievable by ID with matching fields."""
        store = _make_store()
        mem = store.store(user_id, content, memory_type=mtype, category=cat)
        got = store.get(mem.id)
        assert got is not None
        assert got.user_id == user_id
        assert got.content == content
        assert got.category == MemoryCategory(cat)
        assert got.memory_type == mtype

    @given(user_id=user_ids, content=contents)
    @_amem_settings
    def test_store_delete_get_returns_none(self, user_id, content):
        """Deleted memory is no longer retrievable."""
        store = _make_store()
        mem = store.store(user_id, content)
        assert store.delete(mem.id) is True
        assert store.get(mem.id) is None

    @given(user_id=user_ids, items=st.lists(contents, min_size=0, max_size=10))
    @_amem_settings
    def test_list_all_count_matches(self, user_id, items):
        """list_all returns exactly the number of stored memories."""
        store = _make_store()
        for c in items:
            store.store(user_id, c)
        assert len(store.list_all(user_id, limit=1000)) == len(items)

    @given(user_id=user_ids, items=st.lists(contents, min_size=0, max_size=10))
    @_amem_settings
    def test_delete_user_memories_removes_all(self, user_id, items):
        """delete_user_memories removes every memory for that user."""
        store = _make_store()
        for c in items:
            store.store(user_id, c)
        removed = store.delete_user_memories(user_id)
        assert removed == len(items)
        assert store.list_all(user_id) == []

    @given(user_id=user_ids, items=st.lists(contents, min_size=0, max_size=10))
    @_amem_settings
    def test_stats_total_matches_count(self, user_id, items):
        """stats().total_memories equals the number of stored memories."""
        store = _make_store()
        for c in items:
            store.store(user_id, c)
        assert store.stats(user_id).total_memories == len(items)

    @given(user_id=user_ids, n=st.integers(min_value=0, max_value=5))
    @_amem_settings
    def test_consolidate_promotes_short_term(self, user_id, n):
        """consolidate converts all short_term memories to long_term."""
        store = _make_store()
        for i in range(n):
            store.store(user_id, f"m{i}", memory_type="short_term")
        store.store(user_id, "lt", memory_type="long_term")
        count = store.consolidate(user_id)
        assert count == n
        for m in store.list_all(user_id, limit=1000):
            assert m.memory_type == "long_term"


# ── RuleBasedStateMachine ─────────────────────────────────────────────


class AMemStoreMachine(RuleBasedStateMachine):
    """Stateful test: random operation sequences must keep invariants."""

    def __init__(self):
        super().__init__()
        self.store: AMemStore | None = None
        self.model: dict[str, tuple[str, str, str]] = {}  # id → (user, content, type)

    @initialize()
    def init_store(self):
        self.store = _make_store()
        self.model = {}

    def teardown(self):
        _release_chromadb_cache()

    @rule(uid=user_ids, content=contents, cat=categories, mtype=memory_types)
    def do_store(self, uid, content, cat, mtype):
        mem = self.store.store(uid, content, memory_type=mtype, category=cat)
        self.model[mem.id] = (uid, content, mtype)

    @rule()
    def do_get_existing(self):
        if not self.model:
            return
        mid = next(iter(self.model))
        got = self.store.get(mid)
        assert got is not None, f"{mid} should exist"
        uid, content, _ = self.model[mid]
        assert got.user_id == uid
        assert got.content == content

    @rule()
    def do_delete_existing(self):
        if not self.model:
            return
        mid = next(iter(self.model))
        assert self.store.delete(mid) is True
        del self.model[mid]

    @rule(uid=user_ids)
    def do_delete_user(self, uid):
        removed = self.store.delete_user_memories(uid)
        expected = sum(1 for u, _, _ in self.model.values() if u == uid)
        assert removed == expected
        self.model = {k: v for k, v in self.model.items() if v[0] != uid}

    @rule(uid=user_ids)
    def do_list_all(self, uid):
        expected = sum(1 for u, _, _ in self.model.values() if u == uid)
        assert len(self.store.list_all(uid, limit=10000)) == expected

    @invariant()
    def stats_match_model(self):
        if self.store is None:
            return
        assert self.store.stats().total_memories == len(self.model)

    @invariant()
    def every_model_entry_retrievable(self):
        if self.store is None:
            return
        for mid in self.model:
            assert self.store.get(mid) is not None, f"{mid} should exist"

    @invariant()
    def no_phantom_memories(self):
        if self.store is None:
            return
        assert self.store.stats().total_memories == len(self.model)


TestAMemStoreStateful = AMemStoreMachine.TestCase
TestAMemStoreStateful.settings = settings(max_examples=10, stateful_step_count=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
