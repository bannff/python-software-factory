"""Tests for the CAN model evaluation wrapper."""

from __future__ import annotations

import numpy as np

from factory.evals.runtime.adapters.can_evaluator import evaluate_can_model


class TestCanEvaluator:
    """Verify evaluate_can_model emits the expected metric bundle."""

    def test_accuracy_with_perfect_predictions(self) -> None:
        """All-correct predictions yield accuracy=1.0 and perfect f1."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
        )
        assert result["accuracy"] == 1.0
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_accuracy_with_half_misclassifications(self) -> None:
        """Half-wrong predictions should yield accuracy=0.5."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 1, 1, 0],
        )
        assert result["accuracy"] == 0.5

    def test_auroc_with_perfect_scores(self) -> None:
        """Perfectly separated scores should yield auroc=1.0 and a finite brier."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
            y_score=[0.1, 0.2, 0.8, 0.9],
        )
        assert result["auroc"] == 1.0
        assert "auprc" in result
        assert "brier" in result
        assert 0.0 <= result["auprc"] <= 1.0
        assert 0.0 <= result["brier"] <= 1.0

    def test_auroc_with_random_scores(self) -> None:
        """Random-score AUROC should hover near 0.5."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1, 0, 1, 0, 1],
            y_pred=[0, 0, 1, 1, 0, 1, 0, 1],
            y_score=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        )
        assert result["auroc"] == 0.5

    def test_score_metrics_omitted_without_y_score(self) -> None:
        """Without y_score, auroc/auprc/brier must not be in the result."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
        )
        assert "auroc" not in result
        assert "auprc" not in result
        assert "brier" not in result

    def test_score_metrics_omitted_with_single_class(self) -> None:
        """When y_true has a single class, auroc/auprc/brier are undefined."""
        result = evaluate_can_model(
            y_true=[1, 1, 1],
            y_pred=[1, 1, 1],
            y_score=[0.5, 0.6, 0.7],
        )
        assert "auroc" not in result
        assert "auprc" not in result
        assert "brier" not in result
        # Accuracy/precision/recall still computed (precision undefined => 0).
        assert "accuracy" in result
        assert result["accuracy"] == 1.0

    def test_accepts_numpy_arrays(self) -> None:
        """numpy inputs should be coerced to arrays internally."""
        result = evaluate_can_model(
            y_true=np.array([0, 1, 0, 1]),
            y_pred=np.array([0, 1, 0, 0]),
            y_score=np.array([0.1, 0.9, 0.2, 0.4]),
        )
        assert result["accuracy"] == 0.75
        assert "auroc" in result
        assert result["auroc"] >= 0.5

    def test_brier_is_lower_for_better_calibrated(self) -> None:
        """Better-calibrated scores should yield a lower Brier score."""
        y_true = [0, 0, 1, 1]
        y_pred = [0, 0, 1, 1]
        well_cal = evaluate_can_model(
            y_true, y_pred, y_score=[0.05, 0.1, 0.9, 0.95],
        )["brier"]
        poorly_cal = evaluate_can_model(
            y_true, y_pred, y_score=[0.4, 0.45, 0.55, 0.6],
        )["brier"]
        assert well_cal < poorly_cal

    def test_full_production_suite_with_scores(self) -> None:
        """All six computational evaluators fire when y_score is given."""
        # y_true has two positive episodes; y_pred catches the first but
        # misses the second — so episode_recall=0.5, lead_time=2 (early
        # detection two samples before the first onset).
        y_true = [0, 0, 0, 1, 1, 0, 0, 1, 0, 0]
        y_pred = [1, 1, 0, 1, 1, 0, 0, 0, 0, 0]
        y_score = [0.9, 0.8, 0.2, 0.7, 0.7, 0.1, 0.2, 0.4, 0.2, 0.1]
        result = evaluate_can_model(y_true, y_pred, y_score)
        for key in (
            "accuracy", "precision", "recall", "f1",
            "auroc", "auprc", "brier",
            "lead_time", "false_alarm", "episode_recall",
        ):
            assert key in result, f"missing metric: {key}"
        # Operational metrics: 3-step lead (earliest pred=1 at index 0
        # before first onset at index 3), 1/2 episodes detected
        # (episode (3,5) caught, episode (7,8) missed).
        assert result["lead_time"] == 3.0
        assert result["episode_recall"] == 0.5
        # 2 false positives (indices 0,1) over 7 true negatives
        # (indices 0,1,2,5,6,8,9 with y_pred=0) → 2/(2+5).
        assert result["false_alarm"] == round(2 / 7, 6)

    def test_operational_metrics_omitted_without_y_score(self) -> None:
        """Without y_score, the operational metrics follow the same gate
        as the score-based ones (both classes + y_score required)."""
        result = evaluate_can_model(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
        )
        for key in (
            "auroc", "auprc", "brier",
            "lead_time", "false_alarm", "episode_recall",
        ):
            assert key not in result, f"{key} should be gated on y_score"

    def test_operational_metrics_omitted_with_single_class(self) -> None:
        """When y_true has a single class, all six gated metrics are absent."""
        result = evaluate_can_model(
            y_true=[1, 1, 1],
            y_pred=[1, 1, 1],
            y_score=[0.9, 0.8, 0.7],
        )
        for key in (
            "auroc", "auprc", "brier",
            "lead_time", "false_alarm", "episode_recall",
        ):
            assert key not in result
