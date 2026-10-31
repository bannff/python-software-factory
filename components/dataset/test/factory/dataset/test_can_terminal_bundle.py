"""Exact prepared bundle and real Dataset-stage recovery contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from factory.dataset.runtime.can_artifact_codec import (
    artifact_ref, canonical_artifact_bytes, create_prior_policy,
    create_signal_schema,
)
from factory.dataset.runtime.can_terminal_artifacts import stage_artifacts
from factory.dataset.runtime.can_terminal_prepare import prepare_training_bundle
from factory.dataset.runtime.can_terminal_stage import CanTerminalStageRunner
from factory.dataset.runtime.can_terminal_verify import verify_terminal
from factory.dataset.runtime.local import LocalDatasetStore


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


def test_prepared_bundle_contains_exact_contract_x_y_and_timespans(tmp_path: Path):
    policy = create_prior_policy(use_context=False, prior_data_allowlist=())
    schema = create_signal_schema(can_id="0x1", signal_columns=("rpm",))
    policy_ref = _artifact(tmp_path, "policy.json", policy)
    schema_ref = _artifact(tmp_path, "schema.json", schema)
    augmented = tmp_path / "augmented.jsonl"
    augmented.write_text(json.dumps(_window(policy_ref, schema_ref), sort_keys=True) + "\n")
    augmented_digest = hashlib.sha256(augmented.read_bytes()).hexdigest()

    bundle, artifacts = prepare_training_bundle(
        augmented_uri=augmented.as_uri(), augmented_digest=augmented_digest,
        policy=policy, policy_ref=policy_ref, schemas={"0x1": schema},
        schema_refs={"0x1": schema_ref}, root=tmp_path,
        request_sha256="a" * 64,
    )
    prepared = bundle["prepared_by_can_id"]["0x1"]
    assert bundle["top_can_ids"] == ["0x1"]
    assert set(prepared) == {
        "contract_artifact", "x_3d_artifact", "x_2d_artifact", "y_artifact",
        "timespans_artifact", "n_samples", "window_size", "n_features",
        "label_dist",
    }
    X = np.load(Path(artifacts[prepared["x_3d_artifact"]]["uri"].removeprefix("file://")))
    y = np.load(Path(artifacts[prepared["y_artifact"]]["uri"].removeprefix("file://")))
    timing = np.load(Path(artifacts[prepared["timespans_artifact"]]["uri"].removeprefix("file://")))
    assert X.shape == (1, 2, 1)
    assert y.tolist() == [1]
    assert timing.shape == (1, 2)
    for value in artifacts.values():
        assert value["sha256"] == value["evidence"]["sha256"]


def test_real_stage_recovers_published_effect_and_checkpoint_tamper_fails(tmp_path: Path):
    runner = CanTerminalStageRunner(tmp_path, "attempt", "b" * 64)
    config = {"use_context": True, "prior_data_allowlist": ["temp_c"]}
    first = runner.run(
        "prior_data_policy", "recipe://local/can-prior-policy@1", [], config,
    )
    policy = json.loads(Path(first["dataset_uri"].removeprefix("file://")).read_text())
    assert policy["use_context"] is True
    assert policy["prior_data_allowlist"] == ["temp_c"]
    store = LocalDatasetStore(tmp_path)
    status = store.get_job(first["job_id"])
    assert status is not None
    store.save_job(status.model_copy(update={
        "status": "running", "artifact": None, "completed_at": None,
    }))
    recovered = runner.run(
        "prior_data_policy", "recipe://local/can-prior-policy@1", [], config,
    )
    assert recovered == first

    terminal = {
        "status": "completed", "attempt_id": "attempt",
        "request_sha256": "b" * 64,
        "artifacts": stage_artifacts({"prior_data_policy": first}),
        "stage_receipts": {"prior_data_policy": first},
    }
    verify_terminal(
        tmp_path, terminal, attempt_id="attempt", request_sha256="b" * 64,
        expected_roles={"prior_data_policy"},
    )
    substituted = {**terminal, "stage_receipts": {
        "prior_data_policy": {**first, "job_id": "can-" + "0" * 64},
    }}
    with pytest.raises(ValueError, match="job identity mismatch"):
        verify_terminal(
            tmp_path, substituted, attempt_id="attempt", request_sha256="b" * 64,
            expected_roles={"prior_data_policy"},
        )
    checkpoint = next((tmp_path / "checkpoints" / first["job_id"]).glob("*.checkpoint.json"))
    checkpoint.chmod(0o644)
    checkpoint.write_bytes(checkpoint.read_bytes() + b" ")
    with pytest.raises(ValueError):
        verify_terminal(
            tmp_path, terminal, attempt_id="attempt", request_sha256="b" * 64,
        expected_roles={"prior_data_policy"},
        )


def test_terminal_v2_window_receives_scoped_temporal_config(tmp_path: Path):
    policy = create_prior_policy(use_context=False, prior_data_allowlist=())
    schema = create_signal_schema(can_id="0x1", signal_columns=("rpm",))
    policy_ref = _artifact(tmp_path, "window-policy.json", policy)
    schema_ref = _artifact(tmp_path, "window-schema.json", schema)
    raw = tmp_path / "raw.jsonl"
    records = [
        {"timestamp_ns": ts, "arbitration_id": "0x1", "vehicle_id": "v",
         "decoded_signals": {"rpm": float(index + 1)},
         "is_failure": index == 2}
        for index, ts in enumerate((0, 10_000_000, 20_000_000))
    ]
    raw.write_text("".join(json.dumps(row) + "\n" for row in records))
    result = CanTerminalStageRunner(tmp_path, "window", "d" * 64).run(
        "window", "recipe://local/can-window@2",
        [raw.as_uri(), policy_ref.uri, schema_ref.uri],
        {"window_size_ms": 20, "step_size_ms": 20,
         "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
         "label_horizon_ms": 10},
        input_roles=["primary_dataset", "prior_data_policy", "signal_schema:0x1"],
    )
    rows = Path(result["dataset_uri"].removeprefix("file://")).read_text().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["label"] == 1


def test_window_temporal_tamper_is_rejected(tmp_path: Path):
    policy = create_prior_policy(use_context=False, prior_data_allowlist=())
    schema = create_signal_schema(can_id="0x1", signal_columns=("rpm",))
    policy_ref = _artifact(tmp_path, "policy.json", policy)
    schema_ref = _artifact(tmp_path, "schema.json", schema)
    window = _window(policy_ref, schema_ref)
    window["bounds"]["observation_cutoff_ns"] = 19_000_000
    augmented = tmp_path / "bad.jsonl"
    augmented.write_text(json.dumps(window, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="observation bounds mismatch"):
        prepare_training_bundle(
            augmented_uri=augmented.as_uri(),
            augmented_digest=hashlib.sha256(augmented.read_bytes()).hexdigest(),
            policy=policy, policy_ref=policy_ref, schemas={"0x1": schema},
            schema_refs={"0x1": schema_ref}, root=tmp_path,
            request_sha256="c" * 64,
        )
