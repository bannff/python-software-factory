"""Dataset-stage preparation for the backend CAN keystone pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .can_artifact_refs import CanDatasetArtifactRef
from .can_context_pipeline import run_context_chain
from .can_keystone_artifacts import issue_can_artifacts, load_can_profile
from .can_keystone_helpers import collect_mf4_files, uri_to_path
from .ports import TimeSeriesModelType

_RECIPE_URIS = {
    "ingest": "recipe://local/can-ingest@1",
    "profile": "recipe://local/can-profile@1",
    "synthesize": "recipe://local/can-synthesize@1",
    "window": "recipe://local/can-window@2",
    "augment": "recipe://local/can-augment@1",
}


@dataclass(frozen=True)
class PreparedCanPipeline:
    """Artifacts required by the training and response-assembly phases."""

    mf4_files: list[str]
    ingest: dict[str, Any]
    profile: dict[str, Any]
    synth: dict[str, Any]
    windowed: dict[str, Any]
    augmented: dict[str, Any]
    contract_artifacts: dict[str, dict[str, Any]]
    signal_schema_refs: dict[str, CanDatasetArtifactRef]
    prior_policy_ref: CanDatasetArtifactRef
    context_jobs: dict[str, str]
    context_artifacts: dict[str, str]


def prepare_can_training_data(
    *,
    mf4_dir: str,
    dbc_path: str,
    vehicle_id: str,
    max_samples: int,
    config_overrides: dict[str, dict[str, Any]],
    use_context: bool,
    context_sources: list[str],
    requested_models: list[TimeSeriesModelType],
    snapshots_dir: Path,
    storage_root: Path,
    run_stage: Callable[..., dict[str, Any]],
    sample_corpus: Callable[..., dict[str, Any]],
) -> PreparedCanPipeline | dict[str, Any]:
    """Run and validate Dataset stages through the augmented training corpus."""
    mf4_files = collect_mf4_files(mf4_dir)
    if not mf4_files:
        return {"error": f"no MF4 files under {mf4_dir}"}
    if not Path(dbc_path).exists():
        return {"error": f"dbc_path not found: {dbc_path}"}

    def stage_config(name: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        return {**(defaults or {}), **dict(config_overrides.get(name) or {})}

    base_context = {"dbc_path": str(dbc_path), "vehicle_id": vehicle_id}
    ingest = run_stage(
        "ingest", _RECIPE_URIS["ingest"], mf4_files,
        stage_config("ingest", base_context), snapshots_dir, storage_root,
        f"keystone:{vehicle_id}:ingest",
    )
    if "error" in ingest:
        return {"error": ingest["error"], "stage": "ingest", "job_id": ingest.get("job_id")}

    profile = run_stage(
        "profile", _RECIPE_URIS["profile"], [ingest["dataset_uri"]],
        stage_config("profile"), snapshots_dir, storage_root,
        f"keystone:{vehicle_id}:profile",
    )
    if "error" in profile:
        return {"error": profile["error"], "stage": "profile", "job_id": profile.get("job_id")}
    try:
        profile_schema, _ = load_can_profile(profile["dataset_uri"])
    except ValueError as exc:
        return {
            "error": f"profile artifact invalid: {exc}", "stage": "profile",
            "job_id": profile.get("job_id"), "dataset_uri": profile.get("dataset_uri"),
        }

    synth_source_uri = ingest["dataset_uri"]
    context_jobs: dict[str, str] = {}
    context_artifacts: dict[str, str] = {}
    if use_context:
        context_result = run_context_chain(
            ingest_dataset_uri=ingest["dataset_uri"],
            context_sources=context_sources,
            config_overrides=config_overrides,
            vehicle_id=vehicle_id,
            snaps=snapshots_dir,
            root=storage_root,
            run_stage=run_stage,
        )
        if "error" in context_result:
            return context_result
        synth_source_uri = context_result["dataset_uri"]
        context_jobs = context_result["jobs"]
        context_artifacts = context_result["artifacts"]

    sampled = sample_corpus(synth_source_uri, max_samples, vehicle_id, snapshots_dir)
    if "error" in sampled:
        return {
            "error": sampled["error"], "stage": "synthesize",
            "dataset_uri": sampled["dataset_uri"],
        }
    synth = run_stage(
        "synthesize", _RECIPE_URIS["synthesize"], [sampled["sampled_uri"]],
        stage_config("synthesize", {
            "vehicle_id": vehicle_id, "constraint_schema": profile_schema,
        }),
        snapshots_dir, storage_root, f"keystone:{vehicle_id}:synthesize",
    )
    if "error" in synth:
        return {"error": synth["error"], "stage": "synthesize", "job_id": synth.get("job_id")}

    context_columns = (
        list((config_overrides.get("context_augment") or {}).get("context_fields") or [])
        if use_context else []
    )
    try:
        contract_artifacts, signal_schema_refs, prior_policy_ref = issue_can_artifacts(
            profile_uri=profile["dataset_uri"], use_context=use_context,
            context_columns=context_columns, vehicle_id=vehicle_id,
            snaps=snapshots_dir, root=storage_root, run_stage=run_stage,
        )
    except Exception as exc:
        return {"error": str(exc), "stage": "contract_artifacts"}

    schema_items = sorted(signal_schema_refs.items())
    windowed = run_stage(
        "window", _RECIPE_URIS["window"], [
            synth["dataset_uri"], prior_policy_ref.uri,
            *[ref.uri for _, ref in schema_items],
        ],
        stage_config("window", {
            "window_size_ms": 5000, "step_size_ms": 5000,
            "grid_resolution_ms": 10, "observation_cutoff_ms": 5000,
            "label_horizon_ms": 1000,
            "emit_timespans": TimeSeriesModelType.lnn in requested_models,
        }),
        snapshots_dir, storage_root, f"keystone:{vehicle_id}:window",
        input_roles=[
            "primary_dataset", "prior_data_policy",
            *[f"signal_schema:{can_id}" for can_id, _ in schema_items],
        ],
    )
    if "error" in windowed:
        return {"error": windowed["error"], "stage": "window", "job_id": windowed.get("job_id")}

    augmented = run_stage(
        "augment", _RECIPE_URIS["augment"], [windowed["dataset_uri"]],
        stage_config("augment"), snapshots_dir, storage_root,
        f"keystone:{vehicle_id}:augment",
    )
    if "error" in augmented:
        return {"error": augmented["error"], "stage": "augment", "job_id": augmented.get("job_id")}
    augment_path = uri_to_path(augmented["dataset_uri"])
    if augment_path is None or not augment_path.exists() or augment_path.stat().st_size == 0:
        return {
            "error": "augment artifact is missing or empty", "stage": "train",
            "job_id": augmented["job_id"], "dataset_uri": augmented["dataset_uri"],
        }

    return PreparedCanPipeline(
        mf4_files=mf4_files, ingest=ingest, profile=profile, synth=synth,
        windowed=windowed, augmented=augmented,
        contract_artifacts=contract_artifacts,
        signal_schema_refs=signal_schema_refs, prior_policy_ref=prior_policy_ref,
        context_jobs=context_jobs, context_artifacts=context_artifacts,
    )


__all__ = ["PreparedCanPipeline", "prepare_can_training_data"]
