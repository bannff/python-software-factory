"""Generic ModelPassport contract and digest properties."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from pydantic import ValidationError

from factory.machine_learning.runtime.model_passport import ConformanceEvidence, ModelPassport
from factory.machine_learning.runtime.passport_codec import (
    create_model_passport, load_model_passport, passport_artifact_bytes,
)
from factory.machine_learning.runtime.passport_refs import ArchitectureBinding
from factory.machine_learning.runtime.passport_probe_contracts import PassportProbeInput
from factory.machine_learning.runtime.passport_validation import canonical_json

from .passport_fixtures import passport


def _reissue(value: ModelPassport, **updates) -> ModelPassport:
    body = value.model_dump(mode="python", exclude={"passport_digest"})
    body.update(updates)
    return create_model_passport(**body)


def test_candidate_is_frozen_strict_canonical_and_generic(tmp_path: Path) -> None:
    value = passport(tmp_path)
    assert value.promotion_status == "candidate"
    assert value.conformance_status == "not_run"
    assert "can_id" not in ModelPassport.model_fields
    assert load_model_passport(passport_artifact_bytes(value)) == value
    with pytest.raises(ValidationError):
        value.model_id = "changed"  # type: ignore[misc]
    raw = value.model_dump(mode="python")
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        ModelPassport.model_validate(raw)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_metrics_and_config_are_rejected(tmp_path: Path, bad: float) -> None:
    base = passport(tmp_path)
    with pytest.raises(ValidationError, match="NaN|Infinity"):
        _reissue(base, final_metrics={"auroc": bad})
    architecture = ArchitectureBinding(
        architecture="tree", framework="lightgbm", framework_version="4",
        config={"nested": [bad]},
    )
    with pytest.raises(ValidationError, match="NaN|Infinity"):
        _reissue(base, architecture=architecture)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(order=st.permutations((0, 1, 2, 3)))
def test_semantic_digest_sorts_only_declared_set_like_lineage(
    tmp_path: Path, order: list[int],
) -> None:
    base = passport(tmp_path)
    lineage = tuple(base.lineage_artifacts[index] for index in order)
    reordered = _reissue(base, lineage_artifacts=lineage)
    assert reordered.passport_digest == base.passport_digest
    changed_order = _reissue(
        base, limitations=tuple(reversed(("first limitation", "second limitation"))),
    )
    original_order = _reissue(
        base, limitations=("first limitation", "second limitation"),
    )
    assert changed_order.passport_digest != original_order.passport_digest


def test_promotable_requires_exact_fresh_runtime_evidence(tmp_path: Path) -> None:
    base = passport(tmp_path)
    with pytest.raises(ValidationError, match="matching fresh-runtime"):
        _reissue(base, conformance_status="passed", promotion_status="promotable")
    evidence = ConformanceEvidence(
        identity="probe-1", evidence=base.model_artifact.model_copy(
            update={"role": "conformance_evidence"},
        ),
        model_digest=base.model_artifact.digest,
        inference_adapter=base.inference.adapter,
        inference_loader=base.inference.loader,
        inference_version=base.inference.version,
        preparation_contract_digest=base.preparation.feature_contract.digest,
        prepared_x_digest=base.preparation.x.digest,
        prepared_y_digest=base.preparation.y.digest,
        materializer_config_digest=base.preparation.materializer.config_digest,
        runtime_identity="python-3.11-linux", probe_identity="probe-v1",
        verifier_identity="oracle-v1", fresh_runtime=True,
    )
    promoted = _reissue(
        base, limitations=("Validated only for the declared probe envelope.",),
        conformance_status="passed", conformance_evidence=(evidence,),
        promotion_status="promotable",
    )
    assert promoted.promotion_status == "promotable"


def test_rejected_not_run_is_not_a_fabricated_failure(tmp_path: Path) -> None:
    rejected = _reissue(
        passport(tmp_path), promotion_status="rejected",
        rejection_reason="inference_adapter_defect",
    )
    assert rejected.conformance_status == "not_run"
    assert rejected.conformance_evidence == ()


def test_probe_json_boundary_preserves_strict_passport_types(tmp_path: Path) -> None:
    value = passport(tmp_path)
    payload = PassportProbeInput(
        passport=value, snapshot_root=str(tmp_path),
        model_path=str(tmp_path / "model"),
        contract_path=str(tmp_path / "contract.json"),
        prepared_x_path=str(tmp_path / "X.npy"),
        prepared_y_path=str(tmp_path / "y.npy"), nonce="probe-nonce",
    )
    raw = canonical_json(payload.model_dump(mode="json"))
    restored = PassportProbeInput.model_validate_json(raw, strict=True)
    assert restored == payload
    assert isinstance(restored.passport.lineage_artifacts, tuple)
    assert isinstance(restored.passport.limitations, tuple)
    assert isinstance(restored.passport.conformance_evidence, tuple)
    assert isinstance(restored.passport.preparation.contract_shape, tuple)

    document = json.loads(raw)
    document["passport"]["passport_revision"] = "1"
    with pytest.raises(ValidationError, match="int_type"):
        PassportProbeInput.model_validate_json(json.dumps(document), strict=True)
    document = json.loads(raw)
    document["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PassportProbeInput.model_validate_json(json.dumps(document), strict=True)
