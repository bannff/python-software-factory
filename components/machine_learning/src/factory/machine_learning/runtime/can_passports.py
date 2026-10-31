"""CAN-specific assembly of generic, Dataset-verified model passports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .can_evaluation_contracts import CanAdequacyBinding
from .can_evals_binding import MlEvalsRecordPointer
from .can_lifecycle_refs import CanLegacyBinding
from .can_passport_models import model_bindings
from .model_passport import ModelPassport
from .passport_artifacts import file_artifact_ref
from .passport_codec import create_model_passport
from .passport_refs import (
    AdapterBinding, PassportArtifactRef, PreparationBinding, ScenarioLineageBinding,
)
from .passport_composition import _publish_server_passport
from .passport_config import configured_passport_root
from .passport_store_models import ModelPassportPublication
from .passport_service import ModelPassportService


@dataclass(frozen=True)
class CanPassportContext:
    lineage_artifacts: tuple[PassportArtifactRef, ...]
    scenario_lineage: ScenarioLineageBinding | None
    storage_root: str
    evaluation_pointers: tuple[MlEvalsRecordPointer, ...] = ()
    evaluation_adequacy: tuple[CanAdequacyBinding, ...] = ()
    legacy_binding: CanLegacyBinding | None = None


def passport_storage_root(runtime: Any) -> Path:
    """Resolve the passport trust root owned by the active ML runtime."""
    service = runtime._passport_service
    if service is not None and service.storage_root:
        return Path(service.storage_root)
    return configured_passport_root()


def resolve_can_passport_context(
    training_artifact: dict[str, Any], synthesis_artifact: dict[str, Any],
    *, passport_storage_root: str | Path, dataset_storage_root: str | Path,
) -> CanPassportContext:
    """Revalidate Dataset lineage while retaining the distinct passport root."""
    from .can_keystone_helpers import _get_invoker
    invoker = _get_invoker()
    if invoker is None:
        raise ValueError("tool_invoker unavailable for Dataset passport verification")
    passport_root = str(passport_storage_root)
    dataset_root = str(dataset_storage_root)
    refs: list[PassportArtifactRef] = []
    scenarios: list[ScenarioLineageBinding] = []
    for prefix, artifact in (
        ("training", training_artifact), ("synthesis", synthesis_artifact),
    ):
        required = {"dataset_uri", "manifest_uri", "digest"}
        if not required.issubset(artifact):
            raise ValueError(f"{prefix} Dataset passport context is incomplete")
        result = invoker(
            "dataset_resolve_artifact", dataset_uri=artifact["dataset_uri"],
            storage_root=dataset_root,
        )
        if (
            not isinstance(result, dict)
            or result.get("schema_version") != "v1"
            or result.get("ok") is not True
            or not isinstance(result.get("data"), dict)
        ):
            raise ValueError(f"{prefix} Dataset MCP verification failed: {result}")
        resolved = result["data"]
        if (
            resolved.get("dataset_uri") != artifact["dataset_uri"]
            or resolved.get("manifest_uri") != artifact["manifest_uri"]
            or resolved.get("dataset_digest") != artifact["digest"]
        ):
            raise ValueError(f"{prefix} Dataset manifest disagrees with its artifact")
        refs.extend((
            file_artifact_ref(
                f"{prefix}_dataset", artifact["dataset_uri"], artifact["digest"],
            ),
            file_artifact_ref(f"{prefix}_manifest", artifact["manifest_uri"]),
        ))
        scenario = _scenario_binding(resolved.get("scenario_lineage"))
        if scenario is not None:
            scenarios.append(scenario)
    if scenarios and any(item != scenarios[0] for item in scenarios[1:]):
        raise ValueError("Dataset manifests carry conflicting scenario lineage")
    return CanPassportContext(
        tuple(refs), scenarios[0] if scenarios else None, passport_root,
    )


def issue_can_model_passport(
    *, context: CanPassportContext, job: Any, row: dict[str, Any],
    model_type: str, x_uri: str, y_uri: str, info: dict[str, Any],
    contract_uri: str, contract: Any, service: ModelPassportService | None = None,
) -> tuple[ModelPassport, ModelPassportPublication]:
    """Bind exact prepared/model files and publish immutable revision one."""
    is_lightgbm = model_type == "lightgbm"
    x_shape = (
        (int(info["n_samples"]), int(info["window_size"]) * int(info["n_features"]))
        if is_lightgbm else (
            int(info["n_samples"]), int(info["window_size"]), int(info["n_features"]),
        )
    )
    architecture, inference, model_artifact, candidate = model_bindings(
        model_type, job, context.storage_root,
    )
    timespans = None
    timespans_shape = None
    if model_type == "lnn":
        timespans_uri = info.get("timespans_uri")
        if not timespans_uri:
            raise ValueError("LNN passport requires the exact prepared timespans artifact")
        timespans = file_artifact_ref("prepared_timespans", timespans_uri)
        timespans_shape = (int(info["n_samples"]), int(info["window_size"]))
        from .adapters.lnn_native import timing_artifact
        _, timing_scale, timing_digest = timing_artifact(timespans_uri, timespans_shape)
        if (
            architecture.config.get("timing_digest") != timespans.digest
            or timing_digest != timespans.digest
            or architecture.config.get("timing_scale") != timing_scale
        ):
            raise ValueError("LNN checkpoint and timespans contract disagree")
    materializer = AdapterBinding(
        adapter="can_materializer", version=str(contract.version),
        config_digest=contract.digest,
    )
    preparation = PreparationBinding(
        x=file_artifact_ref("prepared_x", x_uri),
        y=file_artifact_ref("prepared_y", y_uri),
        feature_contract=file_artifact_ref("feature_contract", contract_uri),
        x_layout="flat_2d" if is_lightgbm else "time_features_3d",
        x_shape=x_shape, y_shape=(int(info["n_samples"]),),
        contract_shape=tuple(contract.required_shape),
        contract_width=int(contract.required_width), materializer=materializer,
        timespans=timespans, timespans_shape=timespans_shape,
    )
    promotion = "candidate" if candidate else "rejected"
    limitations = (
        (
            "Fresh-runtime conformance has not been run.",
            "Pooled Chronos-2 CAN classifier probe; not a forecasting model.",
        )
        if model_type == "chronos" and candidate else
        (("Fresh-runtime conformance has not been run.",)
         if candidate else ("Native inference adapter is unavailable.",))
    )
    passport = create_model_passport(
        model_id=str(job.id), model_version=str(row.get("model_version", "1")),
        passport_revision=1, predecessor=None,
        lineage_artifacts=context.lineage_artifacts,
        scenario_lineage=context.scenario_lineage,
        evaluation_pointers=context.evaluation_pointers,
        evaluation_adequacy=context.evaluation_adequacy,
        can_legacy_binding=context.legacy_binding, lineage_revalidated=True,
        preparation=preparation, architecture=architecture,
        model_artifact=model_artifact,
        final_metrics=_metrics(row.get("metrics") or {}), limitations=limitations,
        inference=inference, conformance_status="not_run", conformance_evidence=(),
        promotion_status=promotion,
        rejection_reason=None if candidate else "inference_adapter_defect",
    )
    return passport, _publish_server_passport(
        passport, storage_root=context.storage_root, service=service,
    )


def _scenario_binding(value: Any) -> ScenarioLineageBinding | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("scenario_pack"), dict):
        raise ValueError("Dataset scenario_lineage is malformed")
    pack = value["scenario_pack"]
    return ScenarioLineageBinding(
        identity=pack["identity"], version=pack["version"], uri=pack["uri"],
        digest=pack["digest"], generator_adapter=value["generator_adapter"],
        generator_version=value["generator_version"], seed=value["seed"],
    )

def _metrics(values: dict[str, Any]) -> dict[str, float]:
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values.values()
    ):
        raise ValueError("final metrics must be numeric")
    return {str(key): float(value) for key, value in values.items()}

__all__ = [
    "CanPassportContext", "file_artifact_ref", "issue_can_model_passport",
    "passport_storage_root", "resolve_can_passport_context",
]
