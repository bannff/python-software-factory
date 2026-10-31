"""Artifact-map and compact CAN artifact helpers for the terminal."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .can_artifact_codec import (
    load_prior_policy, load_signal_schema, ref_from_prior_policy_uri,
    ref_from_signal_schema_uri,
)
from .can_terminal_canonical import canonical_json
from .atomic_io import read_bytes_no_follow
from .can_terminal_paths import checked_output_path
from .recipe import path_from_uri

DEFAULT_PRIOR_CONTEXT = [
    "aggressiveness_score", "battery_health_pct", "humidity_pct", "lat", "lon",
    "odometer_km", "precipitation_mm", "temp_c",
]


def load_profile(uri: str) -> tuple[dict[str, Any], str]:
    raw = read_bytes_no_follow(path_from_uri(uri))
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("CAN profile must contain exactly one object")
    can_ids = records[0].get("can_ids")
    if not isinstance(can_ids, dict) or not can_ids:
        raise ValueError("CAN profile contains no CAN-IDs")
    return records[0], hashlib.sha256(raw).hexdigest()


def load_contract_refs(
    contract_stages: dict[str, dict[str, Any]],
) -> tuple[Any, dict[str, Any], Any, dict[str, Any]]:
    policy_stage = contract_stages["prior_data_policy"]
    policy_ref = ref_from_prior_policy_uri(policy_stage["dataset_uri"])
    policy = load_prior_policy(policy_ref)
    schemas, schema_refs = {}, {}
    for role, stage in sorted(contract_stages.items()):
        if not role.startswith("signal_schema:"):
            continue
        can_id = role.split(":", 1)[1]
        ref = ref_from_signal_schema_uri(stage["dataset_uri"])
        schema = load_signal_schema(ref)
        if schema.can_id != can_id:
            raise ValueError("signal schema role disagrees with artifact")
        schemas[can_id], schema_refs[can_id] = schema, ref
    return policy, schemas, policy_ref, schema_refs


def stage_artifacts(
    stages: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for role, stage in sorted(stages.items()):
        for kind, key in (("dataset", "dataset_uri"), ("manifest", "manifest_uri")):
            uri = stage[key]
            content = read_bytes_no_follow(path_from_uri(uri))
            digest = hashlib.sha256(content).hexdigest()
            artifacts[f"{role}:{kind}"] = {
                "uri": uri, "sha256": digest, "evidence": {"sha256": digest},
            }
        dataset = path_from_uri(stage["dataset_uri"])
        reference = dataset.with_suffix(".ref.json")
        content = read_bytes_no_follow(reference)
        digest = hashlib.sha256(content).hexdigest()
        artifacts[f"{role}:reference"] = {
            "uri": reference.resolve().as_uri(), "sha256": digest,
            "evidence": {"sha256": digest},
        }
    return artifacts


def publish_sample(
    records: list[dict[str, Any]], root: Path, vehicle_id: str,
) -> tuple[str, dict[str, Any]]:
    content = b"".join(canonical_json(item) + b"\n" for item in records)
    digest = hashlib.sha256(content).hexdigest()
    path = checked_output_path(
        root, root / "can_terminal" / "samples" / f"{_safe(vehicle_id)}-{digest}.jsonl",
    )
    from .atomic_io import atomic_write_immutable
    atomic_write_immutable(path, content)
    artifact = {
        "uri": path.resolve().as_uri(), "sha256": digest,
        "evidence": {"sha256": digest},
    }
    return path.resolve().as_uri(), artifact


def bind_training_refs(
    bundle: dict[str, Any], artifacts: dict[str, dict[str, Any]],
    vehicle_id: str, context_roles: dict[str, str],
) -> None:
    """Add direct immutable references while retaining compact legacy keys."""
    bundle.update({
        "vehicle_id": vehicle_id,
        "augmented_dataset": artifacts["augment:dataset"],
        "augmented_manifest": artifacts["augment:manifest"],
        "context_refs": {
            role: artifacts[f"{role}:dataset"] for role in sorted(context_roles)
        },
        "training_artifacts_by_can_id": {
            can_id: {
                name.removesuffix("_artifact"): artifacts[key]
                for name, key in prepared.items() if name.endswith("_artifact") and key
            }
            for can_id, prepared in bundle["prepared_by_can_id"].items()
        },
    })


def build_terminal(
    *, request, canonical, stages, contracts, bundle, artifacts,
    context_jobs, context_uris,
) -> dict[str, Any]:
    """Assemble terminal output plus exact legacy Dataset-stage projection."""
    legacy = {
        "ingest": {"job_id": stages["ingest"]["job_id"],
                   "n_mf4": len(canonical.mf4_paths)},
        "profile": {"job_id": stages["profile"]["job_id"]},
        "contract_artifacts": {name: {
            "job_id": item["job_id"], "uri": item["dataset_uri"],
            "digest": item["digest"],
        } for name, item in sorted(contracts.items())},
        "synthesize": {"job_id": stages["synthesize"]["job_id"]},
        "window": {"job_id": stages["window"]["job_id"]},
        "augment": {"job_id": stages["augment"]["job_id"]},
        "top_can_ids": bundle["top_can_ids"],
    }
    if context_jobs:
        legacy.update({"context": context_jobs, "context_artifacts": context_uris})
    value = {
        "schema_version": "1.0", "status": "completed",
        "attempt_id": request.attempt_id,
        "request_sha256": canonical.request_sha256,
        "vehicle_id": request.vehicle_id,
        "artifacts": dict(sorted(artifacts.items())),
        "artifact_map": _artifact_map(stages, artifacts),
        "stage_receipts": dict(sorted(stages.items())),
        "training_bundle": bundle,
        "legacy_projection": legacy,
        **legacy,
    }
    payload = getattr(canonical, "payload", {})
    if isinstance(payload.get("dbc_selection"), dict):
        value["dbc_selection"] = dict(payload["dbc_selection"])
    definition = getattr(canonical, "dbc_definition", None)
    if definition is not None:
        value["dbc_definition"] = {
            "definition_id": definition.definition_id,
            "catalog_id": definition.catalog_id, "version": definition.version,
            "digest": definition.digest,
            "provenance": definition.provenance.model_dump(mode="json"),
        }
    refs = getattr(request, "failure_pattern_refs", ())
    if refs:
        value["failure_pattern_refs"] = [item.model_dump(mode="json") for item in refs]
    return value


def _artifact_map(
    stages: dict[str, dict[str, Any]], artifacts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        role: {
            "job_id": stage["job_id"],
            "dataset_ref": artifacts[f"{role}:dataset"],
            "manifest_ref": artifacts[f"{role}:manifest"],
            "contract_ref": artifacts[f"{role}:reference"],
        }
        for role, stage in sorted(stages.items())
    }


def _safe(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


__all__ = [
    "DEFAULT_PRIOR_CONTEXT", "bind_training_refs", "build_terminal",
    "load_contract_refs", "load_profile", "publish_sample", "stage_artifacts",
]
