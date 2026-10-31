"""Bayesian iterative learning — pure math, stdlib only.

Implements precision estimation, sample-size calculation, and
iteration-efficiency comparison for the Cataphract iterative
learning framework.  Uses Beta-distribution helpers built on
``math.lgamma`` and continued-fraction expansion (no scipy).
"""

from __future__ import annotations

import math


# ── Beta-distribution helpers ────────────────────────────────────

def _beta_cf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    """Continued-fraction expansion for the regularised incomplete beta."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < eps:
        d = eps
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < eps:
            d = eps
        c = 1.0 + aa / c
        if abs(c) < eps:
            c = eps
        d = 1.0 / d
        h *= d * c
        # odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < eps:
            d = eps
        c = 1.0 + aa / c
        if abs(c) < eps:
            c = eps
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _beta_cdf(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta function I_x(a, b) — the Beta CDF."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - ln_beta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_cf(a, b, x) / a
    return 1.0 - front * _beta_cf(b, a, 1.0 - x) / b


def _beta_ppf(p: float, a: float, b: float, tol: float = 1e-9) -> float:
    """Beta quantile (PPF) via bisection over the CDF."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2.0


# ── Public API ───────────────────────────────────────────────────

def precision_estimate(
    reviewed: int,
    true_positives: int,
    prior_a: float = 1.0,
    prior_b: float = 1.0,
    target_precision: float = 0.10,
) -> dict:
    """Bayesian precision estimate using a Beta-Binomial conjugate model.

    Returns posterior mean, 95 % credible interval, and the probability
    that the true precision exceeds *target_precision*.
    """
    post_a = prior_a + true_positives
    post_b = prior_b + reviewed - true_positives
    p_hat = post_a / (post_a + post_b)
    lo = _beta_ppf(0.025, post_a, post_b)
    hi = _beta_ppf(0.975, post_a, post_b)
    pr_above = 1.0 - _beta_cdf(target_precision, post_a, post_b)
    return {
        "p_hat": round(p_hat, 6),
        "credible_interval_95": [round(lo, 6), round(hi, 6)],
        "pr_above_target": round(pr_above, 6),
        "posterior_a": post_a,
        "posterior_b": post_b,
        "reviewed": reviewed,
        "true_positives": true_positives,
    }


def sample_size(
    estimated_precision: float = 0.0196,
    confidence: float = 0.95,
    min_true_positives: int = 1,
) -> dict:
    """Minimum sample size to observe ≥ k true positives at given confidence.

    For k=1 uses the geometric closed form; for k>1 uses binomial CDF
    inversion via the regularised incomplete beta function.
    """
    delta = 1.0 - confidence
    p = estimated_precision

    def _x_for_k(k: int) -> int:
        if k == 1:
            return math.ceil(math.log(delta) / math.log(1.0 - p))
        # Find smallest X where P(X >= k | n=X, p) >= confidence
        # P(X >= k) = 1 - I_p(k, X-k+1)  ... but we iterate over X
        for x in range(k, 100_000):
            # CDF of Binomial(x, p) at k-1 = I_{1-p}(x-k+1, k)
            prob_ge_k = 1.0 - _beta_cdf(1.0 - p, x - k + 1, k)
            if prob_ge_k >= confidence:
                return x
        return 100_000  # pragma: no cover

    recommended = _x_for_k(min_true_positives)
    sizes = {k: _x_for_k(k) for k in (1, 2, 3, 5, 10)}
    return {
        "recommended_x": recommended,
        "confidence": confidence,
        "estimated_precision": estimated_precision,
        "sample_sizes": sizes,
    }


def iteration_efficiency(
    initial_ratio: float = 50.0,
    budget: int = 5000,
    sample_size: int = 200,
    improvement_rate: float = 0.95,
) -> dict:
    """Compare review-all-once vs sample-and-iterate strategies.

    R(B,X) = initial_ratio × improvement_rate^(budget / sample_size).
    """
    def _ratio(x: int) -> float:
        return initial_ratio * (improvement_rate ** (budget / x))

    iters_a = 1
    ratio_a = _ratio(budget)
    prec_a = 1.0 / ratio_a if ratio_a > 0 else 0.0

    iters_b = budget // sample_size
    ratio_b = _ratio(sample_size)
    prec_b = 1.0 / ratio_b if ratio_b > 0 else 0.0

    improvement = prec_b / prec_a if prec_a > 0 else float("inf")
    recommended = "iterate" if prec_b > prec_a else "review_all"

    return {
        "strategy_a": {
            "final_ratio": round(ratio_a, 4),
            "precision": round(prec_a, 6),
            "iterations": iters_a,
        },
        "strategy_b": {
            "final_ratio": round(ratio_b, 4),
            "precision": round(prec_b, 6),
            "iterations": iters_b,
        },
        "improvement_factor": round(improvement, 4),
        "recommended_strategy": recommended,
    }
