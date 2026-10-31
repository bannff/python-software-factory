"""Fresh sealed-probe authority for lifecycle conformance and promotion."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from factory.machine_learning.runtime.adapters.passport_conformance import (
    LocalCanModelConformanceRunner,
)
from factory.machine_learning.runtime.adapters.sealed_probe_store import SealedProbeStore
from factory.machine_learning.runtime.passport_evidence import derive_conformance_evidence
from factory.machine_learning.runtime.passport_probe_contracts import PassportProbeResult
from factory.machine_learning.runtime.passport_service import ModelPassportService
from factory.machine_learning.runtime.passport_store_models import (
    ModelPassportPublication, ModelPassportRef,
)
from factory.machine_learning.runtime.passport_validation import canonical_json

from .passport_fixtures import passport


def _candidate(root: Path, model_id="model-1"):
    return passport(root, model_id=model_id, inference={
        "adapter": "can_inference", "loader": "mlflow.lightgbm", "version": "1",
    })


def _ref(candidate, root: Path):
    return ModelPassportRef(
        model_id=candidate.model_id, model_version=candidate.model_version,
        passport_revision=1, uri=(root / f"{candidate.model_id}.json").as_uri(),
        digest=candidate.passport_digest,
    )


def _probe(candidate, nonce: str):
    return PassportProbeResult(
        child_pid=max(os.getpid() + 1000, 99999), parent_nonce=nonce,
        passport_digest=candidate.passport_digest,
        model_digest=candidate.model_artifact.digest, probe_rows=4, probe_width=6,
        probe_input_digest="a" * 64, probe_output_digest="b" * 64,
        predictions_digest="c" * 64, python="3.13-test",
    )


def test_precreated_canonical_content_addressed_forgery_cannot_skip_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    candidate = _candidate(tmp_path)
    ref, nonce = _ref(candidate, tmp_path), "e" * 64
    runner = LocalCanModelConformanceRunner(tmp_path)
    forged = _probe(candidate, nonce)
    raw = canonical_json(forged.model_dump(mode="json"))
    digest = hashlib.sha256(raw).hexdigest()
    objects = tmp_path / "conformance_evidence" / "objects"
    attacker = objects / f"{digest}.json"
    attacker.write_bytes(raw)
    attacker.chmod(0o400)
    legacy = tmp_path / "conformance_evidence" / candidate.passport_digest
    legacy.mkdir()
    (legacy / f"{nonce}.json").write_bytes(raw)
    calls = []
    monkeypatch.setattr(runner, "_execute", lambda payload: calls.append(payload) or forged)
    evidence = runner.run(candidate, ref, effect_id=nonce)
    assert len(calls) == 1
    assert evidence.evidence.digest == digest
    assert evidence.evidence.uri == attacker.as_uri()


class _Store:
    def __init__(self, values):
        self.values, self.published = values, []

    def get(self, ref):
        return self.values[ref.model_id]

    def get_by_model(self, *_args):
        raise KeyError("missing")

    def publish(self, value):
        self.published.append(value)
        return ModelPassportPublication(status="published", ref=ModelPassportRef(
            model_id=value.model_id, model_version=value.model_version,
            passport_revision=value.passport_revision,
            uri=(Path(value.model_artifact.uri.removeprefix("file://")).parent
                 / f"promoted-{value.model_id}.json").as_uri(),
            digest=value.passport_digest,
        ))


class _Runner:
    def __init__(self): self.calls = 0
    def run(self, *_args, **_kwargs): self.calls += 1; raise AssertionError("no probe")


class _Verifier:
    def verify(self, _value): pass


def _sealed(candidate, root: Path, nonce: str):
    store = SealedProbeStore(root)
    try:
        artifact = store.publish(_probe(candidate, nonce))
        evidence = derive_conformance_evidence(
            candidate=candidate, nonce=nonce, artifact=artifact, store=store,
            evaluation_pointers=candidate.evaluation_pointers,
            reject_current_pid=False,
        )
    finally:
        store.close()
    return artifact, evidence


@pytest.mark.parametrize("attack", ["field", "artifact", "cross-candidate"])
def test_lifecycle_promotion_rejects_forgery_without_probe_or_publish(
    tmp_path: Path, attack: str,
):
    one_root, two_root = tmp_path / "one", tmp_path / "two"
    one_root.mkdir(); two_root.mkdir()
    one, two = _candidate(one_root), _candidate(two_root, "model-2")
    ref_one, ref_two, nonce = _ref(one, one_root), _ref(two, two_root), "f" * 64
    artifact, evidence = _sealed(one, tmp_path, nonce)
    receipt = evidence.model_dump(mode="json")
    selected = ref_one
    if attack == "field":
        receipt["runtime_identity"] = "python-forged"
    elif attack == "artifact":
        path = Path(artifact.uri.removeprefix("file://"))
        path.chmod(0o600); path.write_bytes(b"tampered")
    else:
        selected = ref_two
    backing, runner = _Store({one.model_id: one, two.model_id: two}), _Runner()
    service = ModelPassportService(
        store=backing, verifier=_Verifier(), conformance_runner=runner,
        storage_root=str(tmp_path),
    )
    with pytest.raises(ValueError):
        selected_candidate = one if selected == ref_one else two
        service.promote_lifecycle(
            selected, receipt, effect_id=nonce,
            evaluation_pointers=selected_candidate.evaluation_pointers,
            evaluation_adequacy=selected_candidate.evaluation_adequacy,
        )
    assert backing.published == []
    assert runner.calls == 0


def test_valid_lifecycle_promotion_rederives_evidence_without_probe(tmp_path: Path):
    candidate = _candidate(tmp_path)
    ref, nonce = _ref(candidate, tmp_path), "1" * 64
    _, evidence = _sealed(candidate, tmp_path, nonce)
    backing, runner = _Store({candidate.model_id: candidate}), _Runner()
    service = ModelPassportService(
        store=backing, verifier=_Verifier(), conformance_runner=runner,
        storage_root=str(tmp_path),
    )
    publication = service.promote_lifecycle(
        ref, evidence.model_dump(mode="json"), effect_id=nonce,
        evaluation_pointers=candidate.evaluation_pointers,
        evaluation_adequacy=candidate.evaluation_adequacy,
    )
    assert publication.ref.passport_revision == 2
    assert len(backing.published) == 1
    assert backing.published[0].conformance_evidence == (evidence,)
    assert runner.calls == 0
