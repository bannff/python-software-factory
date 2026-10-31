"""Property tests for CheckpointStore local filesystem backend.

Verifies:
- Save/load roundtrip preserves data for all checkpoint types
- List returns all saved checkpoints, filterable by type
- Cleanup respects keep_best_n and older_than_days thresholds
- Empty store operations are safe (no crashes on list/cleanup)
"""

from __future__ import annotations

import tempfile
import time

from hypothesis import given, settings, strategies as st

from factory.machine_learning.runtime.adapters.checkpoint_store import CheckpointStore
from factory.machine_learning.runtime.models import CheckpointType

_cp_types = st.sampled_from(list(CheckpointType))
_job_ids = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_step_names = st.text(
    min_size=1, max_size=15,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_data = st.binary(min_size=0, max_size=1000)


def _make_store() -> CheckpointStore:
    return CheckpointStore(base_path=tempfile.mkdtemp())


@settings(max_examples=50)
@given(job_id=_job_ids, step=_step_names, data=_data, cp_type=_cp_types)
def test_save_load_roundtrip(job_id, step, data, cp_type):
    """Saved data must be loadable and identical."""
    store = _make_store()
    path = store.save(job_id, step, data, cp_type)
    loaded = store.load(path)
    assert loaded == data


@settings(max_examples=50)
@given(job_id=_job_ids, cp_type=_cp_types)
def test_list_empty_job(job_id, cp_type):
    """Listing checkpoints for a non-existent job returns empty list."""
    store = _make_store()
    assert store.list(job_id, cp_type) == []


@settings(max_examples=30)
@given(
    job_id=_job_ids,
    items=st.lists(
        st.tuples(_step_names, _data, _cp_types), min_size=1, max_size=8,
    ),
)
def test_list_returns_all_saved(job_id, items):
    """Every saved checkpoint appears in the unfiltered list."""
    store = _make_store()
    saved_paths = set()
    for step, data, cp_type in items:
        path = store.save(job_id, step, data, cp_type)
        saved_paths.add(path)
    listed = store.list(job_id)
    listed_paths = {entry["path"] for entry in listed}
    assert saved_paths == listed_paths


@settings(max_examples=30)
@given(
    job_id=_job_ids,
    items=st.lists(
        st.tuples(_step_names, _data, _cp_types), min_size=1, max_size=8,
    ),
    filter_type=_cp_types,
)
def test_list_filters_by_type(job_id, items, filter_type):
    """Filtered list only returns checkpoints of the requested type."""
    store = _make_store()
    for step, data, cp_type in items:
        store.save(job_id, step, data, cp_type)
    listed = store.list(job_id, checkpoint_type=filter_type)
    for entry in listed:
        assert entry["type"] == filter_type.value


@settings(max_examples=30)
@given(job_id=_job_ids, keep_best_n=st.integers(min_value=0, max_value=5))
def test_cleanup_respects_keep_best_n(job_id, keep_best_n):
    """Cleanup never deletes the newest keep_best_n per type-dir."""
    import json
    from pathlib import Path

    base = tempfile.mkdtemp()
    store = CheckpointStore(base_path=base)
    cp_type = CheckpointType.training_checkpoint
    # Save several checkpoints with old timestamps
    for i in range(6):
        store.save(job_id, f"step{i}", b"x", cp_type)
    # Force all meta timestamps to be old (use the known base_path)
    job_dir = Path(base) / job_id / cp_type.value
    for meta in job_dir.glob("*.meta.json"):
        m = json.loads(meta.read_text())
        m["created"] = time.time() - 100 * 86400  # 100 days ago
        meta.write_text(json.dumps(m))
    deleted = store.cleanup(older_than_days=1, keep_best_n=keep_best_n)
    remaining = store.list(job_id, cp_type)
    assert len(remaining) >= min(keep_best_n, 6)
    assert deleted <= max(0, 6 - keep_best_n)


def test_load_nonexistent_returns_none():
    """Loading a path that doesn't exist returns None."""
    store = _make_store()
    assert store.load("/tmp/nonexistent_checkpoint_xyz") is None


def test_cleanup_empty_store():
    """Cleanup on an empty store returns 0 and doesn't crash."""
    store = _make_store()
    assert store.cleanup(older_than_days=0, keep_best_n=0) == 0
