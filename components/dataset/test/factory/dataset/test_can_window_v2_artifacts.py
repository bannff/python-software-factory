"""Dataset-owned CAN artifacts and ref-only causal-window invariants."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from factory.dataset.runtime.adapters.can_artifact_stages import (
    CanPriorPolicyStageAdapter, CanSignalSchemaStageAdapter,
)
from factory.dataset.runtime.adapters.can_input_guard import (
    MAX_STANDALONE_CAN_INPUT_BYTES,
)
from factory.dataset.runtime.adapters.can_window_v2 import CanWindowV2StageAdapter
from factory.dataset.runtime.can_artifact_codec import (
    ref_from_prior_policy_uri, ref_from_signal_schema_uri,
)


def _canonical(body: dict) -> bytes:
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()


def _refs(tmp_path: Path, context: bool = True) -> dict:
    schema = list(CanSignalSchemaStageAdapter().execute([{
        "version": "1", "can_ids": {"0x1": {"signals": {"b": {}, "a": {}}}},
    }], {"can_id": "0x1"}))[0]
    policy = list(CanPriorPolicyStageAdapter().execute([], {
        "use_context": context,
        "prior_data_allowlist": ["temp_c"] if context else [],
    }))[0]
    schema_path, policy_path = tmp_path / "schema.json", tmp_path / "policy.json"
    schema_path.write_bytes(_canonical(schema))
    policy_path.write_bytes(_canonical(policy))
    schema_ref = ref_from_signal_schema_uri(schema_path.as_uri())
    policy_ref = ref_from_prior_policy_uri(policy_path.as_uri())
    return {
        "signal_schema_refs_by_can_id": {
            "0x1": schema_ref.model_dump(mode="json"),
        },
        "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
    }


def _records(*, available_at_ns: int = 0) -> list[dict]:
    return [
        {"timestamp_ns": ts, "arbitration_id": "0x1", "vehicle_id": "v",
         "decoded_signals": {"a": float(index), "b": float(index + 1)},
         "context": {"temp_c": 20.0 + index}, "is_failure": index == 2,
         "context_provenance": {
             "version": "2.0", "source_kind": "prior_data",
             "observed_at_ns": 0, "available_at_ns": available_at_ns,
             "merge_strategy": "last_known",
         }}
        for index, ts in enumerate((0, 10_000_000, 20_000_000))
    ]


def _config(tmp_path: Path) -> dict:
    return {
        **_refs(tmp_path), "window_size_ms": 20, "step_size_ms": 20,
        "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
        "label_horizon_ms": 10,
    }


def test_v2_emits_exact_planes_and_bound_refs(tmp_path: Path) -> None:
    result = list(CanWindowV2StageAdapter().execute(_records(), _config(tmp_path)))
    assert len(result) == 1 and result[0]["label"] == 1
    assert result[0]["signal"]["columns"] == ["b", "a"]
    assert result[0]["context"]["columns"] == ["temp_c"]
    observations = result[0]["provenance"]["context_observations"]
    assert observations and observations[0]["observed_at_ns"] == 0
    assert observations[0]["available_at_ns"] == 0
    assert set(result[0]) == {
        "schema_version", "can_id", "vehicle_id", "signal", "context",
        "provenance", "bounds", "label", "window_size_ms", "step_size_ms",
        "grid_resolution_ms", "observation_cutoff_ms", "label_horizon_ms",
        "num_timesteps", "metadata",
    }
    assert "window_data" not in result[0]
    assert set(result[0]["metadata"]) == {
        "label_record_count", "signal_schema_ref", "prior_data_policy_ref",
    }


@pytest.mark.parametrize("container,field", [
    ("prior_data_policy_ref", "uri"), ("prior_data_policy_ref", "digest"),
    ("signal_schema_refs_by_can_id", "uri"),
    ("signal_schema_refs_by_can_id", "digest"),
])
def test_v2_fails_closed_when_any_ref_field_is_absent(
    tmp_path: Path, container: str, field: str,
) -> None:
    config = _config(tmp_path)
    target = config[container]
    if container == "signal_schema_refs_by_can_id":
        target = target["0x1"]
    target.pop(field)
    with pytest.raises(ValueError):
        list(CanWindowV2StageAdapter().execute(_records(), config))


def test_v2_rejects_inline_schema_and_tampering(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(ValueError, match="Unsupported can_window_v2"):
        list(CanWindowV2StageAdapter().execute(_records(), {
            **config, "signal_columns": ["a", "b"],
        }))
    uri = config["signal_schema_refs_by_can_id"]["0x1"]["uri"]
    Path(uri.removeprefix("file://")).write_text("{}")
    with pytest.raises(ValueError, match="canonical|digest|invalid"):
        list(CanWindowV2StageAdapter().execute(_records(), config))


@pytest.mark.parametrize("observed,available,match", [
    (2, 1, "not prior data"),
    (0, 1, "not available before the frame"),
    ("0", 0, "non-bool integers"),
])
def test_typed_provenance_order_is_enforced(
    tmp_path: Path, observed, available, match: str,
) -> None:
    records = _records(available_at_ns=available)
    records[0]["context_provenance"]["observed_at_ns"] = observed
    with pytest.raises(ValueError, match=match):
        list(CanWindowV2StageAdapter().execute(records, _config(tmp_path)))


@given(st.permutations(["temp_c", "humidity_pct", "odometer_km"]))
def test_policy_artifact_preserves_declared_feature_order(columns) -> None:
    config = {"use_context": True, "prior_data_allowlist": list(columns)}
    left = list(CanPriorPolicyStageAdapter().execute([], config))[0]
    right = list(CanPriorPolicyStageAdapter().execute([], deepcopy(config)))[0]
    assert left == right
    assert left["prior_data_allowlist"] == list(columns)


def test_unapproved_context_semantics_are_rejected() -> None:
    with pytest.raises(ValueError, match="not approved prior numeric data"):
        list(CanPriorPolicyStageAdapter().execute([], {
            "use_context": True,
            "prior_data_allowlist": ["future_failure_probability"],
        }))


def test_v2_oversized_standalone_input_is_rejected_before_read(
    tmp_path, monkeypatch,
) -> None:
    path = tmp_path / "oversized.jsonl"
    with path.open("wb") as handle:
        handle.seek(MAX_STANDALONE_CAN_INPUT_BYTES)
        handle.write(b"\n")
    monkeypatch.setattr(
        "factory.dataset.runtime.helpers.load_records_from_uri",
        lambda _uri: pytest.fail("oversized input must not be read"),
    )
    with pytest.raises(ValueError, match="1 GiB.*shard or sample"):
        list(CanWindowV2StageAdapter().execute(
            [], {**_config(tmp_path), "input_uri": path.as_uri()},
        ))
