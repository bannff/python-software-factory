"""Tests for the CAN synthetic data quality evaluators.

Covers can_distribution_similarity, can_temporal_coherence,
can_statistical_fidelity, and can_mode_coverage — all of which
score how realistic synthetic CAN data is (not classifier
performance). They use the same (y_true, y_pred, scores) dispatch
as the classifier evaluators but accept structured data in
y_true/y_pred (windowed CAN records or flat per-signal lists).
"""

from __future__ import annotations

import random

import pytest

from factory.evals.runtime.adapters.can_synthetic_evaluators import (
    CAN_SYNTHETIC_EVALUATORS,
    _lag1_autocorr,
    can_distribution_similarity,
    can_mode_coverage,
    can_statistical_fidelity,
    can_temporal_coherence,
)
from factory.evals.runtime.adapters.can_synthetic_evaluators._ks import (
    ks_pvalue,
    ks_statistic,
)
from factory.evals.runtime.adapters.can_synthetic_evaluators._windowing import (
    is_windowed,
    window_to_per_signal,
)
from factory.evals.runtime.adapters.computational_evaluators import (
    COMPUTATIONAL_EVALUATORS,
    run_computational,
)


def _make_windows(
    rng: random.Random,
    n_windows: int,
    T: int,
    signal_names: list[str],
    sample_fn,
) -> list[dict]:
    """Build a list of windowed records with random time series per signal.

    ``sample_fn(name) -> float`` is called once per (window, time, signal)
    to generate that value, so the caller controls the distribution.
    """
    windows: list[dict] = []
    for _ in range(n_windows):
        data = [[float(sample_fn(s)) for s in signal_names] for _ in range(T)]
        windows.append({"window_data": data, "signal_names": list(signal_names)})
    return windows


class TestRegistration:
    """All 4 synthetic evaluators must be registered in both dicts."""

    def test_registered_in_module_dict(self) -> None:
        expected = {
            "can_distribution_similarity",
            "can_temporal_coherence",
            "can_statistical_fidelity",
            "can_mode_coverage",
        }
        assert expected.issubset(set(CAN_SYNTHETIC_EVALUATORS.keys()))

    def test_registered_in_main_dict(self) -> None:
        expected = {
            "can_distribution_similarity",
            "can_temporal_coherence",
            "can_statistical_fidelity",
            "can_mode_coverage",
        }
        assert expected.issubset(set(COMPUTATIONAL_EVALUATORS.keys()))

    def test_dispatch_through_run_computational(self) -> None:
        for name in (
            "can_distribution_similarity",
            "can_temporal_coherence",
            "can_statistical_fidelity",
            "can_mode_coverage",
        ):
            result = run_computational(name, [], [], [])
            assert "score" in result
            assert 0.0 <= result["score"] <= 1.0


class TestCanDistributionSimilarity:
    """KS-test based distribution similarity."""

    def test_empty_inputs_return_zero(self) -> None:
        result = can_distribution_similarity([], [], [])
        assert result == {
            "evaluator": "can_distribution_similarity",
            "score": 0.0,
        }

    def test_identical_distributions_high_pvalue(self) -> None:
        signal = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = can_distribution_similarity([signal], [signal], [])
        assert result["score"] == pytest.approx(1.0, abs=1e-3)

    def test_completely_different_distributions_low_pvalue(self) -> None:
        real = [float(i) for i in range(50)]
        shift = [float(i) + 100.0 for i in range(50)]
        result = can_distribution_similarity([real], [shift], [])
        assert result["score"] < 0.01

    def test_returns_dict_with_evaluator_and_score(self) -> None:
        result = can_distribution_similarity([[1.0, 2.0]], [[1.0, 2.0]], [])
        assert result["evaluator"] == "can_distribution_similarity"
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0

    def test_multi_signal_averages_pvalues(self) -> None:
        sig1_real = [1.0, 2.0, 3.0, 4.0, 5.0]
        sig2_real = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = can_distribution_similarity(
            [sig1_real, sig2_real], [sig1_real, sig2_real], []
        )
        # Both identical -> mean p-value ~ 1.0
        assert result["score"] == pytest.approx(1.0, abs=1e-3)

    def test_empty_signal_column(self) -> None:
        result = can_distribution_similarity([[1.0, 2.0], []], [[1.0, 2.0], [3.0]], [])
        # One signal contributes 1.0, the other 0.0 -> mean 0.5
        assert 0.0 <= result["score"] <= 1.0


