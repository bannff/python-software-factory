"""Tests for CAN evaluators — can_evaluator wrapper + computational evaluators.

Covers: perfect match, divergent, empty inputs, single-sample edge cases.
"""

from __future__ import annotations

import numpy as np
import pytest

from factory.evals.runtime.adapters.can_evaluator import evaluate_can_model
from factory.evals.runtime.adapters.computational_evaluators import (
    COMPUTATIONAL_EVALUATORS,
    _coerce,
    can_auprc,
    can_auroc,
    can_brier,
    can_episode_recall,
    can_false_alarm,
    can_lead_time,
    run_computational,
)


class TestCanEvaluator:

    def test_perfect_match_yields_high_f1(self) -> None:
        y = [0, 0, 1, 1, 0, 1]
        r = evaluate_can_model(y_true=y, y_pred=y)
        assert r["accuracy"] == 1.0
        assert r["f1"] == 1.0

    def test_completely_different_yields_low_scores(self) -> None:
        r = evaluate_can_model(y_true=[0, 0, 0, 0, 1, 1, 1, 1],
                               y_pred=[1, 1, 1, 1, 0, 0, 0, 0])
        assert r["accuracy"] == 0.0
        assert r["f1"] == 0.0

    def test_empty_inputs_returns_defaults(self) -> None:
        expected = {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        assert evaluate_can_model(y_true=[], y_pred=[]) == expected
        assert evaluate_can_model(y_true=[], y_pred=[], y_score=[]) == expected

    @pytest.mark.parametrize(
        ("y_true", "y_pred", "y_score"),
        [([0, 1], [0], None), ([0, 1], [0, 1], [0.5])],
    )
    def test_mismatched_lengths_raise_stable_error(self, y_true, y_pred, y_score) -> None:
        with pytest.raises(ValueError, match="equal length"):
            evaluate_can_model(y_true=y_true, y_pred=y_pred, y_score=y_score)

    def test_single_sample_no_crash(self) -> None:
        r = evaluate_can_model(y_true=[1], y_pred=[1])
        assert r["accuracy"] == 1.0

    def test_single_sample_wrong(self) -> None:
        r = evaluate_can_model(y_true=[0], y_pred=[1])
        assert r["accuracy"] == 0.0


# --- _coerce validation ---------------------------------------------------


class TestCoerce:

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            _coerce([0, 1], [0], [0.5, 0.6])


# --- can_auroc ------------------------------------------------------------


class TestAuroc:

    def test_perfect_separation(self) -> None:
        r = can_auroc([0, 0, 1, 1], [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
        assert r["score"] == 1.0

    def test_inverted_scores(self) -> None:
        r = can_auroc([0, 0, 1, 1], [1, 1, 0, 0], [0.9, 0.8, 0.1, 0.2])
        assert r["score"] == 0.0

    def test_empty(self) -> None:
        assert can_auroc([], [], [])["score"] == 0.0

    def test_single_sample(self) -> None:
        assert can_auroc([1], [1], [0.5])["score"] == 0.0


# --- can_auprc ------------------------------------------------------------


class TestAuprc:

    def test_perfect_match(self) -> None:
        r = can_auprc([0, 0, 1, 1], [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
        assert r == {"evaluator": "can_auprc", "score": 1.0}

    def test_inverted(self) -> None:
        from sklearn.metrics import average_precision_score

        y_true = [0, 0, 1, 1]
        scores = [0.9, 0.8, 0.1, 0.2]
        expected = average_precision_score(y_true, scores)
        assert expected == pytest.approx(5 / 12, abs=1e-15)
        r = can_auprc(y_true, [1, 1, 0, 0], scores)
        assert r["score"] == pytest.approx(expected, abs=1e-15)

    def test_empty(self) -> None:
        assert can_auprc([], [], [])["score"] == 0.0

    def test_single_positive(self) -> None:
        assert can_auprc([1], [1], [0.9])["score"] == 1.0


# --- can_brier ------------------------------------------------------------


class TestBrier:

    def test_perfect(self) -> None:
        assert can_brier([0, 1], [0, 1], [0.0, 1.0])["score"] == 0.0

    def test_worst_case(self) -> None:
        r = can_brier([0, 0, 1, 1], [1, 1, 0, 0], [1, 1, 0, 0])
        assert r["score"] >= 0.9

    def test_empty(self) -> None:
        assert can_brier([], [], [])["score"] == 0.0

    def test_single_perfect(self) -> None:
        assert can_brier([1], [1], [1.0])["score"] == 0.0


# --- can_lead_time --------------------------------------------------------


class TestLeadTime:

    def test_early_detection(self) -> None:
        r = can_lead_time([0, 0, 0, 1, 1, 1], [1, 1, 0, 0, 0, 0],
                          [0.9, 0.8, 0.3, 0.1, 0.1, 0.1])
        assert r["score"] >= 2.0

    def test_no_early_detection(self) -> None:
        r = can_lead_time([0, 0, 1, 1], [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
        assert r["score"] == 0.0

    def test_empty(self) -> None:
        assert can_lead_time([], [], [])["score"] == 0.0

    def test_single_sample(self) -> None:
        assert can_lead_time([1], [1], [0.5])["score"] == 0.0


# --- can_false_alarm ------------------------------------------------------


class TestFalseAlarm:

    def test_no_fp(self) -> None:
        r = can_false_alarm([0, 0, 1, 1], [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
        assert r["score"] == 0.0

    def test_all_fp(self) -> None:
        r = can_false_alarm([0, 0, 0, 0], [1, 1, 1, 1], [0.9, 0.8, 0.7, 0.6])
        assert r["score"] == 1.0

    def test_empty(self) -> None:
        assert can_false_alarm([], [], [])["score"] == 0.0

    def test_single_correct(self) -> None:
        assert can_false_alarm([0], [0], [0.1])["score"] == 0.0


# --- can_episode_recall ---------------------------------------------------


class TestEpisodeRecall:

    def test_all_detected(self) -> None:
        r = can_episode_recall([0, 1, 1, 0, 1, 0], [0, 1, 0, 0, 1, 0],
                               [0.1, 0.9, 0.3, 0.1, 0.8, 0.1])
        assert r["score"] == 1.0

    def test_none_detected(self) -> None:
        r = can_episode_recall([0, 1, 1, 0], [0, 0, 0, 0], [0.1, 0.1, 0.1, 0.1])
        assert r["score"] == 0.0

    def test_empty(self) -> None:
        assert can_episode_recall([], [], [])["score"] == 0.0

    def test_single_positive_detected(self) -> None:
        assert can_episode_recall([1], [1], [0.9])["score"] == 1.0

    def test_no_episodes(self) -> None:
        assert can_episode_recall([0], [0], [0.1])["score"] == 0.0
