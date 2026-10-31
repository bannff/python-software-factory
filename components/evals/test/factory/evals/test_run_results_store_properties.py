"""Property-based tests for run_results_store.py (file-backed eval run persistence).

Properties verified:
1. save_run + list_runs round-trip: a saved run appears in the list with correct
   run_id, verdict, and pass_rate.
2. save_run + get_run round-trip: full data is retrievable by run_id.
3. Missing directory: list_runs() returns [] when .object_store/eval_runs/ doesn't exist.
4. Multiple runs: N saved runs all appear in list_runs(), newest first.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from hypothesis import given, settings, strategies as st

from factory.evals.runtime.adapters import run_results_store

# ── strategies ────────────────────────────────────────────────────────────────

_names = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))
_short_text = st.text(min_size=0, max_size=80)
_evaluators = st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=4)
_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_case_result = st.fixed_dictionaries({
    "case_name": st.text(min_size=1, max_size=20),
    "passed": st.booleans(),
    "score": _score,
    "reason": _short_text,
})

_case_list = st.lists(_case_result, min_size=1, max_size=6)
_summary = st.dictionaries(st.text(min_size=1, max_size=10), _short_text, max_size=3)


# ── helpers ───────────────────────────────────────────────────────────────────

def _patch_dir(tmp: Path) -> Path:
    """Point run_results_store._RUNS_DIR at a temp subdirectory."""
    runs_dir = tmp / "eval_runs"
    run_results_store._RUNS_DIR = runs_dir
    return runs_dir


# ── tests ─────────────────────────────────────────────────────────────────────

@given(
    experiment_name=_names,
    case_results=_case_list,
    summary=_summary,
    evaluators=_evaluators,
    model_id=_short_text,
    system_prompt=_short_text,
)
@settings(max_examples=50)
def test_save_then_list_round_trip(
    experiment_name, case_results, summary, evaluators, model_id, system_prompt
) -> None:
    """A saved run must appear in list_runs() with correct run_id, verdict, pass_rate."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        run_id = run_results_store.save_run(
            experiment_name=experiment_name,
            case_results=case_results,
            summary=summary,
            evaluators_used=evaluators,
            model_id=model_id,
            system_prompt=system_prompt,
        )
        runs = run_results_store.list_runs()
        ids = [r["run_id"] for r in runs]
        assert run_id in ids

        entry = next(r for r in runs if r["run_id"] == run_id)
        passes = sum(1 for r in case_results if r.get("passed"))
        expected_verdict = "PASS" if passes == len(case_results) else "FAIL"
        expected_pass_rate = round(passes / len(case_results), 3)

        assert entry["verdict"] == expected_verdict
        assert entry["pass_rate"] == expected_pass_rate


@given(
    experiment_name=_names,
    case_results=_case_list,
    summary=_summary,
    evaluators=_evaluators,
    model_id=_short_text,
    system_prompt=_short_text,
)
@settings(max_examples=50)
def test_save_then_get_round_trip(
    experiment_name, case_results, summary, evaluators, model_id, system_prompt
) -> None:
    """get_run(run_id) must return the full record that was saved."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        run_id = run_results_store.save_run(
            experiment_name=experiment_name,
            case_results=case_results,
            summary=summary,
            evaluators_used=evaluators,
            model_id=model_id,
            system_prompt=system_prompt,
        )
        record = run_results_store.get_run(run_id)
        assert record is not None
        assert record["run_id"] == run_id
        assert record["experiment_name"] == experiment_name
        assert record["evaluators_used"] == evaluators
        assert record["summary"]["total_cases"] == len(case_results)


def test_missing_directory_returns_empty_list() -> None:
    """list_runs() must return [] when the runs directory does not exist."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        # directory deliberately not created
        result = run_results_store.list_runs()
        assert result == []


def test_get_run_missing_returns_none() -> None:
    """get_run() must return None for a run_id that was never saved."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        assert run_results_store.get_run("nonexistent000") is None


def test_list_runs_computes_regression_fields() -> None:
    """Latest run should include trend and regression metadata per experiment."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        run_results_store.save_run(
            experiment_name="exp-a",
            case_results=[{"case_name": "c1", "passed": True, "score": 1.0, "reason": "ok"}],
            summary={},
            evaluators_used=["judge"],
            model_id="m1",
            system_prompt="prompt",
        )
        time.sleep(0.01)
        run_results_store.save_run(
            experiment_name="exp-a",
            case_results=[{"case_name": "c1", "passed": False, "score": 0.0, "reason": "bad"}],
            summary={},
            evaluators_used=["judge"],
            model_id="m1",
            system_prompt="prompt",
        )

        latest = run_results_store.list_runs()[0]
        assert latest["regression_state"] == "regressed"
        assert latest["trend_direction"] == "down"
        assert latest["previous_run_id"] is not None
        assert latest["failed_cases"] == 1


@given(
    runs=st.lists(
        st.fixed_dictionaries({
            "experiment_name": _names,
            "case_results": _case_list,
            "summary": _summary,
            "evaluators": _evaluators,
            "model_id": _short_text,
            "system_prompt": _short_text,
        }),
        min_size=2,
        max_size=5,
    )
)
@settings(max_examples=30)
def test_multiple_runs_all_appear_in_list(runs) -> None:
    """N saved runs must all appear in list_runs(), newest first by mtime."""
    with tempfile.TemporaryDirectory() as td:
        _patch_dir(Path(td))
        saved_ids = []
        for r in runs:
            run_id = run_results_store.save_run(
                experiment_name=r["experiment_name"],
                case_results=r["case_results"],
                summary=r["summary"],
                evaluators_used=r["evaluators"],
                model_id=r["model_id"],
                system_prompt=r["system_prompt"],
            )
            saved_ids.append(run_id)
            # small sleep so mtime ordering is deterministic
            time.sleep(0.01)

        listed = run_results_store.list_runs()
        listed_ids = [e["run_id"] for e in listed]

        assert len(listed) == len(runs)
        for sid in saved_ids:
            assert sid in listed_ids

        # newest first: last saved id should be first in the list
        assert listed_ids[0] == saved_ids[-1]
