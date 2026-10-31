"""Hypothesis property tests for Bayesian iterative learning tools.

Tests pure-function invariants for precision_estimate, sample_size,
and iteration_efficiency from factory.metrics.runtime.bayesian.

Properties verified:
  1. Posterior parameter sum is correct (conjugate update identity).
  2. 95% credible interval contains the posterior mean p_hat.
  3. pr_above_target is monotone-increasing in true_positives.
  4. Higher estimated_precision → smaller sample size (monotonicity).
  5. sample_size for k=1 matches the geometric closed form.
  6. Iterate strategy beats review-all when improvement_rate < 1.
  7. Edge cases: reviewed=0, Jeffreys prior, tiny precision.
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume, strategies as st

from factory.metrics.runtime.bayesian import (
    iteration_efficiency,
    precision_estimate,
    sample_size,
)

# ── Strategies ───────────────────────────────────────────────────

_reviewed = st.integers(min_value=0, max_value=200)
_prior = st.floats(min_value=0.5, max_value=10.0, allow_nan=False)
_precision_est = st.floats(min_value=0.005, max_value=0.5, allow_nan=False)
_confidence = st.floats(min_value=0.80, max_value=0.99, allow_nan=False)
_rate = st.floats(min_value=0.5, max_value=0.999, allow_nan=False)


# ── 1. Posterior parameter sum ───────────────────────────────────


@given(reviewed=_reviewed, prior_a=_prior, prior_b=_prior)
@settings(max_examples=50)
def test_posterior_params_sum(reviewed: int, prior_a: float, prior_b: float):
    """posterior_a + posterior_b == reviewed + prior_a + prior_b."""
    tp = reviewed // 2  # valid: tp <= reviewed
    r = precision_estimate(reviewed, tp, prior_a, prior_b)
    expected_sum = reviewed + prior_a + prior_b
    assert abs((r["posterior_a"] + r["posterior_b"]) - expected_sum) < 1e-9


# ── 2. Credible interval contains p_hat ──────────────────────────


@given(reviewed=st.integers(min_value=2, max_value=200), prior_a=_prior, prior_b=_prior)
@settings(max_examples=50)
def test_credible_interval_contains_mean(reviewed: int, prior_a: float, prior_b: float):
    """The 95% CI must contain the posterior mean."""
    tp = reviewed // 3
    r = precision_estimate(reviewed, tp, prior_a, prior_b)
    lo, hi = r["credible_interval_95"]
    assert lo <= r["p_hat"] <= hi


# ── 3. pr_above_target monotonicity in true_positives ────────────


@given(
    reviewed=st.integers(min_value=10, max_value=100),
    prior_a=_prior,
    prior_b=_prior,
)
@settings(max_examples=50)
def test_pr_above_monotone_in_tp(reviewed: int, prior_a: float, prior_b: float):
    """More true positives → higher pr_above_target (fixed reviewed)."""
    tp_lo = reviewed // 4
    tp_hi = reviewed * 3 // 4
    assume(tp_lo < tp_hi)
    r_lo = precision_estimate(reviewed, tp_lo, prior_a, prior_b, target_precision=0.10)
    r_hi = precision_estimate(reviewed, tp_hi, prior_a, prior_b, target_precision=0.10)
    assert r_hi["pr_above_target"] >= r_lo["pr_above_target"]


# ── 4. Sample size monotonicity in precision ─────────────────────


@given(
    p_lo=st.floats(min_value=0.01, max_value=0.10, allow_nan=False),
    p_hi=st.floats(min_value=0.15, max_value=0.50, allow_nan=False),
    conf=_confidence,
)
@settings(max_examples=50)
def test_sample_size_decreases_with_precision(p_lo: float, p_hi: float, conf: float):
    """Higher precision estimate → smaller required sample size."""
    r_lo = sample_size(estimated_precision=p_lo, confidence=conf, min_true_positives=1)
    r_hi = sample_size(estimated_precision=p_hi, confidence=conf, min_true_positives=1)
    assert r_hi["recommended_x"] <= r_lo["recommended_x"]


# ── 5. k=1 closed form ──────────────────────────────────────────


@given(p=_precision_est, conf=_confidence)
@settings(max_examples=50)
def test_sample_size_k1_closed_form(p: float, conf: float):
    """For k=1, X = ceil(ln(delta) / ln(1-p))."""
    r = sample_size(estimated_precision=p, confidence=conf, min_true_positives=1)
    delta = 1.0 - conf
    expected = math.ceil(math.log(delta) / math.log(1.0 - p))
    assert r["recommended_x"] == expected
    assert r["sample_sizes"][1] == expected


# ── 6. Iterate beats review-all ──────────────────────────────────


@given(
    ratio=st.floats(min_value=2.0, max_value=200.0, allow_nan=False),
    budget=st.integers(min_value=500, max_value=10000),
    ssize=st.integers(min_value=50, max_value=400),
    rate=_rate,
)
@settings(max_examples=50)
def test_iterate_beats_review_all(
    ratio: float, budget: int, ssize: int, rate: float,
):
    """With improvement_rate < 1 and budget > sample_size, iterate wins."""
    assume(budget > ssize)
    r = iteration_efficiency(ratio, budget, ssize, rate)
    assert r["strategy_b"]["final_ratio"] <= r["strategy_a"]["final_ratio"]
    assert r["recommended_strategy"] == "iterate"


# ── 7. Edge cases ────────────────────────────────────────────────


def test_zero_reviewed_returns_prior():
    """reviewed=0, tp=0 → posterior equals prior."""
    r = precision_estimate(0, 0, prior_a=1.0, prior_b=1.0)
    assert r["posterior_a"] == 1.0
    assert r["posterior_b"] == 1.0
    assert abs(r["p_hat"] - 0.5) < 1e-6


def test_jeffreys_prior():
    """Jeffreys prior (0.5, 0.5) with reviewed=0 → p_hat = 0.5."""
    r = precision_estimate(0, 0, prior_a=0.5, prior_b=0.5)
    assert r["posterior_a"] == 0.5
    assert r["posterior_b"] == 0.5
    assert abs(r["p_hat"] - 0.5) < 1e-6


def test_all_true_positives():
    """All reviewed items are TPs → p_hat near 1."""
    r = precision_estimate(100, 100, prior_a=1.0, prior_b=1.0)
    assert r["p_hat"] > 0.95
    assert r["pr_above_target"] > 0.99


def test_no_true_positives():
    """Zero TPs → p_hat near 0."""
    r = precision_estimate(100, 0, prior_a=1.0, prior_b=1.0)
    assert r["p_hat"] < 0.05
    lo, hi = r["credible_interval_95"]
    assert lo < hi


def test_sample_size_tiny_precision():
    """Very small precision requires large sample."""
    r = sample_size(estimated_precision=0.001, confidence=0.95)
    assert r["recommended_x"] >= 2000


def test_iteration_efficiency_rate_one():
    """improvement_rate=1.0 → no improvement, both strategies equal."""
    r = iteration_efficiency(50.0, 5000, 200, improvement_rate=1.0)
    assert abs(r["strategy_a"]["final_ratio"] - r["strategy_b"]["final_ratio"]) < 1e-6
    assert r["recommended_strategy"] == "review_all"
