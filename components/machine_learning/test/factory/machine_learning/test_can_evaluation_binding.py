"""Rich Evals verification and pre-effect promotion guards."""
from __future__ import annotations

from copy import deepcopy
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
from factory.machine_learning.runtime.can_evals_binding import verify_evaluation_records
from factory.machine_learning.runtime.can_lifecycle_refs import (
    CanEvalsPointer, CanLegacyBinding,
)
from factory.machine_learning.runtime.can_passport_operations import promote_passports
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef

from .passport_fixtures import passport

_POINTER = {
    "collection": "eval_results", "doc_id": "eval-v2-run",
    "record_kind": "evaluation_run", "schema_version": 2,
    "revision": "v2", "content_hash": "sha256:" + "a" * 64,
}
GOOD = {
    "accuracy": 0.8, "precision": 0.7, "recall": 0.7, "f1": 0.7,
    "auroc": 0.8, "auprc": 0.7, "brier": 0.2,
}
EVIDENCE = CanEvaluationEvidence(
    scope="synthetic_sensitivity", split_kind="ordered_holdout",
    validation_count=30, positive_count=15, negative_count=15,
)
PROVENANCE = CanEvaluatorProvenance(
    schema="evals.can-model-evidence", version="1.0",
    evaluator_identity="evals.can-model@v1", input_digest="sha256:" + "b" * 64,
)


def _adequacy(metrics=GOOD, case_id="0x1", model_id="model-1"):
    case = derive_case(
        case_id=case_id, model_id=model_id, metrics=metrics, evidence=EVIDENCE,
        provenance=PROVENANCE,
    )
    return derive_run((case,))


def _response(adequacy, *, summary=None):
    raw = adequacy.model_dump(mode="json")
    return {
        "verified": True, "pointer": dict(_POINTER), "run_id": "v2-run",
        "case_results": raw["cases"],
        "case_scores": [case["score"] for case in raw["cases"]],
        "verdict": raw["verdict"], "pass_rate": raw["pass_rate"],
        "avg_score": raw["avg_score"], "total_cases": raw["total_cases"],
        "passed_cases": raw["passed"], "failed_cases": raw["failed"],
        "evaluators_used": ["evals.can-model@v1"],
        "summary": summary or {"adequacy": raw, "authenticated": "complete"},
    }


def _legacy(can_id="0x1"):
    return CanLegacyBinding(
        vehicle_id="truck", can_id=can_id, rank=1, n_windows=30,
        n_features=2, window_size=2, label_dist={"0": 15, "1": 15},
        dataset_projection={
            "ingest": {"job_id": "ingest", "n_mf4": 1},
            "profile": {"job_id": "profile"},
            "contract_artifacts": {"schema": {
                "job_id": "schema", "uri": "file:///schema",
                "digest": "c" * 64,
            }},
            "synthesize": {"job_id": "synth"},
            "window": {"job_id": "window"},
            "augment": {"job_id": "augment"},
            "top_can_ids": [can_id],
        },
    )


def test_rich_verifier_returns_per_case_binding_and_full_summary_digest():
    adequacy = _adequacy()
    response = _response(adequacy)
    record = verify_evaluation_records(lambda *_args, **_kwargs: response, [_POINTER])[0]
    binding = record.binding_for("model-1", "0x1")
    assert record.pointer == CanEvalsPointer.model_validate(_POINTER)
    assert record.adequacy == adequacy
    assert binding.pointer == record.pointer
    assert binding.case_id == "0x1" and binding.model_id == "model-1"
    assert binding.input_digest == PROVENANCE.input_digest
    assert binding.run_verdict == "PASS"
    changed = _response(adequacy, summary={
        "adequacy": adequacy.model_dump(mode="json"), "authenticated": "changed",
    })
    changed_binding = verify_evaluation_records(
        lambda *_args, **_kwargs: changed, [_POINTER],
    )[0].binding
    assert changed_binding.summary_digest != binding.summary_digest


@pytest.mark.parametrize("mutation", [
    "case", "aggregate", "evaluator", "summary", "provenance",
])
def test_rich_verifier_rejects_raw_fact_and_summary_attacks(mutation):
    adequacy = _adequacy()
    response = deepcopy(_response(adequacy))
    if mutation == "case":
        response["case_results"][0]["score"] = 0.99
    elif mutation == "aggregate":
        response["passed_cases"] = 0
    elif mutation == "evaluator":
        response["evaluators_used"] = ["ml.policy@v1"]
    elif mutation == "summary":
        response["summary"]["adequacy"]["passed"] = 0
    else:
        response["case_results"][0]["evaluator_provenance"][
            "evaluator_identity"
        ] = "spoofed@v1"
    with pytest.raises(ValueError, match="adequacy"):
        verify_evaluation_records(lambda *_args, **_kwargs: response, [_POINTER])


def test_pointer_and_adequacy_binding_must_correspond(tmp_path: Path):
    pointer = CanEvalsPointer.model_validate(_POINTER)
    binding = adequacy_binding(pointer, "v2-run", _adequacy())
    other = pointer.model_copy(update={"doc_id": "eval-other"})
    with pytest.raises(ValidationError, match="correspond exactly"):
        passport(
            tmp_path, evaluation_pointers=(other,), evaluation_adequacy=(binding,),
            can_legacy_binding=_legacy(),
        )


@pytest.mark.parametrize("metrics", [GOOD, {**GOOD, "f1": 0.1}])
def test_synthetic_pass_or_fail_rejects_promotion_before_effect_and_service(
    tmp_path: Path, metrics,
):
    pointer = CanEvalsPointer.model_validate(_POINTER)
    adequacy = _adequacy(metrics)
    response = _response(adequacy)
    binding = adequacy_binding(pointer, "v2-run", adequacy, response["summary"])
    candidate = passport(
        tmp_path, evaluation_pointers=(pointer,), evaluation_adequacy=(binding,),
        can_legacy_binding=_legacy(),
    )
    ref = ModelPassportRef(
        model_id=candidate.model_id, model_version=candidate.model_version,
        passport_revision=1, uri=(tmp_path / "candidate.json").as_uri(),
        digest=candidate.passport_digest,
    )
    calls = {"effect": 0, "service": 0}

    class Context:
        def conformance_receipt(self, *_args):
            return SimpleNamespace(effect_id="e" * 64, unit="unused", inputs={}), SimpleNamespace(
                output={"passport_ref": ref.model_dump(mode="json"),
                        "conformance_evidence": {}},
            )
        def effect(self, *_args, **_kwargs):
            calls["effect"] += 1
            pytest.fail("promotion effect must not run")

    class Service:
        def get(self, _ref): return candidate
        def promote_lifecycle(self, *_args, **_kwargs):
            calls["service"] += 1
            pytest.fail("promotion service must not run")

    with pytest.raises(ValueError, match="ineligible|failing"):
        promote_passports(
            Context(), conformance_receipt_refs=[{"receipt": "x"}],
            invoker=lambda *_args, **_kwargs: response, service=Service(),
        )
    assert calls == {"effect": 0, "service": 0}
