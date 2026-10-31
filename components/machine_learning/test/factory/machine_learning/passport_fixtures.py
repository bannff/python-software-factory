"""Shared generic ModelPassport fixtures."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from factory.machine_learning.runtime.model_passport import (
    ConformanceEvidence, ModelPassport,
)
from factory.machine_learning.runtime.passport_artifacts import file_artifact_ref
from factory.machine_learning.runtime.passport_codec import create_model_passport
from factory.machine_learning.runtime.passport_refs import (
    AdapterBinding, ArchitectureBinding, InferenceBinding, PassportPredecessorRef,
    PreparationBinding,
)


def passport(tmp_path: Path, **updates: Any) -> ModelPassport:
    artifacts = tmp_path / "passport-inputs"
    artifacts.mkdir(exist_ok=True)
    paths = {}
    dataset_root = tmp_path / "dataset-store"
    manifests = dataset_root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    for prefix in ("training", "synthesis"):
        bundle = dataset_root / "artifacts" / prefix
        bundle.mkdir(parents=True, exist_ok=True)
        dataset = bundle / f"dataset-{prefix}.jsonl"
        dataset.write_bytes(f"{prefix}_dataset-bytes".encode())
        manifest_bytes = f"{prefix}_manifest-bytes".encode()
        manifest = manifests / f"manifest-{hashlib.sha256(manifest_bytes).hexdigest()}.json"
        manifest.write_bytes(manifest_bytes)
        paths[f"{prefix}_dataset"] = dataset
        paths[f"{prefix}_manifest"] = manifest
    for name, suffix in (
        ("prepared_x", ".npy"), ("prepared_y", ".npy"),
        ("feature_contract", ".json"), ("model", ".joblib"),
    ):
        path = artifacts / f"{name}{suffix}"
        if not path.exists():
            path.write_bytes(f"{name}-bytes".encode())
        paths[name] = path
    lineage = tuple(
        file_artifact_ref(role, str(paths[role]))
        for role in (
            "training_dataset", "training_manifest",
            "synthesis_dataset", "synthesis_manifest",
        )
    )
    contract = file_artifact_ref("feature_contract", str(paths["feature_contract"]))
    values: dict[str, Any] = {
        "model_id": "model-1", "model_version": "1", "passport_revision": 1,
        "predecessor": None, "lineage_artifacts": lineage,
        "scenario_lineage": None, "lineage_revalidated": True,
        "preparation": PreparationBinding(
            x=file_artifact_ref("prepared_x", str(paths["prepared_x"])),
            y=file_artifact_ref("prepared_y", str(paths["prepared_y"])),
            feature_contract=contract, x_layout="flat_2d", x_shape=(4, 6),
            y_shape=(4,), contract_shape=(2, 3), contract_width=6,
            materializer=AdapterBinding(
                adapter="materializer", version="1", config_digest=contract.digest,
            ),
        ),
        "architecture": ArchitectureBinding(
            architecture="tree", framework="lightgbm", framework_version="4.6.0",
            config={"seed": 42, "learning_rate": 0.1},
        ),
        "model_artifact": file_artifact_ref("model", str(paths["model"])),
        "final_metrics": {"auroc": 0.8},
        "limitations": ("Fresh-runtime conformance has not been run.",),
        "inference": InferenceBinding(
            adapter="can_inference", loader="joblib", version="1.0",
        ),
        "conformance_status": "not_run", "conformance_evidence": (),
        "promotion_status": "candidate", "rejection_reason": None,
    }
    values.update(updates)
    return create_model_passport(**values)


def promotable_passport(tmp_path: Path, **updates: Any) -> ModelPassport:
    base = passport(tmp_path)
    evidence = ConformanceEvidence(
        identity="probe-1",
        evidence=base.model_artifact.model_copy(update={"role": "conformance_evidence"}),
        model_digest=base.model_artifact.digest,
        inference_adapter=base.inference.adapter,
        inference_loader=base.inference.loader,
        inference_version=base.inference.version,
        preparation_contract_digest=base.preparation.feature_contract.digest,
        prepared_x_digest=base.preparation.x.digest,
        prepared_y_digest=base.preparation.y.digest,
        materializer_config_digest=base.preparation.materializer.config_digest,
        runtime_identity="python-3.11-linux", probe_identity="probe-v1",
        verifier_identity="untrusted-caller", fresh_runtime=True,
    )
    body = base.model_dump(mode="python", exclude={"passport_digest"})
    body.update({
        "limitations": ("Caller-asserted evidence must not establish trust.",),
        "conformance_status": "passed", "conformance_evidence": (evidence,),
        "promotion_status": "promotable",
    })
    body.update(updates)
    return create_model_passport(**body)


def passport_invoker(value: ModelPassport):
    refs = {ref.role: ref for ref in value.lineage_artifacts}

    def invoke(tool_name: str, **kwargs: Any) -> dict[str, Any]:
        if tool_name != "dataset_resolve_artifact":
            raise AssertionError(f"unexpected tool: {tool_name}")
        prefix = "training" if kwargs["dataset_uri"] == refs["training_dataset"].uri else "synthesis"
        return {
            "schema_version": "v1", "ok": True,
            "data": {
                "dataset_uri": refs[f"{prefix}_dataset"].uri,
                "manifest_uri": refs[f"{prefix}_manifest"].uri,
                "dataset_digest": refs[f"{prefix}_dataset"].digest,
                "scenario_lineage": None,
            },
            "error": None, "idempotency_key": None,
        }

    return invoke


def predecessor(ref: Any) -> PassportPredecessorRef:
    return PassportPredecessorRef.model_validate(ref.model_dump())


__all__ = [
    "passport", "passport_invoker", "predecessor", "promotable_passport",
]
