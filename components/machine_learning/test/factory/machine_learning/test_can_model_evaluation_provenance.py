"""Strict Evals-owned held-out metric provenance tests."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from factory.machine_learning.runtime.can_model_evaluation import (
    canonical_input_digest, evaluate_holdout, evaluate_predictions,
)


class _Model:
    def predict(self, value):
        assert value.tolist() == [[10.0], [20.0]]
        return np.array([0, 1])

    def predict_proba(self, value):
        assert value.tolist() == [[10.0], [20.0]]
        return np.array([[0.8, 0.2], [0.1, 0.9]])


def _split(monkeypatch):
    X_val = np.array([[10.0], [20.0]])
    y_val = np.array([0, 1])
    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_model_evaluation."
        "temporal_split_with_shuffle_fallback",
        lambda *_args: (np.empty((0, 1)), np.empty(0), X_val, y_val),
    )
    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_model_evaluation.temporal_split_strategy",
        lambda *_args: "ordered_holdout",
    )


def _envelope(y_true, y_pred, y_score, **changes):
    value = {
        "schema": "evals.can-model-evidence", "version": "1.0",
        "evaluator_identity": "evals.can-model@v1",
        "input_digest": canonical_input_digest(y_true, y_pred, y_score),
        "metrics": {
            "accuracy": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "auroc": 1.0, "auprc": 1.0, "brier": 0.025,
        },
    }
    value.update(changes)
    return value


def test_exact_held_out_arrays_are_sent_once_and_digest_is_checked(monkeypatch):
    _split(monkeypatch)
    calls = []

    def evaluator(**kwargs):
        calls.append(kwargs)
        return _envelope(**kwargs)

    metrics, evidence, provenance = evaluate_holdout(
        np.array([[0.0], [1.0]]), np.array([0, 1]), _Model(),
        SimpleNamespace(validation_split=0.2, seed=42), evaluator,
    )
    assert calls == [{
        "y_true": [0, 1], "y_pred": [0, 1], "y_score": [0.2, 0.9],
    }]
    assert metrics["f1"] == 1.0
    assert evidence["validation_count"] == 2
    assert provenance.input_digest == canonical_input_digest(**calls[0])


@pytest.mark.parametrize("spoof", ["digest", "identity"])
def test_spoofed_digest_or_evaluator_identity_is_rejected(monkeypatch, spoof):
    _split(monkeypatch)

    def evaluator(**kwargs):
        change = (
            {"input_digest": "sha256:" + "0" * 64}
            if spoof == "digest" else {"evaluator_identity": "ml.policy@v1"}
        )
        return _envelope(**kwargs, **change)

    with pytest.raises(ValueError, match="digest mismatch|unknown provenance"):
        evaluate_holdout(
            np.array([[0.0], [1.0]]), np.array([0, 1]), _Model(),
            SimpleNamespace(validation_split=0.2, seed=42), evaluator,
        )


def test_typed_evals_envelope_omits_unavailable_one_class_metrics() -> None:
    y_true, y_pred, y_score = [1.0, 1.0], [1.0, 1.0], [0.9, 0.8]
    evidence = _envelope(y_true, y_pred, y_score)
    evidence["metrics"].update({
        "auroc": None, "auprc": None, "brier": None, "lead_time": None,
        "false_alarm": None, "episode_recall": None,
    })
    envelope = {
        "schema_version": "v1", "ok": True, "data": evidence,
        "error": None, "idempotency_key": None,
    }

    metrics, _, provenance = evaluate_predictions(
        y_true, y_pred, y_score, lambda **_: envelope,
    )

    assert metrics == {"accuracy": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert provenance.input_digest == canonical_input_digest(y_true, y_pred, y_score)


@pytest.mark.parametrize("invalid", [True, "not-a-number"])
def test_typed_evals_envelope_rejects_invalid_present_metrics(invalid) -> None:
    y_true, y_pred, y_score = [0.0, 1.0], [0.0, 1.0], [0.2, 0.9]
    evidence = _envelope(y_true, y_pred, y_score)
    evidence["metrics"]["auroc"] = invalid
    envelope = {
        "schema_version": "v1", "ok": True, "data": evidence,
        "error": None, "idempotency_key": None,
    }

    with pytest.raises(ValueError, match="malformed metrics"):
        evaluate_predictions(y_true, y_pred, y_score, lambda **_: envelope)
