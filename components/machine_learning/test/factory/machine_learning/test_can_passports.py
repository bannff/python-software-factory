"""Dataset-MCP verification and truthful CAN passport issuance."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.machine_learning.runtime.adapters.model_passport_verifier import (
    LocalModelPassportVerifier,
)
from factory.machine_learning.runtime.can_inference_gate import build_inference_gate
from factory.machine_learning.runtime.can_passports import (
    issue_can_model_passport, resolve_can_passport_context,
)
from factory.machine_learning.runtime.passport_composition import (
    create_local_passport_service, get_model_passport_by_model,
)
from factory.machine_learning.runtime.passport_artifacts import file_artifact_ref
from factory.machine_learning.runtime.passport_codec import create_model_passport
from factory.mcp_utils.interface import get_service, set_service

from .passport_fixtures import passport as passport_fixture, passport_invoker


@pytest.fixture(autouse=True)
def restore_invoker():
    previous = get_service("tool_invoker")
    yield
    set_service("tool_invoker", previous)


def _artifact(root: Path, name: str) -> dict:
    bundle = root / "artifacts" / name
    manifests = root / "manifests"
    bundle.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    dataset = bundle / f"dataset-{name}.jsonl"
    dataset.write_text('{"value":1}\n')
    manifest_bytes = f'{{"name":"{name}"}}'.encode()
    manifest = manifests / f"manifest-{hashlib.sha256(manifest_bytes).hexdigest()}.json"
    manifest.write_bytes(manifest_bytes)
    return {
        "dataset_uri": dataset.as_uri(), "manifest_uri": manifest.as_uri(),
        "digest": hashlib.sha256(dataset.read_bytes()).hexdigest(),
    }


def test_dataset_resolution_hashes_manifests_and_extracts_scenario_lineage(
    tmp_path: Path,
) -> None:
    dataset_root, passport_root = tmp_path / "datasets", tmp_path / "passports"
    training = _artifact(dataset_root, "training")
    synthesis = _artifact(dataset_root, "synthesis")
    pack = dataset_root / "pack.json"
    pack.write_text("pack")
    scenario = {
        "scenario_pack": {
            "identity": "pack-1", "version": "1", "uri": pack.as_uri(),
            "digest": hashlib.sha256(pack.read_bytes()).hexdigest(),
        },
        "generator_adapter": "scenario-generator", "generator_version": "1",
        "seed": 42,
    }
    calls = []

    def invoker(tool_name: str, **kwargs):
        calls.append((tool_name, kwargs))
        artifact = training if kwargs["dataset_uri"] == training["dataset_uri"] else synthesis
        return {
            "schema_version": "v1", "ok": True,
            "data": {
                "dataset_uri": artifact["dataset_uri"],
                "manifest_uri": artifact["manifest_uri"],
                "dataset_digest": artifact["digest"], "scenario_lineage": scenario,
            },
            "error": None, "idempotency_key": None,
        }

    set_service("tool_invoker", invoker)
    context = resolve_can_passport_context(
        training, synthesis, passport_storage_root=passport_root,
        dataset_storage_root=dataset_root,
    )
    assert [name for name, _ in calls] == [
        "dataset_resolve_artifact", "dataset_resolve_artifact",
    ]
    assert {kwargs["storage_root"] for _, kwargs in calls} == {str(dataset_root)}
    assert context.storage_root == str(passport_root)
    assert {ref.role for ref in context.lineage_artifacts} == {
        "training_dataset", "training_manifest", "synthesis_dataset", "synthesis_manifest",
    }
    training_manifest = next(
        ref for ref in context.lineage_artifacts if ref.role == "training_manifest"
    )
    assert training_manifest.digest == hashlib.sha256(
        Path(training["manifest_uri"].removeprefix("file://")).read_bytes()
    ).hexdigest()
    assert context.scenario_lineage and context.scenario_lineage.seed == 42


def test_issuance_binds_exact_files_and_candidate_is_not_deployable(tmp_path: Path) -> None:
    dataset_root, passport_root = tmp_path / "datasets", tmp_path / "passports"
    passport_root.mkdir()
    training = _artifact(dataset_root, "training")
    synthesis = _artifact(dataset_root, "synthesis")

    def invoker(_tool_name: str, **kwargs):
        assert kwargs["storage_root"] == str(dataset_root)
        artifact = (
            training if kwargs["dataset_uri"] == training["dataset_uri"] else synthesis
        )
        return {
            "schema_version": "v1", "ok": True,
            "data": {
                "dataset_uri": artifact["dataset_uri"],
                "manifest_uri": artifact["manifest_uri"],
                "dataset_digest": artifact["digest"], "scenario_lineage": None,
            },
            "error": None, "idempotency_key": None,
        }

    set_service("tool_invoker", invoker)
    context = resolve_can_passport_context(
        training, synthesis, passport_storage_root=passport_root,
        dataset_storage_root=dataset_root,
    )
    x, y = passport_root / "X.npy", passport_root / "y.npy"
    contract_path = passport_root / "contract.json"
    for path, content in ((x, b"x"), (y, b"y"), (contract_path, b"contract")):
        path.write_bytes(content)
    model_path = passport_root / "mlflow-model"
    model_path.mkdir()
    (model_path / "MLmodel").write_bytes(b"model")
    contract_digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    contract = SimpleNamespace(
        version="2.0", digest=contract_digest, required_shape=(2, 3), required_width=6,
    )
    job = SimpleNamespace(
        id="job-lightgbm", model_path=str(model_path), config={"seed": 42},
    )
    service = create_local_passport_service(context.storage_root)
    issued = []
    original_issue = service.issue_candidate
    service.issue_candidate = lambda value: issued.append(value) or original_issue(value)
    passport, publication = issue_can_model_passport(
        context=context, job=job, row={"metrics": {"auroc": 0.9}},
        model_type="lightgbm", x_uri=x.as_uri(), y_uri=y.as_uri(),
        info={"n_samples": 4, "window_size": 2, "n_features": 3},
        contract_uri=contract_path.as_uri(), contract=contract, service=service,
    )
    assert issued == [passport]
    assert publication.status == "published"
    assert passport.promotion_status == "candidate"
    assert passport.conformance_status == "not_run"
    assert passport.preparation.x.size_bytes == 1
    assert get_model_passport_by_model(
        "job-lightgbm", "1", 1, service=service,
    ) == passport
    Path(training["dataset_uri"].removeprefix("file://")).write_text("tampered\n")
    with pytest.raises(ValueError, match="reference does not match exact bytes"):
        service.get_by_model("job-lightgbm", "1", 1)
    gate = build_inference_gate([{
        "model_id": "job-lightgbm", "model_type": "lightgbm",
        "passport_ref": publication.ref.model_dump(mode="json"),
        "passport_digest": passport.passport_digest,
        "promotion_status": "candidate", "conformance_status": "not_run",
    }], ["job-lightgbm"])
    assert gate["status"] == "failed"
    assert gate["error_code"] == "passport_not_promotable"
    assert gate["warm_model_ids"] == ["job-lightgbm"]
    assert gate["live_model_ids"] == []


def test_verifier_rejects_dataset_lineage_spanning_roots(tmp_path: Path) -> None:
    value = passport_fixture(tmp_path)
    other = _artifact(tmp_path / "other-dataset", "synthesis")
    replacements = {
        "synthesis_dataset": file_artifact_ref(
            "synthesis_dataset", other["dataset_uri"], other["digest"],
        ),
        "synthesis_manifest": file_artifact_ref(
            "synthesis_manifest", other["manifest_uri"],
        ),
    }
    body = value.model_dump(mode="python", exclude={"passport_digest"})
    body["lineage_artifacts"] = tuple(
        replacements.get(ref.role, ref) for ref in value.lineage_artifacts
    )
    mixed = create_model_passport(**body)
    verifier = LocalModelPassportVerifier(tmp_path, passport_invoker(value))
    with pytest.raises(ValueError, match="spans multiple storage roots"):
        verifier.verify(mixed)
