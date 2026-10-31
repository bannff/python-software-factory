"""Tests for the CAN augmentation stage adapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.can_augment import CanAugmentStageAdapter


def _make_window(
    ts_start: int = 0,
    arb_id: str = "0x25",
    n_steps: int = 500,
    n_features: int = 2,
    is_failure: int = 0,
) -> dict:
    import numpy as np
    rng = np.random.default_rng(42)
    data = rng.uniform(0, 100, (n_steps, n_features)).tolist()
    return {
        "window_data": data,
        "label": is_failure,
        "arbitration_id": arb_id,
        "vehicle_id": "test",
        "window_start_ns": ts_start,
        "window_end_ns": ts_start + 5_000_000_000,
        "signal_names": [f"S{i}" for i in range(n_features)],
        "num_timesteps": n_steps,
        "num_features": n_features,
        "is_failure": is_failure,
        "trip_id": "synth_test",
        "capture_source": "synthetic",
    }


def _adapter() -> CanAugmentStageAdapter:
    return CanAugmentStageAdapter()


# --- Protocol compliance ---

def test_satisfies_dataset_stage_port():
    a = _adapter()
    assert a.name == "can_augment"
    assert a.stage_version.startswith("factory-can-augment")
    assert isinstance(a.allowed_config, frozenset)


def test_rejects_unknown_config_keys():
    records = [_make_window()]
    with pytest.raises(ValueError, match="Unsupported can_augment"):
        list(_adapter().execute(records, {"rogue_key": True}))


# --- Multiplication ---

def test_jitter_multiplies_records():
    records = [_make_window()]
    result = list(_adapter().execute(records, {
        "techniques": ["jitter"],
        "seed": 42,
    }))
    originals = [r for r in result if r.get("capture_source") != "augmented"]
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(originals) == 1
    assert len(augmented) >= 1


def test_scale_multiplies_records():
    records = [_make_window()]
    result = list(_adapter().execute(records, {
        "techniques": ["scale"],
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1


def test_combined_techniques_multiply_combinatorially():
    records = [_make_window(), _make_window(ts_start=5_000_000_000)]
    result = list(_adapter().execute(records, {
        "techniques": ["jitter", "scale"],
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 2, f"Expected >=2 augmented, got {len(augmented)}"


def test_warp_preserves_shape():
    records = [_make_window(n_steps=100, n_features=2)]
    result = list(_adapter().execute(records, {
        "techniques": ["warp"],
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1
    for r in augmented:
        assert len(r["window_data"]) == 100
        assert len(r["window_data"][0]) == 2


def test_permute_preserves_shape():
    records = [_make_window(n_steps=100, n_features=2)]
    result = list(_adapter().execute(records, {
        "techniques": ["permute"],
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1
    for r in augmented:
        assert len(r["window_data"]) == 100
        assert len(r["window_data"][0]) == 2


def test_warp_different_from_original():
    records = [_make_window(n_steps=100)]
    result = list(_adapter().execute(records, {
        "techniques": ["warp"],
        "warp_factor": 0.3,
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1
    orig = records[0]["window_data"]
    aug = augmented[0]["window_data"]
    assert orig != aug, "Warp should change the data"


def test_permute_different_from_original():
    records = [_make_window(n_steps=100)]
    result = list(_adapter().execute(records, {
        "techniques": ["permute"],
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1
    orig = records[0]["window_data"]
    aug = augmented[0]["window_data"]
    assert orig != aug, "Permute should change the data"


# --- Failure preservation ---

def test_failure_records_pass_through_unchanged():
    records = [_make_window(is_failure=1)]
    result = list(_adapter().execute(records, {
        "techniques": ["jitter", "scale"],
        "preserve_failures": True,
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) == 0, "Failure records should not be augmented"


def test_failure_records_augmented_when_flag_off():
    records = [_make_window(is_failure=1)]
    result = list(_adapter().execute(records, {
        "techniques": ["jitter"],
        "preserve_failures": False,
        "seed": 42,
    }))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) >= 1


# --- Output contract ---

def test_output_preserves_all_input_fields():
    records = [_make_window()]
    result = list(_adapter().execute(records, {"techniques": ["jitter"], "seed": 42}))
    for r in result:
        assert "window_data" in r
        assert "label" in r
        assert "arbitration_id" in r
        assert "num_timesteps" in r


def test_augmented_window_data_shape_matches_original():
    records = [_make_window(n_steps=100, n_features=3)]
    result = list(_adapter().execute(records, {"techniques": ["jitter"], "seed": 42}))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    for r in augmented:
        assert len(r["window_data"]) == 100
        assert len(r["window_data"][0]) == 3


def test_augmented_trip_id_suffixed():
    records = [_make_window()]
    records[0]["trip_id"] = "orig_trip"
    result = list(_adapter().execute(records, {"techniques": ["jitter"], "seed": 42}))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    for r in augmented:
        assert "aug_jitter" in r["trip_id"]


# --- Empty input ---

def test_empty_input_yields_nothing():
    result = list(_adapter().execute([]))
    assert result == []


def test_window_without_data_skipped():
    rec = _make_window()
    rec["window_data"] = []
    result = list(_adapter().execute([rec], {"techniques": ["jitter"], "seed": 42}))
    augmented = [r for r in result if r.get("capture_source") == "augmented"]
    assert len(augmented) == 0


# --- Standalone loading ---

def test_input_uri_loads_records(tmp_path: Path):
    records = [_make_window()]
    path = tmp_path / "windows.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    result = list(_adapter().execute([], {
        "input_uri": path.as_uri(),
        "techniques": ["jitter"],
        "seed": 42,
    }))
    assert len(result) >= 1
