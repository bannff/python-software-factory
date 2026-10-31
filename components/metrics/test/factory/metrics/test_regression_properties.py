"""
Property tests for the regression gate and baseline manager.

Pure-function properties (compare_to_baseline):
  - Self-comparison symmetry: X vs X → all PASS, zero deltas
  - Signal monotonicity: larger abs(delta) → same or worse signal
  - Threshold ordering: block > warn means BLOCK harder to trigger
  - Empty inputs: empty dicts → empty comparisons

Stateful properties (BaselineManager):
  - Store-then-retrieve roundtrip
  - Overwrite semantics (same metric_id+tag replaces)
  - Compare against stored baseline succeeds
  - Compare against missing baseline returns error
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize

from factory.metrics.runtime.regression import compare_to_baseline
from factory.metrics.runtime.baselines import BaselineManager

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_ids = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_metric_dicts = st.dictionaries(_ids, _values, min_size=0, max_size=5)
_tags = st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N")))

# ---------------------------------------------------------------------------
# Pure-function properties: compare_to_baseline
# ---------------------------------------------------------------------------

SIGNAL_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}


@settings(max_examples=50)
@given(values=_metric_dicts)
def test_self_comparison_is_pass(values):
    """Comparing X to itself must yield all-PASS with zero deltas."""
    result = compare_to_baseline(values, values, baseline_tag="self")
    assert result.overall_signal == "PASS"
    for c in result.comparisons:
        assert c.signal == "PASS"
        assert c.delta == 0.0


@settings(max_examples=50)
@given(data=st.data())
def test_signal_monotonicity(data):
    """A larger absolute delta cannot produce a *better* signal."""
    key = data.draw(_ids)
    base_val = data.draw(st.floats(min_value=0.1, max_value=1e4, allow_nan=False, allow_infinity=False))
    small_shift = data.draw(st.floats(min_value=0.0, max_value=base_val * 0.5, allow_nan=False, allow_infinity=False))
    big_shift = data.draw(st.floats(min_value=small_shift, max_value=base_val * 2, allow_nan=False, allow_infinity=False))

    baseline = {key: base_val}
    r_small = compare_to_baseline({key: base_val + small_shift}, baseline)
    r_big = compare_to_baseline({key: base_val + big_shift}, baseline)

    sig_small = SIGNAL_RANK[r_small.comparisons[0].signal]
    sig_big = SIGNAL_RANK[r_big.comparisons[0].signal]
    assert sig_big >= sig_small


@settings(max_examples=50)
@given(values=_metric_dicts)
def test_empty_baseline_produces_empty_comparisons(values):
    """Empty current AND baseline → no comparisons."""
    result = compare_to_baseline({}, {})
    assert result.overall_signal == "PASS"
    assert len(result.comparisons) == 0


@settings(max_examples=50)
@given(
    key=_ids,
    base=st.floats(min_value=0.1, max_value=1e4, allow_nan=False, allow_infinity=False),
    warn=st.floats(min_value=0.01, max_value=0.49, allow_nan=False, allow_infinity=False),
)
def test_threshold_ordering(key, base, warn):
    """With block = warn * 2, a delta triggering WARN must not trigger BLOCK."""
    block = warn * 2
    shift = base * (warn + 0.001)  # just above warn
    current = {key: base + shift}
    baseline = {key: base}
    result = compare_to_baseline(current, baseline, threshold_block=block, threshold_warn=warn)
    sig = result.comparisons[0].signal
    # delta_pct ≈ warn+ε which is < block, so signal is WARN at worst
    assert sig in ("WARN", "PASS")


# ---------------------------------------------------------------------------
# Stateful tests: BaselineManager
# ---------------------------------------------------------------------------

class BaselineManagerMachine(RuleBasedStateMachine):
    """Verify BaselineManager maintains consistent state."""

    def __init__(self):
        super().__init__()
        self.mgr = BaselineManager()
        self.model: dict[str, dict[str, float]] = {}  # key → values

    @rule(metric_id=_ids, tag=_tags, values=_metric_dicts)
    def set_baseline(self, metric_id, tag, values):
        result = self.mgr.set_baseline(metric_id, tag, values)
        assert result["ok"] is True
        self.model[f"{metric_id}:{tag}"] = values

    @rule(metric_id=_ids, tag=_tags)
    def compare_missing(self, metric_id, tag):
        key = f"{metric_id}:{tag}"
        if key not in self.model:
            result = self.mgr.compare_baseline(metric_id, {}, tag)
            assert result["ok"] is False
            assert "not found" in result["error"].lower()

    @rule(metric_id=_ids, tag=_tags, current=_metric_dicts)
    def compare_existing(self, metric_id, tag, current):
        key = f"{metric_id}:{tag}"
        if key in self.model:
            result = self.mgr.compare_baseline(metric_id, current, tag)
            assert result["ok"] is True
            assert result["overall_signal"] in ("PASS", "WARN", "BLOCK")

    @invariant()
    def list_matches_model(self):
        listed = self.mgr.list_baselines()
        listed_keys = {f"{b['metric_id']}:{b['tag']}" for b in listed}
        assert listed_keys == set(self.model.keys())

    @invariant()
    def stored_values_match(self):
        for key, expected_vals in self.model.items():
            metric_id, tag = key.split(":", 1)
            matches = [
                b for b in self.mgr.list_baselines(metric_id=metric_id)
                if b["tag"] == tag
            ]
            assert len(matches) == 1
            assert matches[0]["values"] == expected_vals


TestBaselineManager = BaselineManagerMachine.TestCase
TestBaselineManager.settings = settings(max_examples=50, stateful_step_count=15)
