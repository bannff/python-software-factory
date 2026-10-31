"""Security, authority, composition, and registration tests for CAN terminals."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_evals_binding import (
    MlEvalsRecordPointer,
    verify_evaluation_pointers,
)
from factory.machine_learning.runtime.can_lifecycle_composition import (
    CanLifecycleOperations,
)
from factory.machine_learning.runtime.can_passport_operations import issue_passports
from factory.machine_learning.runtime.can_projection import project_pipeline_result
from factory.machine_learning.runtime.model_passport import ConformanceEvidence
from factory.machine_learning.runtime.passport_service import ModelPassportService
from factory.machine_learning.runtime.passport_store_models import (
    ModelPassportPublication,
    ModelPassportRef,
)
from factory.machine_learning.server import create_mcp_server

from .passport_fixtures import passport

_POINTER = {
    "collection": "eval_results", "doc_id": "eval-v2-run",
    "record_kind": "evaluation_run", "schema_version": 2,
    "revision": "v2", "content_hash": "sha256:" + "a" * 64,
}


def test_evals_verification_is_fail_closed_before_issue_effects(tmp_path: Path):
    calls = []

    def invoker(name, **kwargs):
        calls.append((name, kwargs))
        return {"verified": False, "reason": "tampered", "pointer": kwargs}

    class Context:
        def effect(self, *_args, **_kwargs):
            pytest.fail("passport effect must not run after Evals rejection")

    with pytest.raises(ValueError, match="tampered"):
        issue_passports(
            Context(), training_terminal={
                "status": "completed", "portfolio": [],
                "dataset_terminal": {"vehicle_id": "fixture", "legacy_projection": {}},
            }, evaluation_pointers=[_POINTER], invoker=invoker,
            service=object(), passport_root=tmp_path,
        )
    assert calls[0][0] == "evals_verify_record_pointer"


@pytest.mark.parametrize("mutation", [
    {"schema_version": True}, {"extra": "forbidden"}, {"schema_version": "2"},
])
def test_evals_pointer_is_strict_frozen_and_exact(mutation):
    with pytest.raises(ValidationError):
        MlEvalsRecordPointer.model_validate({**_POINTER, **mutation})
    pointer = MlEvalsRecordPointer.model_validate(_POINTER)
    with pytest.raises(ValidationError):
        pointer.revision = "changed"


def test_evals_verifier_returns_typed_canonical_exact_echo():
    verified = verify_evaluation_pointers(
        lambda _name, **kwargs: {"verified": True, "pointer": kwargs}, [_POINTER],
    )
    assert verified == (MlEvalsRecordPointer.model_validate(_POINTER),)
    with pytest.raises(ValueError, match="different pointer"):
        verify_evaluation_pointers(
            lambda _name, **_kwargs: {"verified": True, "pointer": {}}, [_POINTER],
        )


def test_conformance_and_promotion_are_split_by_composition(tmp_path: Path):
    candidate = passport(tmp_path, inference={
        "adapter": "can_inference", "loader": "mlflow.lightgbm", "version": "1",
    })
    ref = ModelPassportRef(
        model_id=candidate.model_id, model_version=candidate.model_version,
        passport_revision=1, uri=(tmp_path / "candidate.json").as_uri(),
        digest=candidate.passport_digest,
    )
    evidence = ConformanceEvidence(
        identity="lightgbm-isolated-effect",
        evidence=candidate.model_artifact.model_copy(update={"role": "conformance_evidence"}),
        model_digest=candidate.model_artifact.digest,
        inference_adapter=candidate.inference.adapter,
        inference_loader=candidate.inference.loader,
        inference_version=candidate.inference.version,
        preparation_contract_digest=candidate.preparation.feature_contract.digest,
        prepared_x_digest=candidate.preparation.x.digest,
        prepared_y_digest=candidate.preparation.y.digest,
        materializer_config_digest=candidate.preparation.materializer.config_digest,
        runtime_identity="python-test", probe_identity="probe-v1",
        verifier_identity="local-lightgbm-isolated-v1", fresh_runtime=True,
    )

    class Store:
        def __init__(self): self.published = []
        def get(self, _ref): return candidate
        def get_by_model(self, *_args): raise KeyError("missing")
        def publish(self, value):
            self.published.append(value)
            return ModelPassportPublication(status="published", ref=ref.model_copy(
                update={"passport_revision": value.passport_revision,
                        "digest": value.passport_digest}))

    class Runner:
        def __init__(self): self.calls = 0
        def run(self, *_args, **_kwargs): self.calls += 1; return evidence

    class Verifier:
        def verify(self, _value): return None

    store, runner = Store(), Runner()
    service = ModelPassportService(store=store, verifier=Verifier(), conformance_runner=runner)
    assert service.generate_conformance(ref, effect_id="e" * 64) == evidence
    assert store.published == [] and runner.calls == 1
    assert service.promote(ref, evidence).ref.passport_revision == 2
    assert len(store.published) == 1 and runner.calls == 1


def test_projection_rejects_candidate_as_deployability_authority(tmp_path: Path):
    candidate = passport(tmp_path)
    ref = ModelPassportRef(
        model_id=candidate.model_id, model_version=candidate.model_version,
        passport_revision=1, uri=(tmp_path / "candidate.json").as_uri(),
        digest=candidate.passport_digest,
    )
    with pytest.raises(ValueError, match="revision-two"):
        project_pipeline_result(
            training_terminal={"status": "completed"},
            promotion_terminal={
                "status": "completed", "passport_refs": [ref.model_dump(mode="json")],
            }, service=type("Service", (), {"get": lambda self, _ref: candidate})(),
        )


def test_non_lightgbm_rejected_before_dataset_effect(tmp_path: Path):
    calls = []
    operations = CanLifecycleOperations(
        root=tmp_path, runtime=object(), store=LocalCanLifecycleStore(tmp_path),
        invoker=lambda *_args, **_kwargs: calls.append(True), passport_service=object(),
    )
    result = operations.train({
        "attempt_id": "unsupported", "dataset_request": {"attempt_id": "dataset"},
        "model_family": "tcn",
    })
    assert result["status"] == "failed"
    assert "unsupported CAN lifecycle model_family" in result["error"] and calls == []
    assert result["operation"].endswith("@v1")


def test_generic_passport_contracts_default_empty_lifecycle_pointers(tmp_path: Path):
    candidate = passport(tmp_path)
    assert candidate.evaluation_pointers == ()
    assert candidate.can_legacy_binding is None


def test_exact_tools_are_registered():
    server = create_mcp_server(can_lifecycle_service=object(), passport_service=object())
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {
        "ml_train_can_portfolio", "ml_issue_can_passports",
        "ml_run_can_cold_conformance", "ml_promote_can_passports",
        "ml_project_can_pipeline_result",
    } <= names
