"""C8 Canary — Computational evaluators for CAN failure prediction."""

from __future__ import annotations

import pytest

from factory.evals.runtime.adapters.computational_evaluators import (
    COMPUTATIONAL_EVALUATORS,
    can_auroc,
    can_auprc,
    can_brier,
    can_episode_recall,
    can_false_alarm,
    can_lead_time,
    run_computational,
)


class TestC8ComputationalEvaluators:
    """Verify computational evaluators return valid scores."""

    def test_computational_evaluator_returns_score(self) -> None:
        """C8 core canary: can_auroc returns a score in [0, 1]."""
        result = run_computational(
            "can_auroc",
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
            scores=[0.1, 0.4, 0.35, 0.8],
        )
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_all_evaluators_registered(self) -> None:
        """All 10 evaluators must be in the catalog."""
        expected = {
            "can_auroc",
            "can_auprc",
            "can_brier",
            "can_lead_time",
            "can_false_alarm",
            "can_episode_recall",
            "can_distribution_similarity",
            "can_temporal_coherence",
            "can_statistical_fidelity",
            "can_mode_coverage",
        }
        assert set(COMPUTATIONAL_EVALUATORS.keys()) == expected

    def test_run_computational_unknown_returns_error(self) -> None:
        """Unknown evaluator name should return error dict."""
        result = run_computational(
            "nonexistent",
            y_true=[0, 1],
            y_pred=[0, 1],
            scores=[0.1, 0.9],
        )
        assert "error" in result

    def test_auroc_perfect_separation(self) -> None:
        """Perfect separation should yield AUROC = 1.0."""
        result = can_auroc(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
            scores=[0.1, 0.2, 0.8, 0.9],
        )
        assert result["score"] == 1.0

    def test_auroc_no_separation(self) -> None:
        """Identical scores should yield AUROC = 0.5."""
        result = can_auroc(
            y_true=[0, 1],
            y_pred=[0, 1],
            scores=[0.5, 0.5],
        )
        assert result["score"] == 0.5

    def test_auprc_matches_sklearn_known_answers(self) -> None:
        """AUPRC matches sklearn for ties, all-positive, and mixed scores."""
        from sklearn.metrics import average_precision_score

        cases = [
            ([0, 1, 0, 1], [0.5, 0.5, 0.2, 0.2]),
            ([1, 1, 1], [0.8, 0.9, 0.7]),
            ([0, 1, 0, 1, 1], [0.1, 0.7, 0.4, 0.35, 0.8]),
        ]
        for y_true, scores in cases:
            result = can_auprc(y_true, y_true, scores)
            expected = average_precision_score(y_true, scores)
            assert result == {
                "evaluator": "can_auprc",
                "score": pytest.approx(expected, rel=1e-15, abs=1e-15),
            }

    def test_auprc_no_positives_returns_zero_without_warning(self) -> None:
        """No-positive input avoids sklearn's undefined-metric warning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = can_auprc([0, 0, 0], [0, 0, 0], [0.3, 0.2, 0.1])
        assert result == {"evaluator": "can_auprc", "score": 0.0}
        assert caught == []

    def test_auprc_empty_returns_zero_without_warning(self) -> None:
        """Empty input returns the public zero result without warning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = can_auprc([], [], [])
        assert result == {"evaluator": "can_auprc", "score": 0.0}
        assert caught == []

    @pytest.mark.parametrize("labels", [[0, 2], [-1, 1], [0, 0.5]])
    def test_auprc_rejects_non_binary_labels(self, labels: list) -> None:
        """Only binary labels are accepted by the CAN AUPRC contract."""
        with pytest.raises(ValueError, match=r"binary values in \{0, 1\}"):
            can_auprc(labels, [0, 1], [0.1, 0.9])

    def test_brier_score_range(self) -> None:
        """Brier score must be in [0, 1]."""
        result = can_brier(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
            scores=[0.1, 0.4, 0.35, 0.8],
        )
        assert 0.0 <= result["score"] <= 1.0

    def test_empty_inputs(self) -> None:
        """Empty inputs should return score 0.0 without crashing."""
        result = can_auroc(y_true=[], y_pred=[], scores=[])
        assert result["score"] == 0.0

    def test_all_positive_labels(self) -> None:
        """All-positive labels should yield AUROC = 0.0."""
        result = can_auroc(
            y_true=[1, 1, 1],
            y_pred=[1, 1, 1],
            scores=[0.8, 0.9, 0.7],
        )
        assert result["score"] == 0.0
