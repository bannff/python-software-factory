"""Property-based tests for sop_store.py (file-backed SOP session persistence).

Properties verified:
1. Round-trip: any SOPState saved then loaded returns an equal state
2. Sequential saves: multiple sessions saved independently are all retrievable
3. Missing file: load_all() returns empty dict when store file doesn't exist
4. Partial state: malformed entries in the JSON file are skipped gracefully
"""
from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from factory.evals.runtime.adapters import sop_store
from factory.evals.runtime.adapters.sop_adapter import SOPState

# ── strategies ───────────────────────────────────────────────────────────────

_ids = st.text(min_size=1, max_size=8, alphabet=st.characters(whitelist_categories=("L", "N")))
_short_text = st.text(min_size=0, max_size=80)
_tool_list = st.lists(st.text(min_size=1, max_size=20), max_size=5)
_phase = st.sampled_from(["plan", "data", "eval", "report", "complete"])
_str_dict = st.dictionaries(st.text(max_size=10), st.text(max_size=20), max_size=4)
_case_list = st.lists(_str_dict, max_size=3)

_sop_state = st.builds(
    SOPState,
    id=_ids,
    phase=_phase,
    agent_description=_short_text,
    agent_tools=_tool_list,
    evaluation_goals=_short_text,
    eval_plan=_str_dict,
    test_cases=_case_list,
    eval_results=_str_dict,
    report=_short_text,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _patch_paths(tmp: Path) -> tuple[Path, Path]:
    """Point sop_store module-level paths at a temp directory."""
    store = tmp / "sop_sessions.json"
    tmp_file = tmp / "sop_sessions.json.tmp"
    sop_store._STORE_PATH = store
    sop_store._TMP_PATH = tmp_file
    sop_store._cache = None  # reset in-memory cache
    return store, tmp_file


# ── tests ─────────────────────────────────────────────────────────────────────

@given(state=_sop_state)
@settings(max_examples=50)
def test_round_trip(state: SOPState) -> None:
    """Save a SOPState then load it back — must be equal."""
    with tempfile.TemporaryDirectory() as td:
        _patch_paths(Path(td))
        sop_store.save_session(state)
        sop_store._cache = None  # force re-read from disk
        loaded = sop_store.load_session(state.id)
        assert loaded is not None
        assert dataclasses.asdict(loaded) == dataclasses.asdict(state)


@given(states=st.lists(_sop_state, min_size=2, max_size=6, unique_by=lambda s: s.id))
@settings(max_examples=50)
def test_sequential_saves_all_retrievable(states: list[SOPState]) -> None:
    """Saving N sessions sequentially means all N are loadable afterwards."""
    with tempfile.TemporaryDirectory() as td:
        _patch_paths(Path(td))
        for s in states:
            sop_store.save_session(s)
        sop_store._cache = None
        all_sessions = sop_store.load_all()
        for s in states:
            assert s.id in all_sessions
            assert dataclasses.asdict(all_sessions[s.id]) == dataclasses.asdict(s)


def test_missing_file_returns_empty_dict() -> None:
    """load_all() must return {} when the store file does not exist."""
    with tempfile.TemporaryDirectory() as td:
        _patch_paths(Path(td))
        # file deliberately not created
        result = sop_store.load_all()
        assert result == {}


@given(good=_sop_state)
@settings(max_examples=50)
def test_partial_state_skips_malformed(good: SOPState) -> None:
    """A file with one valid and one malformed entry loads the valid one only."""
    with tempfile.TemporaryDirectory() as td:
        store_path, _ = _patch_paths(Path(td))
        raw = {
            good.id: dataclasses.asdict(good),
            "bad-session": {"phase": "plan", "unexpected_field_only": True},
        }
        store_path.write_text(json.dumps(raw), encoding="utf-8")
        sop_store._cache = None
        result = sop_store.load_all()
        assert good.id in result
        assert "bad-session" not in result
        assert dataclasses.asdict(result[good.id]) == dataclasses.asdict(good)
