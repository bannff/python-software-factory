"""Per-case Evals binding selection during CAN passport issuance."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from factory.machine_learning.runtime.can_evaluation_contracts import (
    CanEvaluationEvidence, CanEvaluatorProvenance,
)
from factory.machine_learning.runtime.can_evaluation_policy import (
    adequacy_binding, derive_case, derive_run,
)
from factory.machine_learning.runtime.can_lifecycle_refs import (
    CanEvalsPointer, CanLegacyBinding,
)
from factory.machine_learning.runtime.can_passport_operations import issue_passports
from factory.machine_learning.runtime.can_training_job_rehydrate import (
    rehydrate_training_job,
)
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef

from .passport_fixtures import passport

_POINTER = {
    "collection": "eval_results", "doc_id": "eval-v2-multi",
    "record_kind": "evaluation_run", "schema_version": 2,
    "revision": "v2", "content_hash": "sha256:" + "a" * 64,
}
_METRICS = {
    "accuracy": 0.8, "precision": 0.7, "recall": 0.7, "f1": 0.7,
    "auroc": 0.8, "auprc": 0.7, "brier": 0.2,
}
_EVIDENCE = CanEvaluationEvidence(
    scope="synthetic_sensitivity", split_kind="ordered_holdout",
    validation_count=30, positive_count=15, negative_count=15,
)


def _provenance(index):
    return CanEvaluatorProvenance(
        schema="evals.can-model-evidence", version="1.0",
        evaluator_identity="evals.can-model@v1",
        input_digest="sha256:" + str(index) * 64,
    )


def _adequacy():
    return derive_run(tuple(derive_case(
        case_id=f"0x{index}", model_id=f"model-{index}", metrics=_METRICS,
        evidence=_EVIDENCE, provenance=_provenance(index),
    ) for index in (1, 2)))


def _response():
    raw = _adequacy().model_dump(mode="json")
    return {
        "verified": True, "pointer": _POINTER, "run_id": "multi",
        "case_results": raw["cases"],
        "case_scores": [case["score"] for case in raw["cases"]],
        "verdict": raw["verdict"], "pass_rate": raw["pass_rate"],
        "avg_score": raw["avg_score"], "total_cases": 2,
        "passed_cases": 2, "failed_cases": 0,
        "evaluators_used": ["evals.can-model@v1"],
        "summary": {"adequacy": raw, "portfolio": "two"},
    }


def _projection(can_ids):
    return {
        "ingest": {"job_id": "ingest", "n_mf4": 1},
        "profile": {"job_id": "profile"},
        "contract_artifacts": {"schema": {
            "job_id": "schema", "uri": "file:///schema", "digest": "c" * 64,
        }},
        "synthesize": {"job_id": "synth"}, "window": {"job_id": "window"},
        "augment": {"job_id": "augment"}, "top_can_ids": can_ids,
    }


def _legacy(can_id):
    return CanLegacyBinding(
        vehicle_id="truck", can_id=can_id, rank=1, n_windows=30,
        n_features=2, window_size=2, label_dist={"0": 15, "1": 15},
        dataset_projection=_projection([can_id]),
    )


def _file(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(name.encode())
    return {"uri": path.as_uri(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _terminal(tmp_path):
    lineage = {name: _file(tmp_path, name) for name in (
        "augmented.jsonl", "augmented-manifest.json", "synthesis.jsonl",
        "synthesis-manifest.json",
    )}
    rows = []
    for index in (1, 2):
        rows.append({
            "rank": index, "can_id": f"0x{index}", "job_id": f"model-{index}",
            "training_config": {}, "metrics": _METRICS,
            "model_path": f"file:///model-{index}", "n_samples": 30,
            "window_size": 2, "n_features": 2, "label_dist": {"0": 15, "1": 15},
            "artifact_refs": {
                key: {"uri": f"file:///{key}-{index}", "sha256": "d" * 64}
                for key in ("contract", "x_2d", "y")
            },
        })
    return {
        "status": "completed", "portfolio": rows,
        "dataset_terminal": {
            "vehicle_id": "truck", "legacy_projection": _projection(["0x1", "0x2"]),
            "training_bundle": {
                "augmented_dataset": lineage["augmented.jsonl"],
                "augmented_manifest": lineage["augmented-manifest.json"],
            },
            "artifacts": {
                "synthesize:dataset": lineage["synthesis.jsonl"],
                "synthesize:manifest": lineage["synthesis-manifest.json"],
            },
        },
    }


def test_each_passport_receives_only_its_exact_case_binding(tmp_path, monkeypatch):
    observed = []
    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_passport_operations.load_can_feature_contract",
        lambda _uri: SimpleNamespace(version="1", digest="d" * 64),
    )
    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_passport_operations.require_training_model_seal",
        lambda *_args: None,
    )

    def issue(*, context, job, **_kwargs):
        observed.append((job.id, context.legacy_binding.can_id, context.evaluation_adequacy))
        ref = ModelPassportRef(
            model_id=job.id, model_version="1", passport_revision=1,
            uri=f"file:///{job.id}.json", digest="e" * 64,
        )
        return object(), SimpleNamespace(ref=ref)

    monkeypatch.setattr(
        "factory.machine_learning.runtime.can_passport_operations.issue_can_model_passport",
        issue,
    )

    class Context:
        def effect(self, _unit, _inputs, _reconcile, execute):
            return execute("effect")

    result = issue_passports(
        Context(), training_terminal=_terminal(tmp_path),
        evaluation_pointers=[_POINTER],
        invoker=lambda *_args, **_kwargs: _response(), service=object(),
        passport_root=tmp_path,
    )
    assert result["can_ids"] == ["0x1", "0x2"]
    assert [(model, case, len(bindings)) for model, case, bindings in observed] == [
        ("model-1", "0x1", 1), ("model-2", "0x2", 1),
    ]
    for model, case, bindings in observed:
        assert (bindings[0].model_id, bindings[0].case_id) == (model, case)


def test_cross_model_or_case_binding_is_rejected(tmp_path):
    pointer = CanEvalsPointer.model_validate(_POINTER)
    first = derive_run((_adequacy().cases[0],))
    binding = adequacy_binding(pointer, "multi", first)
    with pytest.raises(ValidationError, match="passport model and CAN-ID"):
        passport(
            tmp_path, model_id="model-2", can_legacy_binding=_legacy("0x2"),
            evaluation_pointers=(pointer,), evaluation_adequacy=(binding,),
        )


def test_explicit_unsupported_family_remains_rejected(tmp_path):
    row = _terminal(tmp_path)["portfolio"][0]
    row["model_family"] = "tcn"
    with pytest.raises(ValueError, match="unsupported CAN lifecycle model_family: tcn"):
        rehydrate_training_job(row)
