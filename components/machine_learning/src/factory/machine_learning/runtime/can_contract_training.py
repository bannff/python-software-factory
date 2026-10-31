"""Per-CAN contract creation, training, and truthful inference gating."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .adapters.jsonl_to_npy import convert_records_to_npy, load_jsonl_windows
from .can_artifact_refs import CanDatasetArtifactRef, load_prior_policy, load_signal_schema
from .can_feature_contract import create_can_feature_contract, save_can_feature_contract
from .can_keystone_dataset_payload import uri_to_path
from .can_keystone_training import _pick_x_uri, _train_one, resolve_model_types
from .can_passports import CanPassportContext, issue_can_model_passport
from .passport_trees import local_model_artifact_digest
from .ports import TimeSeriesModelConfig, TimeSeriesModelType

_EXCLUDED_FIELDS = (
    "correlation", "correlation_heatmap", "failure_mode", "failure_strategy",
    "failure_timestamp_ns", "is_failure", "label", "provenance",
    "source_lineage", "synthetic_lineage", "target", "timestamp_ns",
)

def train_can_contracts(
    *, trainer: Any, runtime: Any, augmented_uri: str, top_n: int,
    vehicle_id: str, snapshots_dir: Path,
    model_types: list[TimeSeriesModelType] | list[str] | None,
    source_digests: list[str],
    signal_schema_refs: dict[str, CanDatasetArtifactRef],
    prior_data_policy_ref: CanDatasetArtifactRef,
    passport_context: CanPassportContext | None = None, require_passport: bool = False,
    model_configs: dict[TimeSeriesModelType, TimeSeriesModelConfig | None] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Train competitors; passport promotion is the sole deployability truth."""
    if require_passport and passport_context is None:
        raise ValueError("required model-passport context is absent")
    records = load_jsonl_windows(uri_to_path(augmented_uri) or Path(augmented_uri))
    policy = load_prior_policy(prior_data_policy_ref)
    top_ids = [can_id for can_id, _ in Counter(
        str(record.get("arbitration_id", record.get("can_id", "unknown")))
        for record in records
    ).most_common(top_n)]
    missing = sorted(set(top_ids) - set(signal_schema_refs))
    if missing:
        raise ValueError(f"signal schema refs missing CAN-IDs: {missing}")
    requested = resolve_model_types(model_types)
    output = snapshots_dir / "npy" / vehicle_id
    output.mkdir(parents=True, exist_ok=True)
    table: list[dict[str, Any]] = []
    warm_model_ids: list[str] = []
    for rank, can_id in enumerate(top_ids, start=1):
        subset = [record for record in records if str(
            record.get("arbitration_id", record.get("can_id"))
        ) == can_id]
        if not subset:
            continue
        schema_ref = signal_schema_refs[can_id]
        schema = load_signal_schema(schema_ref)
        contract = _contract(
            subset, can_id, source_digests, schema.columns_for(can_id),
            policy.columns, schema_ref, prior_data_policy_ref,
        )
        prefix = f"can{rank}_{can_id.replace('0x', '').replace(' ', '_')}"
        contract_path = output / "contracts" / f"{prefix}-{contract.digest}.json"
        contract_uri = save_can_feature_contract(contract, contract_path)
        _, y_uri, info = convert_records_to_npy(
            subset, output, prefix=prefix, layout="2d", contract=contract,
            max_features=len(contract.ordered_columns),
        )
        for model_type in requested:
            job, row = _train_one(
                trainer, model_type, info["x_2d_uri"], y_uri, info,
                f"keystone-{vehicle_id}", vehicle_id,
                model_config=(model_configs or {}).get(model_type),
            )
            if job is None or row is None or not job.model_path:
                table.append({
                    "rank": rank, "can_id": can_id, "model_type": model_type.value,
                    "n_windows": info["n_samples"], "n_features": info["n_features"],
                    "window_size": info["window_size"], "label_dist": info["label_dist"],
                    "metrics": {}, "registration_status": "failed",
                    "inference_registered": False, "inference_gate": "failed",
                    "error_code": "training_failed",
                    "error": f"requested {model_type.value} training produced no artifact",
                })
                continue
            is_warm = model_type is TimeSeriesModelType.lightgbm
            is_candidate = model_type.value in {
                "lightgbm", "lstm", "tcn", "patchtst", "lnn", "chronos",
            }
            model_digest = ""
            passport = None
            publication = None
            failure_code = "training_failed"
            try:
                model_digest = local_model_artifact_digest(job.model_path)
                if passport_context is not None:
                    failure_code = "passport_publication_failed"
                    passport, publication = issue_can_model_passport(
                        context=passport_context, job=job, row=row,
                        model_type=model_type.value,
                        x_uri=_pick_x_uri(model_type, info), y_uri=y_uri, info=info,
                        contract_uri=contract_uri, contract=contract,
                    )
                if is_warm:
                    failure_code = (
                        "warm_registration_failed" if passport_context is not None
                        else "training_failed"
                    )
                    runtime.register_inference_model(
                        job.id, job.model_path, can_id=can_id,
                        contract_uri=contract_uri, contract_digest=contract.digest,
                        model_type="lightgbm", loader_id="mlflow.lightgbm",
                        model_digest=model_digest, required_shape=contract.required_shape,
                        required_width=contract.required_width,
                        passport_ref=(
                            publication.ref.model_dump(mode="json")
                            if publication is not None else None
                        ),
                        passport_root=(
                            passport_context.storage_root
                            if publication is not None and passport_context is not None
                            else str(Path(job.model_path).parent)
                        ),
                        prepared_x_digest=(passport.preparation.x.digest if passport else None),
                        prepared_y_digest=(passport.preparation.y.digest if passport else None),
                        materializer_config_digest=(
                            passport.preparation.materializer.config_digest
                            if passport else None
                        ),
                        inference_adapter=(passport.inference.adapter if passport else None),
                        inference_version=(passport.inference.version if passport else None),
                    )
            except Exception as exc:
                row.update({
                    "rank": rank, "can_id": can_id, "contract_uri": contract_uri,
                    "contract_digest": contract.digest, "model_digest": model_digest or None,
                    "registration_status": "failed", "inference_registered": False,
                    "inference_gate": "failed", "passport_ref": None,
                    "passport_digest": None, "passport_revision": None,
                    "passport_status": "unpassported", "promotion_status": None,
                    "conformance_status": None,
                    "error_code": failure_code,
                    "error": f"model artifact, passport, or warm registration failed: {exc}",
                })
                table.append(row)
                continue
            if is_warm:
                warm_model_ids.append(job.id)
            promotion = "candidate" if is_candidate else "rejected"
            row.update({
                "rank": rank, "can_id": can_id, "contract_uri": contract_uri,
                "contract_digest": contract.digest, "model_digest": model_digest,
                "registration_status": (
                    "warm" if is_warm else "candidate" if is_candidate else "rejected"
                ),
                "inference_registered": is_warm, "inference_gate": "failed",
                "passport_ref": (
                    publication.ref.model_dump(mode="json") if publication else None
                ),
                "passport_digest": passport.passport_digest if passport else None,
                "passport_revision": passport.passport_revision if passport else None,
                "passport_status": publication.status if publication else "not_published",
                "promotion_status": promotion, "conformance_status": "not_run",
            })
            if not is_candidate:
                row.update({
                    "error_code": "inference_adapter_defect",
                    "error": f"native inference adapter unavailable for {model_type.value}",
                })
            table.append(row)
    table.sort(key=lambda row: row["metrics"].get("auroc", 0.0), reverse=True)
    return table, warm_model_ids

