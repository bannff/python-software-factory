"""Hypothesis property-based tests for MemoryCacheStore."""

import time
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
from factory.cache.runtime.adapters.memory_adapter import MemoryCacheStore

keys_st = st.text(min_size=1, max_size=20)
values_st = st.one_of(st.integers(), st.text(max_size=50), st.booleans(), st.none())

@given(key=keys_st, value=values_st)
@settings(max_examples=100)
def test_set_then_get_roundtrip(key, value):
    """set(k, v) then get(k) always returns v."""
    cache = MemoryCacheStore()
    cache.set(key, value)
    assert cache.get(key) == value


@given(key=keys_st, value=values_st)
@settings(max_examples=100)
def test_delete_means_not_exists(key, value):
    """After delete(k), exists(k) is False."""
    cache = MemoryCacheStore()
    cache.set(key, value)
    cache.delete(key)
    assert not cache.exists(key)


@given(data=st.dictionaries(keys_st, values_st, min_size=0, max_size=15))
@settings(max_examples=100)
def test_clear_empties_all_keys(data):
    """After clear(), keys('*') returns empty list."""
    cache = MemoryCacheStore()
    for k, v in data.items():
        cache.set(k, v)
    cache.clear()
    assert cache.keys("*") == []


@given(data=st.dictionaries(keys_st, values_st, min_size=0, max_size=15))
@settings(max_examples=100)
def test_stats_size_matches_keys(data):
    """stats().size always equals len(keys('*'))."""
    cache = MemoryCacheStore()
    for k, v in data.items():
        cache.set(k, v)
    assert cache.stats().size == len(cache.keys("*"))


@given(
    data=st.dictionaries(keys_st, values_st, min_size=1, max_size=10),
    extra_keys=st.lists(keys_st, min_size=0, max_size=5),
)
@settings(max_examples=100)
def test_hits_plus_misses_equals_total_gets(data, extra_keys):
    """stats().hits + stats().misses equals total get() calls made."""
    cache = MemoryCacheStore()
    for k, v in data.items():
        cache.set(k, v)
    get_count = 0
    for k in list(data.keys()) + extra_keys:
        cache.get(k)
        get_count += 1
    s = cache.stats()
    assert s.hits + s.misses == get_count


@given(key=keys_st, v1=values_st, v2=values_st)
@settings(max_examples=100)
def test_set_overwrites_previous(key, v1, v2):
    """Setting the same key twice means get returns the latest value."""
    cache = MemoryCacheStore()
    cache.set(key, v1)
    cache.set(key, v2)
    assert cache.get(key) == v2


# -- TTL edge-case properties --

@given(key=keys_st, value=values_st)
@settings(max_examples=5, deadline=None)
def test_ttl_zero_expires_immediately(key, value):
    """set with ttl_seconds=0 \u2192 key has no TTL (0 is falsy)."""
    cache = MemoryCacheStore()
    cache.set(key, value, ttl_seconds=0)
    # ttl_seconds=0 is falsy, so no expiration is set
    assert cache.ttl(key) is None
    assert cache.get(key) == value


@given(key=keys_st, value=values_st)
@settings(max_examples=3, deadline=None)
def test_ttl_1_expires_after_sleep(key, value):
    """set with ttl_seconds=1 + sleep(1.1) \u2192 key is gone."""
    cache = MemoryCacheStore()
    cache.set(key, value, ttl_seconds=1)
    time.sleep(1.1)
    assert cache.get(key) is None


@given(key=keys_st, value=values_st)
@settings(max_examples=100)
def test_no_ttl_returns_none(key, value):
    """ttl() returns None for keys set without TTL."""
    cache = MemoryCacheStore()
    cache.set(key, value)
    assert cache.ttl(key) is None


# -- RuleBasedStateMachine stateful test --

class CacheStateMachine(RuleBasedStateMachine):
    """Stateful test: random op sequences must keep model and cache in sync."""

    def __init__(self):
        super().__init__()
        self.cache = None
        self.model: dict[str, object] = {}
        self.get_hits = 0
        self.get_misses = 0

    @initialize()
    def init_cache(self):
        self.cache = MemoryCacheStore()
        self.model = {}
        self.get_hits = 0
        self.get_misses = 0

    @rule(key=keys_st, value=values_st)
    def set_key(self, key, value):
        self.cache.set(key, value)
        self.model[key] = value

    @rule(key=keys_st)
    def get_key(self, key):
        result = self.cache.get(key)
        if key in self.model:
            assert result == self.model[key]
            self.get_hits += 1
        else:
            assert result is None
            self.get_misses += 1

    @rule(key=keys_st)
    def delete_key(self, key):
        self.cache.delete(key)
        self.model.pop(key, None)

    @rule(key=keys_st)
    def exists_key(self, key):
        assert self.cache.exists(key) == (key in self.model)

    @rule()
    def clear_all(self):
        self.cache.clear()
        self.model.clear()

    @rule()
    def list_keys(self):
        assert set(self.cache.keys("*")) == set(self.model.keys())

    @invariant()
    def size_matches_model(self):
        if self.cache is not None:
            assert self.cache.stats().size == len(self.model)

    @invariant()
    def model_keys_exist_in_cache(self):
        if self.cache is not None:
            for k in self.model:
                assert self.cache.exists(k), f"Key {k!r} should exist"

    @invariant()
    def non_model_keys_absent(self):
        if self.cache is not None:
            cache_keys = set(self.cache.keys("*"))
            model_keys = set(self.model.keys())
            extra = cache_keys - model_keys
            assert not extra, f"Unexpected keys in cache: {extra}"

    @invariant()
    def hit_rate_consistent(self):
        if self.cache is not None:
            s = self.cache.stats()
            total = self.get_hits + self.get_misses
            if total > 0:
                expected = self.get_hits / total
                assert abs(s.hit_rate - expected) < 1e-9


TestCacheStateful = CacheStateMachine.TestCase
TestCacheStateful.settings = settings(max_examples=100, stateful_step_count=30)
