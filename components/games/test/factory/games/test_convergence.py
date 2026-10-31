"""Tests for convergence detection — 2-of-3 voting."""

from hypothesis import given, settings, strategies as st

from factory.games.runtime.convergence import (
    ConvergenceConfig,
    ConvergenceState,
)


class TestConvergenceBasic:
    """Basic convergence behavior."""

    def test_below_min_iterations_never_stops(self):
        state = ConvergenceState(config=ConvergenceConfig(min_iterations=3))
        state.record(0.5)
        state.record(0.5)
        stop, details = state.should_stop()
        assert stop is False
        assert details["reason"] == "below min_iterations"

    def test_max_iterations_always_stops(self):
        state = ConvergenceState(config=ConvergenceConfig(max_iterations=3))
        for _ in range(3):
            state.record(0.5)
        stop, details = state.should_stop()
        assert stop is True
        assert details["reason"] == "max_iterations"

    def test_improving_scores_continue(self):
        state = ConvergenceState(
            config=ConvergenceConfig(patience=3, epsilon=0.01),
        )
        for i in range(5):
            state.record(0.1 * (i + 1))
        stop, _ = state.should_stop()
        assert stop is False

    def test_flat_scores_stop(self):
        """Same score repeated = plateau + patience both trigger."""
        state = ConvergenceState(
            config=ConvergenceConfig(patience=3, epsilon=0.01),
        )
        for _ in range(5):
            state.record(0.5)
        stop, details = state.should_stop()
        assert stop is True
        assert details["votes"]["patience"] is True
        assert details["votes"]["plateau"] is True

    def test_regression_plus_patience_stops(self):
        """Score drops significantly + no improvement = stop."""
        cfg = ConvergenceConfig(patience=2, epsilon=0.01)
        state = ConvergenceState(config=cfg)
        state.record(0.9)
        state.record(0.95)
        state.record(0.5)  # regression
        state.record(0.4)  # still regressing + patience exhausted
        stop, details = state.should_stop()
        assert stop is True
        assert details["stop_votes"] >= 2


class TestConvergenceVoting:
    """2-of-3 voting logic."""

    def test_single_vote_not_enough(self):
        """Only patience triggers, plateau and regression don't = continue."""
        cfg = ConvergenceConfig(patience=2, epsilon=0.001)
        state = ConvergenceState(config=cfg)
        state.record(0.5)
        state.record(0.52)  # small improvement
        state.record(0.53)  # small improvement (delta > epsilon)
        state.record(0.53)  # no improvement (patience=1)
        state.record(0.53)  # no improvement (patience=2) but plateau also triggers
        stop, details = state.should_stop()
        # patience=True (2 no-improve), plateau=True (delta=0)
        assert stop is True

    def test_best_score_tracking(self):
        state = ConvergenceState()
        state.record(0.3)
        state.record(0.7)
        state.record(0.5)
        assert state.best_score == 0.7
        assert state.best_iteration == 1

    def test_to_dict_serialization(self):
        state = ConvergenceState()
        state.record(0.5)
        state.record(0.8)
        d = state.to_dict()
        assert d["scores"] == [0.5, 0.8]
        assert d["best_score"] == 0.8
        assert d["iteration_count"] == 2


class TestConvergenceProperty:
    """Property-based tests."""

    @given(scores=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1, max_size=50,
    ))
    @settings(max_examples=100)
    def test_always_stops_at_max_iterations(self, scores):
        """Must stop at or before max_iterations."""
        cfg = ConvergenceConfig(max_iterations=len(scores))
        state = ConvergenceState(config=cfg)
        for s in scores:
            state.record(s)
        stop, _ = state.should_stop()
        assert stop is True

    @given(scores=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1, max_size=50,
    ))
    @settings(max_examples=100)
    def test_best_score_is_max(self, scores):
        """best_score always equals the maximum recorded score."""
        state = ConvergenceState()
        for s in scores:
            state.record(s)
        assert abs(state.best_score - max(scores)) < 1e-9

    @given(n=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_monotonic_increase_never_triggers_patience(self, n):
        """Strictly increasing scores never trigger patience."""
        state = ConvergenceState(
            config=ConvergenceConfig(patience=10, max_iterations=100),
        )
        for i in range(n):
            state.record(float(i + 1) / 10)
        assert state.no_improve_count == 0