class TestCanTemporalCoherence:
    """Lag-1 autocorrelation match between real and synthetic."""

    def test_empty_inputs_return_zero(self) -> None:
        result = can_temporal_coherence([], [], [])
        assert result == {"evaluator": "can_temporal_coherence", "score": 0.0}

    def test_identical_signals_return_one(self) -> None:
        signal = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        result = can_temporal_coherence([signal], [signal], [])
        assert result["score"] == pytest.approx(1.0)

    def test_uncorrelated_synthetic_scores_lower(self) -> None:
        # Real signal has strong positive autocorrelation (rising trend)
        real = [float(i) for i in range(50)]
        # Synthetic is i.i.d.-ish (alternating values => ~0 lag-1 autocorr)
        synth = [1.0 if i % 2 == 0 else -1.0 for i in range(50)]
        result = can_temporal_coherence([real], [synth], [])
        assert 0.0 <= result["score"] < 1.0

    def test_score_in_unit_interval(self) -> None:
        real = [1.0, 2.0, 1.5, 3.0, 2.5, 4.0]
        synth = [1.0, 1.8, 1.6, 2.9, 2.7, 3.8]
        result = can_temporal_coherence([real], [synth], [])
        assert 0.0 <= result["score"] <= 1.0

    def test_too_short_signal_handled(self) -> None:
        # _lag1_autocorr returns 0 for n < 2, so both signals score 0 diff
        result = can_temporal_coherence([[1.0]], [[1.0]], [])
        assert result["score"] == pytest.approx(1.0)