def _contract(
    records: list[dict[str, Any]], can_id: str, source_digests: list[str],
    signal_columns: tuple[str, ...], context_columns: tuple[str, ...],
    signal_schema_ref: CanDatasetArtifactRef,
    prior_data_policy_ref: CanDatasetArtifactRef,
):
    first = records[0]
    if tuple((first.get("signal") or {}).get("columns") or ()) != signal_columns:
        raise ValueError(f"window signal projection disagrees for CAN-ID {can_id}")
    if tuple((first.get("context") or {}).get("columns") or ()) != context_columns:
        raise ValueError("window context projection disagrees with Dataset policy")
    return create_can_feature_contract(
        can_id=can_id, signal_schema_ref=signal_schema_ref,
        prior_data_policy_ref=prior_data_policy_ref,
        signal_columns=signal_columns, context_columns=context_columns,
        window_size_ms=int(first["window_size_ms"]),
        step_size_ms=int(first["step_size_ms"]),
        grid_resolution_ms=int(first["grid_resolution_ms"]),
        observation_cutoff_ms=int(first["observation_cutoff_ms"]),
        label_horizon_ms=int(first["label_horizon_ms"]),
        num_timesteps=int(first["num_timesteps"]), excluded_fields=_EXCLUDED_FIELDS,
        source_digests=[*source_digests, signal_schema_ref.digest,
                        prior_data_policy_ref.digest],
    )

__all__ = ["train_can_contracts"]
