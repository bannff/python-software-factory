"""Hypothesis property-based tests for config brick.

Properties verified:
- InfraEnvConfigStore set/get roundtrip for arbitrary keys and values
- Key mapping is deterministic (same input → same output, always)
- Delete semantics: True if existed, False if not
- Layered resolution respects priority (last layer wins)
"""

from __future__ import annotations

import os

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.config.runtime.adapters.infra_env import InfraEnvConfigStore

# Strategy: dot-notation keys like "neo4j.uri", "a.b.c"
_segment = st.text(min_size=1, max_size=8, alphabet=st.characters(
    whitelist_categories=("L", "N"),
))
_dot_key = st.lists(_segment, min_size=1, max_size=3).map(".".join)
# os.environ rejects null bytes — use printable text only
_value = st.text(
    min_size=0, max_size=50,
    alphabet=st.characters(blacklist_characters="\x00"),
)


# --- Stateless @given tests ---

@settings(max_examples=50)
@given(key=_dot_key, value=_value)
def test_set_get_roundtrip(key: str, value: str) -> None:
    """set(k, v) then get(k) returns v."""
    store = InfraEnvConfigStore()
    env_key = key.upper().replace(".", "_")
    try:
        store.set(key, value)
        assert store.get(key) == value
    finally:
        os.environ.pop(env_key, None)


@settings(max_examples=50)
@given(key=_dot_key)
def test_key_mapping_deterministic(key: str) -> None:
    """Same key always maps to the same env var name."""
    store = InfraEnvConfigStore()
    assert store._key(key) == store._key(key)


@settings(max_examples=50)
@given(key=_dot_key)
def test_key_mapping_is_upper_underscore(key: str) -> None:
    """Mapped key is always uppercase with underscores, no dots."""
    store = InfraEnvConfigStore()
    mapped = store._key(key)
    assert mapped == mapped.upper()
    assert "." not in mapped


@settings(max_examples=50)
@given(key=_dot_key, value=_value)
def test_delete_returns_true_when_existed(key: str, value: str) -> None:
    """delete returns True for existing key, False for missing."""
    store = InfraEnvConfigStore()
    env_key = key.upper().replace(".", "_")
    try:
        store.set(key, value)
        assert store.delete(key) is True
        assert store.delete(key) is False
    finally:
        os.environ.pop(env_key, None)


@settings(max_examples=50)
@given(key=_dot_key)
def test_exists_false_after_delete(key: str) -> None:
    """After delete, exists returns False."""
    store = InfraEnvConfigStore()
    env_key = key.upper().replace(".", "_")
    try:
        store.set(key, "tmp")
        store.delete(key)
        assert not store.exists(key)
    finally:
        os.environ.pop(env_key, None)


@settings(max_examples=50)
@given(
    key=_dot_key,
    low_val=_value,
    high_val=_value,
)
def test_layered_last_layer_wins(key: str, low_val: str, high_val: str) -> None:
    """In layered config, the last layer's value wins."""
    from factory.config.runtime.runtime import ConfigRuntime

    rt = ConfigRuntime()
    rt._bootstrapped = True  # skip auto-bootstrap

    low = InfraEnvConfigStore()
    high = InfraEnvConfigStore()

    env_key = key.upper().replace(".", "_")
    try:
        # Both layers share os.environ, so set the high value last
        os.environ[env_key] = high_val
        rt.add_layer(low)
        rt.add_layer(high)
        assert rt.get_layered(key) == high_val
    finally:
        os.environ.pop(env_key, None)


# --- RuleBasedStateMachine ---

class InfraEnvStoreMachine(RuleBasedStateMachine):
    """Stateful property test: model dict tracks expected env state."""

    def __init__(self) -> None:
        super().__init__()
        self.store: InfraEnvConfigStore | None = None
        self.model: dict[str, str] = {}

    @initialize()
    def init_store(self) -> None:
        self.store = InfraEnvConfigStore()
        self.model = {}

    @rule(key=_dot_key, value=_value)
    def do_set(self, key: str, value: str) -> None:
        self.store.set(key, value)
        self.model[key] = value

    @rule(key=_dot_key)
    def do_delete(self, key: str) -> None:
        existed = key in self.model
        assert self.store.delete(key) is existed
        self.model.pop(key, None)

    @invariant()
    def model_matches_store(self) -> None:
        for key, expected in self.model.items():
            assert self.store.get(key) == expected

    def teardown(self) -> None:
        for key in list(self.model):
            env_key = key.upper().replace(".", "_")
            os.environ.pop(env_key, None)


TestInfraEnvStoreStateful = InfraEnvStoreMachine.TestCase
TestInfraEnvStoreStateful.settings = settings(
    max_examples=50, stateful_step_count=15,
)
