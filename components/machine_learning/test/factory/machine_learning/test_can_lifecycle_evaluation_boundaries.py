"""Evaluation-record and training-seal boundaries for CAN lifecycle."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from factory.machine_learning.runtime.can_passport_operations import issue_passports
from factory.machine_learning.runtime.can_training_seal_binding import (
    require_training_model_seal,
)
from pydantic import ValidationError

_POINTER = {
    "collection": "eval_results",
    "doc_id": "eval-v2-run",
    "record_kind": "evaluation_run",
    "schema_version": 2,
    "revision": "v2",
    "content_hash": "sha256:" + "a" * 64,
}


def _training_row(digest: str) -> dict:
    return {
        "rank": 1,
        "can_id": "0x1",
        "model_family": "lightgbm",
        "job_id": "job@v1",
        "model_path": "file:///model",
        "metrics": {
            "accuracy": 0.8,
            "precision": 0.7,
            "recall": 0.7,
            "f1": 0.7,
            "auroc": 0.8,
            "auprc": 0.7,
            "brier": 0.2,
        },
        "evaluation_evidence": {
            "scope": "synthetic_sensitivity",
            "split_kind": "ordered_holdout",
            "validation_count": 2,
            "positive_count": 1,
            "negative_count": 1,
        },
        "evaluator_provenance": {
            "schema": "evals.can-model-evidence",
            "version": "1.0",
            "evaluator_identity": "evals.can-model@v1",
            "input_digest": "sha256:" + "b" * 64,
        },
        "training_config": {},
        "artifact_seal": {
            "uri": "file:///seal",
            "sha256": digest,
            "model_tree_sha256": digest,
        },
        "n_samples": 2,
        "window_size": 1,
        "n_features": 1,
        "label_dist": {"0": 1, "1": 1},
        "x_shape": [2, 1],
        "contract_digest": digest,
        "artifact_refs": {
            name: {"uri": f"file:///{name}", "sha256": digest, "evidence": {"sha256": digest}}
            for name in ("contract", "x_2d", "y")
        },
    }


def test_score_projection_pointer_is_rejected_before_issuance_effect(tmp_path: Path):
    pointer = {
        **_POINTER,
        "doc_id": "eval-score-v2-run",
        "record_kind": "evaluation_score_projection",
    }
    with pytest.raises(ValidationError, match="evaluation_run"):
        issue_passports(
            object(),
            training_terminal={
                "status": "completed",
                "portfolio": [],
                "dataset_terminal": {"vehicle_id": "fixture", "legacy_projection": {}},
            },
            evaluation_pointers=[pointer],
            invoker=lambda *_args, **_kwargs: pytest.fail("must fail before Evals call"),
            service=object(),
            passport_root=tmp_path,
        )


def test_training_model_tree_must_match_trusted_seal_before_issuance(tmp_path: Path):
    model = tmp_path / "models/effect/mlflow-model"
    model.mkdir(parents=True)
    (model / "MLmodel").write_text("trusted")
    seal = tmp_path / "seal.json"
    seal.write_text("sealed")
    seal.chmod(0o444)
    row = {
        "model_path": str(model),
        "artifact_seal": {
            "uri": seal.as_uri(),
            "sha256": hashlib.sha256(seal.read_bytes()).hexdigest(),
            "model_tree_sha256": "0" * 64,
        },
    }
    with pytest.raises(ValueError, match="trusted training seal"):
        require_training_model_seal(row, tmp_path)
