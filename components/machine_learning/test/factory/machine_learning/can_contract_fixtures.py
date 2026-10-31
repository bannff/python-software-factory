"""Canonical Dataset artifact and contract fixtures for CAN ML tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.machine_learning.runtime.can_artifact_refs import (
    CanDatasetArtifactRef, ref_from_uri,
)
from factory.machine_learning.runtime.can_feature_contract import create_can_feature_contract


def _canonical(body: dict) -> bytes:
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()


def write_artifact(tmp_path: Path, name: str, body: dict) -> CanDatasetArtifactRef:
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    artifact = {**body, "digest": digest}
    path = tmp_path / f"{name}.json"
    path.write_bytes(_canonical(artifact))
    return ref_from_uri(path.as_uri())


def refs(tmp_path: Path, *, context: tuple[str, ...] = ()):
    schema = write_artifact(tmp_path, "schema", {
        "version": "1.0", "source_digests": [], "can_id": "0x1",
        "signal_columns": ["a", "b"],
    })
    policy = write_artifact(tmp_path, "policy", {
        "version": "1.0", "source_digests": [], "use_context": bool(context),
        "prior_data_allowlist": list(context),
    })
    return schema, policy


def contract(tmp_path: Path, *, context: tuple[str, ...] = (), **overrides):
    schema, policy = refs(tmp_path, context=context)
    values = {
        "can_id": "0x1", "signal_schema_ref": schema,
        "prior_data_policy_ref": policy, "signal_columns": ("a", "b"),
        "context_columns": context, "window_size_ms": 20, "step_size_ms": 20,
        "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
        "label_horizon_ms": 10, "num_timesteps": 2,
        "source_digests": ["a" * 64], "excluded_fields": ["label"],
    }
    values.update(overrides)
    return create_can_feature_contract(**values)


def window(contract_value, *, label: int = 0) -> dict:
    context_columns = list(contract_value.context_columns)
    return {
        "schema_version": "2.0", "can_id": contract_value.can_id,
        "vehicle_id": "v", "signal": {
            "columns": list(contract_value.signal_columns),
            "values": [[1.0, 2.0], [3.0, 4.0]],
        }, "context": {
            "columns": context_columns,
            "values": [[10.0] * len(context_columns), [11.0] * len(context_columns)],
        }, "provenance": {"source_records": [], "synthetic_lineage": []},
        "bounds": {"window_start_ns": 0, "observation_cutoff_ns": 20_000_000,
                   "label_horizon_end_ns": 30_000_000},
        "label": label, "window_size_ms": 20, "step_size_ms": 20,
        "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
        "label_horizon_ms": 10, "num_timesteps": 2,
        "metadata": {
            "signal_schema_ref": contract_value.signal_schema_ref.model_dump(mode="json"),
            "prior_data_policy_ref": contract_value.prior_data_policy_ref.model_dump(mode="json"),
        },
    }


def install_dataset_invoker(tmp_path: Path, calls: list | None = None):
    """Return a Dataset-tool canary that executes the exact ref-only adapter."""
    from factory.dataset.runtime.adapters.can_window_v2 import CanWindowV2StageAdapter

    artifact = tmp_path / "windows.jsonl"

    def invoker(name: str, **kwargs):
        if calls is not None:
            calls.append((name, kwargs))
        if name == "dataset_submit_generation":
            roles = dict(zip(kwargs["input_artifact_roles"], zip(
                kwargs["input_artifact_uris"], kwargs["input_artifact_digests"], strict=True,
            ), strict=True))
            raw_uri, _ = roles["primary_dataset"]
            policy_uri, _ = roles["prior_data_policy"]
            schema_role = next(role for role in roles if role.startswith("signal_schema:"))
            schema_uri, _ = roles[schema_role]
            payload = json.loads(Path(
                kwargs["context_snapshot_uri"].removeprefix("file://")
            ).read_text())
            config = dict(payload["stage_overrides"]["can_window_v2"])
            config.update({
                "input_uri": raw_uri,
                "prior_data_policy_ref": ref_from_uri(policy_uri).model_dump(mode="json"),
                "signal_schema_refs_by_can_id": {
                    schema_role.split(":", 1)[1]:
                    ref_from_uri(schema_uri).model_dump(mode="json"),
                },
            })
            windows = list(CanWindowV2StageAdapter().execute([], config))
            artifact.write_text("\n".join(json.dumps(item) for item in windows))
            return {"schema_version": "v1", "ok": True, "data": {"job_id": "job"}, "error": None, "idempotency_key": None}
        if name == "dataset_get_job":
            return {"schema_version": "v1", "ok": True, "data": {"status": "completed"}, "error": None, "idempotency_key": None}
        if name == "dataset_get_artifact":
            return {"schema_version": "v1", "ok": True, "data": {"dataset_uri": artifact.as_uri(), "manifest_uri": (tmp_path / "manifest.json").as_uri()}, "error": None, "idempotency_key": None}
        raise AssertionError(name)

    return invoker


__all__ = ["contract", "install_dataset_invoker", "refs", "window", "write_artifact"]
