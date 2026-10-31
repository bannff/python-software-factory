"""Re-derive trusted conformance evidence from a sealed probe artifact."""
from __future__ import annotations

import os
from typing import Any

from .adapters.sealed_probe_store import SealedProbeStore
from .model_passport import ConformanceEvidence, ModelPassport
from .passport_native_contract import native_conformance_identity
from .passport_refs import PassportArtifactRef


def derive_conformance_evidence(
    *, candidate: ModelPassport, nonce: str, artifact: PassportArtifactRef,
    store: SealedProbeStore, evaluation_pointers: tuple[Any, ...],
    reject_current_pid: bool,
) -> ConformanceEvidence:
    """Validate sealed child bytes and rebuild every candidate-bound field."""
    result = store.read(artifact)
    if (
        result.parent_nonce != nonce
        or result.passport_digest != candidate.passport_digest
        or result.model_digest != candidate.model_artifact.digest
        or (reject_current_pid and result.child_pid == os.getpid())
    ):
        raise ValueError("sealed CAN model probe is not bound to the candidate")
    if tuple(evaluation_pointers) != candidate.evaluation_pointers:
        raise ValueError("sealed evidence changes exact Evals pointer bindings")
    family, verifier = native_conformance_identity(candidate.inference.loader)
    return ConformanceEvidence(
        identity=f"{family}-isolated-{nonce}", evidence=artifact,
        evaluation_pointers=candidate.evaluation_pointers,
        model_digest=candidate.model_artifact.digest,
        inference_adapter=candidate.inference.adapter,
        inference_loader=candidate.inference.loader,
        inference_version=candidate.inference.version,
        preparation_contract_digest=candidate.preparation.feature_contract.digest,
        prepared_x_digest=candidate.preparation.x.digest,
        prepared_y_digest=candidate.preparation.y.digest,
        materializer_config_digest=candidate.preparation.materializer.config_digest,
        prepared_timespans_digest=(
            candidate.preparation.timespans.digest
            if candidate.preparation.timespans is not None else None
        ),
        runtime_identity=f"python-{result.python}",
        probe_identity=f"native-{family}-v1:{result.probe_output_digest}",
        verifier_identity=verifier, fresh_runtime=True,
    )


__all__ = ["derive_conformance_evidence"]
