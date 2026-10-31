"""
Property-based tests for LocalBlobStore using Hypothesis.

Tests that the LocalBlobStore maintains valid state across
arbitrary sequences of operations with fuzzed inputs.
"""

import tempfile

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.storage.runtime.adapters.blob_local import LocalBlobStore

# --- Strategies ---
blob_keys = st.text(
    min_size=1, max_size=15,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
blob_data = st.binary(min_size=0, max_size=1000)


def make_store() -> LocalBlobStore:
    """Create a fresh store in a unique temp directory."""
    return LocalBlobStore(root_path=tempfile.mkdtemp())


# --- @given property tests ---

@given(key=blob_keys, data=blob_data)
@settings(max_examples=50)
def test_put_then_get_roundtrip(key: str, data: bytes) -> None:
    """put(k, d) then get(k) returns the same bytes."""
    store = make_store()
    store.put(key, data)
    content, _ = store.get(key)
    assert content == data


@given(key=blob_keys, data=blob_data)
@settings(max_examples=50)
def test_put_then_exists(key: str, data: bytes) -> None:
    """put(k, d) then exists(k) returns True."""
    store = make_store()
    store.put(key, data)
    assert store.exists(key)


@given(key=blob_keys, data=blob_data)
@settings(max_examples=50)
def test_delete_then_not_exists(key: str, data: bytes) -> None:
    """put(k) then delete(k) then exists(k) returns False."""
    store = make_store()
    store.put(key, data)
    store.delete(key)
    assert not store.exists(key)


@given(key=blob_keys, data=blob_data)
@settings(max_examples=50)
def test_put_metadata_has_correct_size(key: str, data: bytes) -> None:
    """put(k, d) metadata.size == len(d)."""
    store = make_store()
    meta = store.put(key, data)
    assert meta.size == len(data)
    _, get_meta = store.get(key)
    assert get_meta.size == len(data)


@given(
    keys=st.lists(blob_keys, min_size=1, max_size=10, unique=True),
    prefix=blob_keys,
    data=blob_data,
)
@settings(max_examples=50)
def test_list_keys_prefix_filter(
    keys: list[str], prefix: str, data: bytes,
) -> None:
    """list_keys(prefix=X) only returns keys starting with X."""
    store = make_store()
    for k in keys:
        store.put(k, data)
    results = store.list_keys(prefix=prefix)
    for meta in results:
        assert meta.key.startswith(prefix), (
            f"key {meta.key!r} does not start with prefix {prefix!r}"
        )


@given(key=blob_keys, data1=blob_data, data2=blob_data)
@settings(max_examples=50)
def test_put_overwrites(key: str, data1: bytes, data2: bytes) -> None:
    """put(k, d1) then put(k, d2) \u2014 get(k) returns d2."""
    store = make_store()
    store.put(key, data1)
    store.put(key, data2)
    content, _ = store.get(key)
    assert content == data2


# --- RuleBasedStateMachine stateful test ---

class BlobStoreStateMachine(RuleBasedStateMachine):
    """Stateful test: model dict tracks expected blobs."""

    def __init__(self) -> None:
        super().__init__()
        self.store: LocalBlobStore | None = None
        self.model: dict[str, bytes] = {}

    @initialize()
    def init_store(self) -> None:
        self.store = make_store()
        self.model = {}

    @rule(key=blob_keys, data=blob_data)
    def put_blob(self, key: str, data: bytes) -> None:
        meta = self.store.put(key, data)
        self.model[key] = data
        assert meta.size == len(data)

    @rule(key=blob_keys)
    def get_blob(self, key: str) -> None:
        if key in self.model:
            content, meta = self.store.get(key)
            assert content == self.model[key]
            assert meta.size == len(self.model[key])
        else:
            assert not self.store.exists(key)

    @rule(key=blob_keys)
    def delete_blob(self, key: str) -> None:
        existed = key in self.model
        result = self.store.delete(key)
        assert result == existed
        self.model.pop(key, None)

    @rule(key=blob_keys)
    def exists_blob(self, key: str) -> None:
        assert self.store.exists(key) == (key in self.model)

    @rule()
    def list_all(self) -> None:
        results = self.store.list_keys()
        assert len(results) == len(self.model)

    @invariant()
    def count_matches_model(self) -> None:
        if self.store is None:
            return
        listed = self.store.list_keys()
        assert len(listed) == len(self.model)

    @invariant()
    def every_model_key_exists(self) -> None:
        if self.store is None:
            return
        for key in self.model:
            assert self.store.exists(key), f"{key!r} should exist"

    @invariant()
    def deleted_keys_absent(self) -> None:
        if self.store is None:
            return
        listed_keys = {m.key for m in self.store.list_keys()}
        for key in listed_keys:
            assert key in self.model, f"{key!r} in store but not model"


TestBlobStoreStateful = BlobStoreStateMachine.TestCase
TestBlobStoreStateful.settings = settings(
    max_examples=50, stateful_step_count=20, deadline=None,
)
