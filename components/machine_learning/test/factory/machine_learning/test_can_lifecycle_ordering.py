"""Reference authority, pointer ordering, and legacy projection composition tests."""
from __future__ import annotations
from pathlib import Path
import pytest
from factory.machine_learning.runtime.adapters.local_can_lifecycle import LocalCanLifecycleStore
from factory.machine_learning.runtime.can_evaluation_contracts import (
    CanEvaluationEvidence, CanEvaluatorProvenance,
)
from factory.machine_learning.runtime.can_evaluation_policy import (
    adequacy_binding, derive_case, derive_run,
)
from factory.machine_learning.runtime.can_evals_binding import MlEvalsRecordPointer
from factory.machine_learning.runtime.can_lifecycle_canonical import (
    CONFORM_OPERATION, PROMOTE_OPERATION,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext
from factory.machine_learning.runtime.can_lifecycle_refs import CanLegacyBinding
from factory.machine_learning.runtime.can_passport_operations import (
    promote_passports, run_conformance,
)
from factory.machine_learning.runtime.can_projection import project_pipeline_result
from factory.machine_learning.runtime.model_passport import ConformanceEvidence
from factory.machine_learning.runtime.passport_service import ModelPassportService
from factory.machine_learning.runtime.passport_store_models import (
    ModelPassportPublication, ModelPassportRef,
)
from .passport_fixtures import passport
_POINTER = {
    "collection": "eval_results", "doc_id": "eval-v2-run",
    "record_kind": "evaluation_run", "schema_version": 2,
    "revision": "v2", "content_hash": "sha256:" + "a" * 64,
}
_POLICY_METRICS = {
    "accuracy": 0.8, "precision": 0.7, "recall": 0.7, "f1": 0.7,
    "auroc": 0.8, "auprc": 0.7, "brier": 0.2,
}
_POLICY_EVIDENCE = CanEvaluationEvidence(
    scope="synthetic_sensitivity", split_kind="ordered_holdout",
    validation_count=30, positive_count=15, negative_count=15,
)
_POLICY_PROVENANCE = CanEvaluatorProvenance(
    schema="evals.can-model-evidence", version="1.0",
    evaluator_identity="evals.can-model@v1", input_digest="sha256:" + "b" * 64,
)
_POLICY_ADEQUACY = derive_run((derive_case(
    case_id="0x1", model_id="model-1", metrics=_POLICY_METRICS,
    evidence=_POLICY_EVIDENCE, provenance=_POLICY_PROVENANCE,
),))
_PROJECTION = {
    "ingest": {"job_id": "ingest", "n_mf4": 2},
    "profile": {"job_id": "profile"},
    "contract_artifacts": {"schema": {
        "job_id": "schema", "uri": "file:///x", "digest": "a" * 64,
    }},
    "synthesize": {"job_id": "synth"}, "window": {"job_id": "window"},
    "augment": {"job_id": "augment"}, "top_can_ids": ["0x1"],
    "context": {"ingest": "ctx"}, "context_artifacts": {"correlate": "file:///ctx"},
}

def _accept(_name, **kwargs):
    raw = _POLICY_ADEQUACY.model_dump(mode="json")
    return {
        "verified": True, "pointer": kwargs, "run_id": "v2-run",
        "case_results": raw["cases"], "case_scores": [raw["cases"][0]["score"]],
        "verdict": raw["verdict"], "pass_rate": raw["pass_rate"],
        "avg_score": raw["avg_score"], "total_cases": raw["total_cases"],
        "passed_cases": raw["passed"], "failed_cases": raw["failed"],
        "evaluators_used": ["evals.can-model@v1"],
        "summary": {"adequacy": raw},
    }

def _candidate(
    tmp_path: Path, *, pointers=None, rank=1, can_id="0x1", vehicle_id="truck-1",
):
    typed = tuple(pointers) if pointers is not None else ()
    bindings = tuple(
        adequacy_binding(pointer, "v2-run", _POLICY_ADEQUACY)
        for pointer in typed
    )
    value = passport(
        tmp_path, evaluation_pointers=typed, evaluation_adequacy=bindings,
        can_legacy_binding=CanLegacyBinding(
            vehicle_id=vehicle_id, can_id=can_id, rank=rank,
            n_windows=12, n_features=4, window_size=3,
            label_dist={"0": 7, "1": 5},
            dataset_projection={**_PROJECTION, "top_can_ids": [can_id]},
        ),
        inference={
            "adapter": "can_inference", "loader": "mlflow.lightgbm", "version": "1",
        },
    )
    ref = ModelPassportRef(
        model_id=value.model_id, model_version=value.model_version,
        passport_revision=1, uri=(tmp_path / f"candidate-{rank}.json").as_uri(),
        digest=value.passport_digest,
    )
    evidence = ConformanceEvidence(
        identity=f"lightgbm-isolated-effect-{rank}",
        evidence=value.model_artifact.model_copy(update={"role": "conformance_evidence"}),
        evaluation_pointers=typed, model_digest=value.model_artifact.digest,
        inference_adapter=value.inference.adapter,
        inference_loader=value.inference.loader,
        inference_version=value.inference.version,
        preparation_contract_digest=value.preparation.feature_contract.digest,
        prepared_x_digest=value.preparation.x.digest,
        prepared_y_digest=value.preparation.y.digest,
        materializer_config_digest=value.preparation.materializer.config_digest,
        runtime_identity="python-test", probe_identity="probe-v1",
        verifier_identity="local-lightgbm-isolated-v1", fresh_runtime=True,
    )
    return value, ref, evidence

def _training_terminal(candidate, *, rank=1, can_id="0x1", vehicle_id="truck-1"):
    projection = {**_PROJECTION, "top_can_ids": [can_id]}
    return {
        "status": "completed",
        "dataset_terminal": {
            "vehicle_id": vehicle_id, "legacy_projection": projection,
        },
        "portfolio": [{
            "rank": rank, "can_id": can_id, "job_id": candidate.model_id,
            "metrics": candidate.final_metrics,
            "contract_digest": candidate.preparation.feature_contract.digest,
            "artifact_seal": {"model_tree_sha256": candidate.model_artifact.digest},
            "model_path": candidate.model_artifact.uri,
            "n_samples": 12, "n_features": 4, "window_size": 3,
            "label_dist": {"0": 7, "1": 5},
            "artifact_refs": {
                "x_2d": {"sha256": candidate.preparation.x.digest},
                "y": {"sha256": candidate.preparation.y.digest},
            },
        }],
    }


def test_conformance_succeeds_but_synthetic_promotion_fails_closed(tmp_path: Path):
    pointer = MlEvalsRecordPointer.model_validate(_POINTER)
    candidate, ref, evidence = _candidate(tmp_path, pointers=(pointer,))
    class Service:
        promotion_calls = 0
        def get(self, observed): assert observed == ref; return candidate
        def generate_conformance(self, observed, *, effect_id):
            assert observed == ref and len(effect_id) == 64
            return evidence
        def promote_lifecycle(self, *_args, **_kwargs):
            self.promotion_calls += 1
            pytest.fail("synthetic adequacy must not reach promotion service")
    store = LocalCanLifecycleStore(tmp_path / "lifecycle")
    conformance = run_conformance(
        CanLifecycleContext(CONFORM_OPERATION, "c" * 64, store),
        passport_refs=[ref.model_dump(mode="json")], invoker=_accept, service=Service(),
    )
    assert conformance["passport_refs"] == [ref.model_dump(mode="json")]
    assert conformance["receipts"][0]["can_id"] == "0x1"
    assert "conformance_evidence" not in conformance
    with pytest.raises(ValueError, match="ineligible"):
        promote_passports(
            CanLifecycleContext(PROMOTE_OPERATION, "d" * 64, store),
            conformance_receipt_refs=conformance["conformance_receipt_refs"],
            invoker=_accept, service=Service(),
        )

def test_conformance_and_receipt_pointer_mismatch_fail_closed(tmp_path: Path):
    pointer = MlEvalsRecordPointer.model_validate(_POINTER)
    candidate, ref, evidence = _candidate(tmp_path, pointers=(pointer,))
    mismatch = MlEvalsRecordPointer.model_validate({**_POINTER, "doc_id": "other"})
    bad = evidence.model_copy(update={"evaluation_pointers": (mismatch,)})
    class Service:
        def get(self, _ref): return candidate
        def generate_conformance(self, *_args, **_kwargs): return bad
    with pytest.raises(ValueError, match="changed verified Evals"):
        run_conformance(
            CanLifecycleContext(
                CONFORM_OPERATION, "c" * 64, LocalCanLifecycleStore(tmp_path / "bad"),
            ),
            passport_refs=[ref.model_dump(mode="json")], invoker=_accept,
            service=Service(),
        )

def test_cross_operation_conformance_reference_fails_closed(tmp_path: Path):
    pointer = MlEvalsRecordPointer.model_validate(_POINTER)
    candidate, ref, evidence = _candidate(tmp_path, pointers=(pointer,))
    class Service:
        def get(self, _ref): return candidate
        def generate_conformance(self, *_args, **_kwargs): return evidence
    store = LocalCanLifecycleStore(tmp_path / "cross")
    result = run_conformance(
        CanLifecycleContext(CONFORM_OPERATION, "c" * 64, store),
        passport_refs=[ref.model_dump(mode="json")], invoker=_accept, service=Service(),
    )
    forged = dict(result["conformance_receipt_refs"][0])
    forged["operation"] = "ml_issue_can_passports@v1"
    with pytest.raises(ValueError, match="crosses"):
        promote_passports(
            CanLifecycleContext(PROMOTE_OPERATION, "d" * 64, store),
            conformance_receipt_refs=[forged], invoker=_accept, service=Service(),
        )

def test_projection_reconstructs_full_legacy_shape_from_promoted_passport(tmp_path: Path):
    candidate, ref, evidence = _candidate(tmp_path)
    class Store:
        def __init__(self): self.promoted = None
        def get(self, _ref): return candidate
        def get_by_model(self, *_args): raise KeyError("missing")
        def publish(self, value):
            self.promoted = value
            return ModelPassportPublication(status="published", ref=ref.model_copy(
                update={"passport_revision": value.passport_revision,
                        "digest": value.passport_digest}))
    class Verifier:
        def verify(self, _value): pass
    store = Store()
    service = ModelPassportService(store=store, verifier=Verifier())
    promoted_ref = service.promote(ref, evidence).ref
    reader = type("Reader", (), {"get": lambda self, _ref: store.promoted})()
    result = project_pipeline_result(
        training_terminal=_training_terminal(candidate),
        promotion_terminal={
            "status": "completed", "passport_refs": [promoted_ref.model_dump(mode="json")],
        },
        service=reader,
    )
    assert set(result) == {
        "vehicle_id", "ingest", "profile", "contract_artifacts", "synthesize",
        "window", "augment", "top_can_ids", "comparison_table", "model_ids",
        "deployable_model_ids", "warm_model_ids", "inference_gate", "context",
        "context_artifacts",
    }
    assert result["vehicle_id"] == "truck-1"
    assert result["top_can_ids"] == ["0x1"]
    assert result["deployable_model_ids"] == result["model_ids"]
    assert result["warm_model_ids"] == []
    assert result["inference_gate"]["status"] == "passed"
    assert result["inference_gate"]["warm_model_ids"] == []
    row = result["comparison_table"][0]
    assert set(row) == {
        "rank", "can_id", "model_id", "model_version", "model_type",
        "n_windows", "n_features", "window_size", "label_dist", "metrics",
        "model_path", "model_digest", "contract_uri", "contract_digest",
        "passport_ref", "passport_digest", "passport_revision", "passport_status",
        "promotion_status", "conformance_status", "inference_gate",
        "inference_registered", "registration_status",
    }
    assert (row["n_windows"], row["n_features"], row["window_size"]) == (12, 4, 3)
    assert row["label_dist"] == {"0": 7, "1": 5}
    assert row["contract_uri"] == store.promoted.preparation.feature_contract.uri
    assert row["contract_digest"] == store.promoted.preparation.feature_contract.digest
    assert row["model_path"] == store.promoted.model_artifact.uri
    assert row["model_digest"] == store.promoted.model_artifact.digest
    assert row["passport_status"] == "published"
    assert row["inference_registered"] is False
    substituted = _training_terminal(candidate)
    substituted["portfolio"][0]["artifact_seal"]["model_tree_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="trusted training"):
        project_pipeline_result(
            training_terminal=substituted,
            promotion_terminal={
                "status": "completed",
                "passport_refs": [promoted_ref.model_dump(mode="json")],
            },
            service=reader,
        )

def test_projection_rejects_disagreeing_legacy_bindings(tmp_path: Path):
    (tmp_path / "one").mkdir(); (tmp_path / "two").mkdir()
    inputs = [
        _candidate(tmp_path / "one", rank=1, can_id="0x1"),
        _candidate(tmp_path / "two", rank=2, can_id="0x2", vehicle_id="other"),
    ]
    promoted = []
    for candidate, ref, evidence in inputs:
        class Store:
            value = None
            def get(self, _ref): return candidate
            def get_by_model(self, *_args): raise KeyError("missing")
            def publish(self, value):
                self.value = value
                return ModelPassportPublication(status="published", ref=ref.model_copy(
                    update={"passport_revision": 2, "digest": value.passport_digest}))
        store = Store()
        service = ModelPassportService(
            store=store, verifier=type("Verifier", (), {"verify": lambda self, value: None})(),
        )
        promoted_ref = service.promote(ref, evidence).ref
        promoted.append((promoted_ref, store.value))
    passports = {ref.digest: value for ref, value in promoted}
    with pytest.raises(ValueError, match="bindings disagree"):
        project_pipeline_result(
            training_terminal={"status": "completed"},
            promotion_terminal={
                "status": "completed",
                "passport_refs": [ref.model_dump(mode="json") for ref, _ in promoted],
            },
            service=type("Reader", (), {
                "get": lambda self, observed: passports[observed.digest],
            })(),
        )