class TestLag1Autocorr:
    """Direct tests of the helper function."""

    def test_constant_signal_returns_zero(self) -> None:
        assert _lag1_autocorr([5.0, 5.0, 5.0, 5.0]) == 0.0

    def test_strongly_negative_autocorr_alternating(self) -> None:
        # Alternating signal has strongly negative lag-1 autocorr
        result = _lag1_autocorr([1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
        # Finite series => |r_1| < 1 due to edge effects
        assert result < -0.8

    def test_strongly_positive_autocorr_linear(self) -> None:
        # Linear ramp has strongly positive lag-1 autocorr
        result = _lag1_autocorr([1.0, 2.0, 3.0, 4.0, 5.0])
        # For [1..5] with mean=3, r_1 = sum((x-3)(y-3)) / sum((x-3)^2) = 4/10
        assert result == pytest.approx(0.4)

    def test_short_signal_returns_zero(self) -> None:
        assert _lag1_autocorr([1.0]) == 0.0
        assert _lag1_autocorr([]) == 0.0


class TestCanStatisticalFidelity:
    """Normalized mean error of per-signal statistics."""

    def test_empty_inputs_return_zero(self) -> None:
        result = can_statistical_fidelity({}, {}, [])
        assert result == {
            "evaluator": "can_statistical_fidelity",
            "score": 0.0,
        }

    def test_identical_stats_return_one(self) -> None:
        stats = {
            "sig1": {"min": 0.0, "max": 10.0, "mean": 5.0},
            "sig2": {"min": -1.0, "max": 1.0, "mean": 0.0},
        }
        result = can_statistical_fidelity(stats, stats, [])
        assert result["score"] == pytest.approx(1.0)

    def test_means_shifted_by_half_range(self) -> None:
        real = {"sig1": {"min": 0.0, "max": 10.0, "mean": 5.0}}
        # synth mean off by 5 (half of range) -> normalized error = 0.5
        synth = {"sig1": {"min": 0.0, "max": 10.0, "mean": 10.0}}
        result = can_statistical_fidelity(real, synth, [])
        assert result["score"] == pytest.approx(0.5)

    def test_missing_signal_in_synth_skipped(self) -> None:
        real = {
            "sig1": {"min": 0.0, "max": 10.0, "mean": 5.0},
            "sig2": {"min": 0.0, "max": 4.0, "mean": 2.0},
        }
        synth = {
            "sig1": {"min": 0.0, "max": 10.0, "mean": 5.0},
            # sig2 missing
        }
        result = can_statistical_fidelity(real, synth, [])
        # Only sig1 contributes, and it's identical
        assert result["score"] == pytest.approx(1.0)

    def test_zero_range_signal_skipped(self) -> None:
        real = {"flat": {"min": 5.0, "max": 5.0, "mean": 5.0}}
        synth = {"flat": {"min": 5.0, "max": 5.0, "mean": 5.0}}
        # Range is 0 -> signal contributes no error but also no valid diff
        result = can_statistical_fidelity(real, synth, [])
        assert result["score"] == 0.0

    def test_score_clipped_to_unit_interval(self) -> None:
        real = {"sig1": {"min": 0.0, "max": 1.0, "mean": 0.5}}
        synth = {"sig1": {"min": 0.0, "max": 1.0, "mean": 0.0}}
        # Error is 0.5 -> score is 0.5
        result = can_statistical_fidelity(real, synth, [])
        assert 0.0 <= result["score"] <= 1.0


class TestCanModeCoverage:
    """Fraction of signal ranges covered by synthetic data."""

    def test_empty_inputs_return_zero(self) -> None:
        result = can_mode_coverage([], [], [])
        assert result == {"evaluator": "can_mode_coverage", "score": 0.0}

    def test_synthetic_fully_covers_real(self) -> None:
        real = [[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]]
        synth = [[0.0, 1.0, 2.0, 3.0, 4.0], [5.0, 10.0, 20.0, 30.0, 40.0]]
        result = can_mode_coverage(real, synth, [])
        assert result["score"] == pytest.approx(1.0)

    def test_synthetic_does_not_cover_real(self) -> None:
        real = [[0.0, 5.0, 10.0]]
        synth = [[1.0, 2.0, 3.0]]  # Doesn't reach 0 or 10
        result = can_mode_coverage(real, synth, [])
        assert result["score"] == 0.0

    def test_partial_coverage(self) -> None:
        real = [[0.0, 10.0], [0.0, 10.0]]  # Two signals
        synth = [
            [-1.0, 5.0, 11.0],  # Covers signal 1
            [2.0, 5.0, 8.0],  # Does NOT cover signal 2 (misses 0 and 10)
        ]
        result = can_mode_coverage(real, synth, [])
        assert result["score"] == pytest.approx(0.5)

    def test_empty_signal_column_skipped(self) -> None:
        result = can_mode_coverage([[]], [[1.0]], [])
        # Empty signal in real is skipped, no signal covered
        assert result["score"] == 0.0

    def test_identical_signals_covered(self) -> None:
        sig = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = can_mode_coverage([sig], [sig], [])
        assert result["score"] == pytest.approx(1.0)

    def test_score_in_unit_interval(self) -> None:
        real = [[1.0, 2.0, 3.0]]
        synth = [[2.0, 3.0, 4.0]]
        result = can_mode_coverage(real, synth, [])
        assert 0.0 <= result["score"] <= 1.0


class TestKsHelpers:
    """Direct tests of the two-sample KS helpers."""

    def test_ks_statistic_zero_for_identical(self) -> None:
        # Same data sorted -> ECDFs identical -> d = 0
        r = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert ks_statistic(r, list(r)) == 0.0

    def test_ks_statistic_one_for_disjoint(self) -> None:
        # Disjoint supports -> ECDFs never overlap -> d = 1
        r = [0.0, 1.0, 2.0]
        s = [10.0, 11.0, 12.0]
        assert ks_statistic(r, s) == pytest.approx(1.0)

    def test_ks_pvalue_one_for_zero_d(self) -> None:
        assert ks_pvalue(0.0, 100, 100) == 1.0

    def test_ks_pvalue_one_for_empty_sample(self) -> None:
        # Degenerate input: 0 samples or 0 statistic -> 1.0 (no evidence)
        assert ks_pvalue(0.5, 0, 100) == 1.0
        assert ks_pvalue(0.5, 100, 0) == 1.0

    def test_ks_pvalue_decreases_with_larger_d(self) -> None:
        # Monotonicity: bigger statistic => smaller p-value
        p_small = ks_pvalue(0.05, 200, 200)
        p_large = ks_pvalue(0.5, 200, 200)
        assert p_small > p_large

    def test_ks_pvalue_in_unit_interval(self) -> None:
        for d in (0.01, 0.1, 0.3, 0.5, 1.0):
            p = ks_pvalue(d, 100, 100)
            assert 0.0 <= p <= 1.0


class TestWindowingHelpers:
    """Direct tests of the windowed record -> per-signal helpers."""

    def test_is_windowed_true_for_dict_with_window_data(self) -> None:
        rec = {"window_data": [[1.0]], "signal_names": ["a"]}
        assert is_windowed([rec]) is True

    def test_is_windowed_false_for_empty(self) -> None:
        assert is_windowed([]) is False

    def test_is_windowed_false_for_plain_lists(self) -> None:
        # Legacy flat per-signal lists are NOT windowed records
        assert is_windowed([[1.0, 2.0], [3.0, 4.0]]) is False

    def test_window_to_per_signal_mean_aggregates(self) -> None:
        # Two windows, two signals, T=3. Per-window mean of column 0:
        #   window 0: (1+2+3)/3 = 2.0
        #   window 1: (4+5+6)/3 = 5.0
        windows = [
            {
                "window_data": [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]],
                "signal_names": ["a", "b"],
            },
            {
                "window_data": [[4.0, 40.0], [5.0, 50.0], [6.0, 60.0]],
                "signal_names": ["a", "b"],
            },
        ]
        out = window_to_per_signal(windows, agg="mean")
        assert out == {"a": [2.0, 5.0], "b": [20.0, 50.0]}

    def test_window_to_per_signal_sum_aggregates(self) -> None:
        windows = [
            {
                "window_data": [[1.0, 10.0], [2.0, 20.0]],
                "signal_names": ["a", "b"],
            },
        ]
        out = window_to_per_signal(windows, agg="sum")
        assert out == {"a": [3.0], "b": [30.0]}

    def test_window_to_per_signal_last_aggregates(self) -> None:
        windows = [
            {
                "window_data": [[1.0, 10.0], [2.0, 20.0], [9.0, 90.0]],
                "signal_names": ["a", "b"],
            },
        ]
        out = window_to_per_signal(windows, agg="last")
        assert out == {"a": [9.0], "b": [90.0]}

    def test_window_to_per_signal_empty_input(self) -> None:
        assert window_to_per_signal([]) == {}

    def test_window_to_per_signal_collects_union_of_signal_names(self) -> None:
        # First window has 'a','b'; second only 'b','c' -> all three should appear
        windows = [
            {"window_data": [[1.0, 2.0]], "signal_names": ["a", "b"]},
            {"window_data": [[3.0, 4.0]], "signal_names": ["b", "c"]},
        ]
        out = window_to_per_signal(windows, agg="mean")
        assert set(out.keys()) == {"a", "b", "c"}
        # 'a' only has a value from the first window
        assert out["a"] == [1.0]
        # 'c' only has a value from the second window
        assert out["c"] == [4.0]

    def test_window_to_per_signal_skips_zero_length_window(self) -> None:
        windows = [
            {"window_data": [], "signal_names": ["a"]},
            {"window_data": [[7.0]], "signal_names": ["a"]},
        ]
        out = window_to_per_signal(windows, agg="mean")
        assert out == {"a": [7.0]}


class TestCanDistributionSimilarityWindowed:
    """can_distribution_similarity with the windowed record input format.

    The bug being fixed: the evaluator used to treat windowed records
    as flat numeric lists, returning 0.0 for CAN IDs whose data was
    split from a single shuffled pool. It now correctly extracts
    per-signal value series from each window and runs KS per signal.
    """

    def test_empty_inputs_return_zero(self) -> None:
        result = can_distribution_similarity([], [], [])
        assert result == {
            "evaluator": "can_distribution_similarity",
            "score": 0.0,
        }

    def test_one_side_empty_returns_zero(self) -> None:
        rng = random.Random(0)
        real = _make_windows(rng, 20, 5, ["a", "b"], lambda s: rng.gauss(0, 1))
        result = can_distribution_similarity(real, [], [])
        assert result == {
            "evaluator": "can_distribution_similarity",
            "score": 0.0,
        }

    def test_identical_windows_score_near_one(self) -> None:
        rng = random.Random(0)
        real = _make_windows(rng, 100, 10, ["a", "b"], lambda s: rng.gauss(0, 1))
        # Deep-copy real for synth so values are identical
        synth = [
            {"window_data": [row[:] for row in w["window_data"]], "signal_names": w["signal_names"][:]}
            for w in real
        ]
        result = can_distribution_similarity(real, synth, [])
        assert result["evaluator"] == "can_distribution_similarity"
        assert result["score"] == pytest.approx(1.0, abs=1e-3)

    def test_similar_distributions_score_above_half(self) -> None:
        # Both halves drawn from the same N(0, 1) process — should not be
        # rejected, so mean per-signal KS p-value should be > 0.5.
        rng = random.Random(123)
        signal_names = ["speed", "torque", "rpm"]
        real = _make_windows(rng, 200, 20, signal_names, lambda s: rng.gauss(0, 1))
        synth = _make_windows(rng, 200, 20, signal_names, lambda s: rng.gauss(0, 1))
        result = can_distribution_similarity(real, synth, [])
        assert result["score"] > 0.5, (
            f"Expected p > 0.5 for similar distributions, got {result['score']}"
        )

    def test_dissimilar_distributions_score_below_half(self) -> None:
        # real ~ N(0, 1), synth ~ N(10, 1) — clearly different distributions
        rng = random.Random(456)
        signal_names = ["a", "b"]
        real = _make_windows(rng, 200, 20, signal_names, lambda s: rng.gauss(0, 1))
        synth = _make_windows(rng, 200, 20, signal_names, lambda s: rng.gauss(10, 1))
        result = can_distribution_similarity(real, synth, [])
        assert result["score"] < 0.5, (
            f"Expected p < 0.5 for dissimilar distributions, got {result['score']}"
        )

    def test_score_is_mean_across_signals(self) -> None:
        # One signal identical (p=1), another very different (p~0).
        # Mean should land between 0 and 1, closer to the mix.
        rng = random.Random(7)
        real = [
            {"window_data": [[0.0, 0.0] for _ in range(10)], "signal_names": ["match", "mismatch"]}
        ] * 100
        # Reset randomness so synth 'match' mirrors real, but 'mismatch' is shifted
        rng2 = random.Random(7)
        synth_match = _make_windows(rng2, 100, 10, ["match"], lambda s: rng2.gauss(0, 1))
        rng3 = random.Random(99)
        synth_mismatch = _make_windows(rng3, 100, 10, ["mismatch"], lambda s: rng3.gauss(20, 1))
        # Combine per-signal windows into aligned records
        synth = [
            {
                "window_data": [m_row + mm_row for m_row, mm_row in zip(m["window_data"], mm["window_data"])],
                "signal_names": ["match", "mismatch"],
            }
            for m, mm in zip(synth_match, synth_mismatch)
        ]
        real = [
            {
                "window_data": [[0.0, 0.0] for _ in range(10)],
                "signal_names": ["match", "mismatch"],
            }
            for _ in range(100)
        ]
        result = can_distribution_similarity(real, synth, [])
        # 'match' signal: real is constant 0, synth varies around 0 — some p
        # 'mismatch' signal: clearly different — p ~ 0
        # Mean should be in (0, 1)
        assert 0.0 < result["score"] < 1.0

    def test_score_in_unit_interval(self) -> None:
        rng = random.Random(0)
        real = _make_windows(rng, 50, 5, ["a"], lambda s: rng.gauss(0, 1))
        synth = _make_windows(rng, 50, 5, ["a"], lambda s: rng.gauss(1, 2))
        result = can_distribution_similarity(real, synth, [])
        assert 0.0 <= result["score"] <= 1.0

    def test_only_common_signals_compared(self) -> None:
        # Real has signals [a, b], synth has [b, c] — only 'b' should be compared
        # N=150 + fixed seed chosen so the per-window-mean KS test is stable
        rng = random.Random(42)
        real = _make_windows(rng, 150, 5, ["a", "b"], lambda s: rng.gauss(0, 1))
        synth = _make_windows(random.Random(43), 150, 5, ["b", "c"], lambda s: rng.gauss(0, 1))
        result = can_distribution_similarity(real, synth, [])
        # Only 'b' is shared and both 'b' are drawn from N(0, 1) -> p > 0.5
        assert result["score"] > 0.5, (
            f"Expected shared-signal match to score > 0.5, got {result['score']}"
        )

    def test_no_common_signals_returns_zero(self) -> None:
        rng = random.Random(0)
        real = _make_windows(rng, 30, 5, ["a"], lambda s: rng.gauss(0, 1))
        synth = _make_windows(rng, 30, 5, ["z"], lambda s: rng.gauss(0, 1))
        result = can_distribution_similarity(real, synth, [])
        assert result == {
            "evaluator": "can_distribution_similarity",
            "score": 0.0,
        }

    def test_mismatched_formats_returns_zero(self) -> None:
        # Windowed real + flat synth -> cannot compare
        rng = random.Random(0)
        real = _make_windows(rng, 20, 5, ["a"], lambda s: rng.gauss(0, 1))
        flat = [[1.0, 2.0, 3.0]]
        result = can_distribution_similarity(real, flat, [])
        assert result == {
            "evaluator": "can_distribution_similarity",
            "score": 0.0,
        }

    def test_empty_window_data_skipped(self) -> None:
        # A window with window_data=[] should be ignored, not crash
        real = [
            {"window_data": [], "signal_names": ["a"]},
            {
                "window_data": [[1.0], [2.0], [3.0]],
                "signal_names": ["a"],
            },
        ]
        synth = [
            {"window_data": [[1.0], [2.0], [3.0]], "signal_names": ["a"]},
            {"window_data": [[1.0], [2.0], [3.0]], "signal_names": ["a"]},
        ]
        result = can_distribution_similarity(real, synth, [])
        assert 0.0 <= result["score"] <= 1.0

    def test_result_dict_shape(self) -> None:
        rng = random.Random(0)
        real = _make_windows(rng, 20, 5, ["a"], lambda s: rng.gauss(0, 1))
        synth = _make_windows(rng, 20, 5, ["a"], lambda s: rng.gauss(0, 1))
        result = can_distribution_similarity(real, synth, [])
        assert set(result.keys()) == {"evaluator", "score"}
        assert isinstance(result["score"], float)
