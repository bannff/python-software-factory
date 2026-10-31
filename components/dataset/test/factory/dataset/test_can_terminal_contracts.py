"""Strict numeric and terminal projection contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.dataset.runtime.can_artifact_codec import (
    artifact_ref, canonical_artifact_bytes, create_prior_policy,
    create_signal_schema,
)
from factory.dataset.runtime.can_terminal_artifacts import build_terminal
from factory.dataset.runtime.can_terminal_prepare import prepare_training_bundle


def _artifact(root: Path, name: str, value):
    path = root / name
    path.write_bytes(canonical_artifact_bytes(value))
    return artifact_ref(path.as_uri(), value.version, value.digest)


def _window(policy_ref, schema_ref):
    return {
        "schema_version": "2.0", "can_id": "0x1",
        "window_size_ms": 20, "step_size_ms": 20,
        "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
        "label_horizon_ms": 10, "num_timesteps": 2,
        "bounds": {
            "window_start_ns": 0, "observation_cutoff_ns": 20_000_000,
            "label_horizon_end_ns": 30_000_000,
        },
        "signal": {"columns": ["rpm"], "values": [[1.0], [2.0]]},
        "context": {"columns": [], "values": [[], []]},
        "label": 1, "timespans": [0.01, 0.01],
        "metadata": {
            "signal_schema_ref": schema_ref.model_dump(mode="json"),
            "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
        },
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("timespans", ["0.01", 0.01], "timespans must be finite positive"),
        ("signal", {"columns": ["rpm"], "values": [[1e40], [2.0]]}, "float32 range"),
    ],
)
def test_prepared_bundle_rejects_lossy_numeric_coercion(
    tmp_path: Path, field: str, value, message: str,
) -> None:
    policy = create_prior_policy(use_context=False, prior_data_allowlist=())
    schema = create_signal_schema(can_id="0x1", signal_columns=("rpm",))
    policy_ref = _artifact(tmp_path, "strict-policy.json", policy)
    schema_ref = _artifact(tmp_path, "strict-schema.json", schema)
    window = _window(policy_ref, schema_ref)
    window[field] = value
    augmented = tmp_path / "strict.jsonl"
    augmented.write_text(json.dumps(window, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match=message):
        prepare_training_bundle(
            augmented_uri=augmented.as_uri(),
            augmented_digest=hashlib.sha256(augmented.read_bytes()).hexdigest(),
            policy=policy, policy_ref=policy_ref, schemas={"0x1": schema},
            schema_refs={"0x1": schema_ref}, root=tmp_path,
            request_sha256="d" * 64,
        )


def test_terminal_exposes_artifact_map_and_exact_legacy_projection() -> None:
    roles = ["ingest", "profile", "synthesize", "window", "augment"]
    stages = {
        role: {
            "job_id": f"job-{role}", "dataset_uri": f"file:///{role}.jsonl",
            "manifest_uri": f"file:///{role}-manifest.json", "digest": "a" * 64,
        }
        for role in roles
    }
    artifacts = {
        f"{role}:{kind}": {
            "uri": f"file:///{role}-{kind}", "sha256": "b" * 64,
            "evidence": {"sha256": "b" * 64},
        }
        for role in roles for kind in ("dataset", "manifest", "reference")
    }
    terminal = build_terminal(
        request=SimpleNamespace(attempt_id="attempt", vehicle_id="vehicle"),
        canonical=SimpleNamespace(request_sha256="c" * 64, mf4_paths=(Path("a"),)),
        stages=stages, contracts={}, bundle={"top_can_ids": ["0x1"]},
        artifacts=artifacts, context_jobs={}, context_uris={},
    )
    assert terminal["legacy_projection"]["ingest"] == terminal["ingest"]
    assert terminal["legacy_projection"]["top_can_ids"] == terminal["top_can_ids"]
    assert terminal["artifact_map"]["ingest"] == {
        "job_id": "job-ingest", "dataset_ref": artifacts["ingest:dataset"],
        "manifest_ref": artifacts["ingest:manifest"],
        "contract_ref": artifacts["ingest:reference"],
    }
    assert all(set(value) == {"uri", "sha256", "evidence"}
               for value in terminal["artifacts"].values())
