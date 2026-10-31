"""Backend-only CAN keystone pipeline orchestration.

Each Dataset stage is submitted and polled independently. The optional context
path executes ingest → augment → correlate; augmentation becomes the synthesis
input corpus while correlation is retained as an analytical sidecar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .can_context_pipeline import sample_corpus_for_synth
from .can_inference_gate import build_inference_gate
from .can_keystone_helpers import train_top_can_ids
from .can_keystone_runner import run_keystone_stage
from .can_keystone_stages import PreparedCanPipeline, prepare_can_training_data
from .can_model_configs import preflight_can_model_configs
from .can_passports import passport_storage_root, resolve_can_passport_context
from .passport_config import passport_training_paths
from .runtime import TrackingRuntime, get_runtime


def run_keystone_pipeline(
    *,
    mf4_dir: str,
    dbc_path: str,
    vehicle_id: str = "unknown",
    storage_root: Path | str | None = None,
    max_samples: int = 20_000,
    top_n_can_ids: int = 5,
    config_overrides: dict[str, dict[str, Any]] | None = None,
    use_context: bool = False,
    context_sources: list[str] | None = None,
    model_types: list[str] | None = None,
    model_configs: dict[str, Any] | None = None,
    runtime: TrackingRuntime | None = None,
) -> dict[str, Any]:
    """Run ingest → profile → [context] → synth → window → augment → train."""
    rt = runtime if runtime is not None else get_runtime()
    chronos_root = rt.chronos_storage_root()
    try:
        requested_models, typed_model_configs = preflight_can_model_configs(
            model_types, model_configs,
            chronos_storage_root=str(chronos_root) if chronos_root else None,
        )
    except (TypeError, ValueError) as exc:
        return {"error": str(exc), "stage": "preflight"}

    root = Path(storage_root) if storage_root else Path(".dataset_store")
    root.mkdir(parents=True, exist_ok=True)
    snapshots = root / "keystone_snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    prepared = prepare_can_training_data(
        mf4_dir=mf4_dir,
        dbc_path=dbc_path,
        vehicle_id=vehicle_id,
        max_samples=max_samples,
        config_overrides=config_overrides or {},
        use_context=use_context,
        context_sources=list(context_sources or []),
        requested_models=requested_models,
        snapshots_dir=snapshots,
        storage_root=root,
        run_stage=run_keystone_stage,
        sample_corpus=sample_corpus_for_synth,
    )
    if isinstance(prepared, dict):
        return prepared

    passport_root, training_snapshots = passport_training_paths(passport_storage_root(rt))
    try:
        passport_context = resolve_can_passport_context(
            prepared.augmented,
            prepared.synth,
            passport_storage_root=passport_root,
            dataset_storage_root=root,
        )
        table, model_ids = train_top_can_ids(
            rt.get_timeseries_trainer(),
            prepared.augmented["dataset_uri"],
            top_n_can_ids,
            vehicle_id,
            training_snapshots,
            model_types=requested_models,
            model_configs=typed_model_configs,
            runtime=rt,
            source_digests=(
                [prepared.augmented["digest"]] if prepared.augmented.get("digest") else []
            ),
            signal_schema_refs=prepared.signal_schema_refs,
            prior_data_policy_ref=prepared.prior_policy_ref,
            passport_context=passport_context,
            require_passport=True,
        )
    except Exception as exc:
        return {
            "error": f"training failed: {exc}", "stage": "train",
            "job_id": prepared.augmented["job_id"],
        }
    return _build_result(vehicle_id, prepared, table, model_ids)


def _build_result(
    vehicle_id: str,
    prepared: PreparedCanPipeline,
    table: list[dict[str, Any]],
    model_ids: list[str],
) -> dict[str, Any]:
    result = {
        "vehicle_id": vehicle_id,
        "ingest": {"job_id": prepared.ingest["job_id"], "n_mf4": len(prepared.mf4_files)},
        "profile": {"job_id": prepared.profile["job_id"]},
        "contract_artifacts": {
            name: {
                "job_id": value["job_id"],
                "uri": value["dataset_uri"],
                "digest": value["digest"],
            }
            for name, value in prepared.contract_artifacts.items()
        },
        "synthesize": {"job_id": prepared.synth["job_id"]},
        "window": {"job_id": prepared.windowed["job_id"]},
        "augment": {"job_id": prepared.augmented["job_id"]},
        "top_can_ids": [row["can_id"] for row in table],
        "comparison_table": table,
        "model_ids": model_ids,
        "warm_model_ids": model_ids,
        "inference_gate": build_inference_gate(table, model_ids),
    }
    if prepared.context_jobs:
        result.update({
            "context": prepared.context_jobs,
            "context_artifacts": prepared.context_artifacts,
        })
    return result


__all__ = ["run_keystone_pipeline"]
