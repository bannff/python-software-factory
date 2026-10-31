"""Compact compatibility tests for explicit legacy can-window@1 behavior."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from factory.dataset.runtime.adapters.can_input_guard import (
    MAX_STANDALONE_CAN_INPUT_BYTES,
)
from factory.dataset.runtime.adapters.can_window import CanWindowStageAdapter


def _record(ms: int, signals=None, failure: int = 0, can_id: str = "0x25") -> dict:
    return {
        "timestamp_ns": ms * 1_000_000, "vehicle_id": "v",
        "arbitration_id": can_id, "decoded_signals": signals,
        "is_failure": failure,
    }


def _config(**extra) -> dict:
    return {
        "window_size_ms": 20, "step_size_ms": 20,
        "grid_resolution_ms": 10, "observation_cutoff_ms": 20,
        "label_horizon_ms": 10, "signal_columns": ["a", "b"], **extra,
    }


def _records() -> list[dict]:
    return [
        _record(0, {"a": 1.0, "b": 2.0}),
        _record(10, {"a": 3.0, "b": 4.0}),
        _record(20, {"a": 9.0, "b": 9.0}, failure=1),
    ]


def test_stage_identity_and_unknown_config() -> None:
    adapter = CanWindowStageAdapter()
    assert adapter.name == "can_window" and adapter.stage_version
    with pytest.raises(ValueError, match="Unsupported can_window"):
        list(adapter.execute(_records(), {"rogue": True}))


def test_legacy_route_emits_v2_planes_plus_compatibility_keys() -> None:
    result = list(CanWindowStageAdapter().execute(_records(), _config()))
    assert len(result) == 1 and result[0]["label"] == 1
    assert result[0]["schema_version"] == "2.0"
    assert result[0]["signal"]["columns"] == ["a", "b"]
    assert result[0]["window_data"] == result[0]["signal"]["values"]
    assert result[0]["signal_names"] == ["a", "b"]
    assert result[0]["arbitration_id"] == "0x25"


def test_future_label_frame_is_excluded_from_observation() -> None:
    result = list(CanWindowStageAdapter().execute(_records(), _config()))[0]
    assert result["window_data"] == [[1.0, 2.0], [3.0, 4.0]]
    assert result["label"] == 1


@given(
    future_a=st.floats(allow_nan=False, allow_infinity=False),
    future_b=st.floats(allow_nan=False, allow_infinity=False),
    generation_only=st.text(max_size=20),
)
def test_future_generation_fields_cannot_change_observation_projection(
    future_a: float, future_b: float, generation_only: str,
) -> None:
    baseline = list(CanWindowStageAdapter().execute(_records(), _config()))[0]
    changed = _records()
    changed[-1]["decoded_signals"] = {"a": future_a, "b": future_b}
    changed[-1].update({
        "failure_mode": generation_only,
        "correlation_heatmap": {"future": future_a},
        "synthetic_lineage": [{"future": generation_only}],
    })
    projected = list(CanWindowStageAdapter().execute(changed, _config()))[0]
    assert projected["window_data"] == baseline["window_data"]
    assert projected["label"] == baseline["label"] == 1


@pytest.mark.parametrize("key,value", [
    ("window_size_ms", 0), ("step_size_ms", -1),
    ("grid_resolution_ms", 0), ("observation_cutoff_ms", 0),
])
def test_positive_temporal_fields(key: str, value: int) -> None:
    with pytest.raises(ValueError, match=key):
        list(CanWindowStageAdapter().execute(_records(), _config(**{key: value})))


def test_missing_and_empty_inputs_yield_no_windows(tmp_path: Path) -> None:
    assert list(CanWindowStageAdapter().execute([])) == []
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    assert list(CanWindowStageAdapter().execute([], {"input_uri": path.as_uri()})) == []


def test_input_uri_and_timespans(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in _records()))
    result = list(CanWindowStageAdapter().execute([], _config(
        input_uri=path.as_uri(), emit_timespans=True,
    )))
    assert len(result) == 1
    assert result[0]["timespans"] == [10_000_000.0, 10_000_000.0]


def test_sparse_fixed_grid_timing_sums_to_observation_cutoff() -> None:
    records = [
        _record(0, {"a": 1.0, "b": 2.0}),
        _record(30, {"a": 3.0, "b": 4.0}),
        _record(40, {"a": 9.0, "b": 9.0}, failure=1),
    ]
    result = list(CanWindowStageAdapter().execute(records, _config(
        window_size_ms=40, step_size_ms=40, observation_cutoff_ms=40,
        emit_timespans=True,
    )))[0]
    assert result["timespans"] == [10_000_000.0] * 4
    assert sum(result["timespans"]) == 40_000_000.0


@pytest.mark.parametrize("source_ms", [(0, 0, 20), (10, 0, 20)])
def test_timing_plane_rejects_duplicate_or_regressing_source_time(source_ms) -> None:
    records = [
        _record(ms, {"a": float(index), "b": 1.0}, failure=index == 2)
        for index, ms in enumerate(source_ms)
    ]
    with pytest.raises(ValueError, match="strictly increasing"):
        list(CanWindowStageAdapter().execute(records, _config(emit_timespans=True)))


def test_strictly_increasing_same_cell_preserves_last_write() -> None:
    records = [
        _record(0, {"a": 1.0, "b": 2.0}),
        _record(5, {"a": 5.0, "b": 6.0}),
        _record(10, {"a": 3.0, "b": 4.0}),
        _record(20, {"a": 9.0, "b": 9.0}, failure=1),
    ]
    result = list(CanWindowStageAdapter().execute(
        records, _config(emit_timespans=True),
    ))[0]
    assert result["window_data"] == [[5.0, 6.0], [3.0, 4.0]]
    assert result["timespans"] == [10_000_000.0, 10_000_000.0]


def test_per_can_schema_is_required_for_every_present_id() -> None:
    with pytest.raises(ValueError, match="signal columns missing"):
        list(CanWindowStageAdapter().execute(_records(), {
            **_config(), "signal_columns": None,
            "signal_columns_by_can_id": {"0x99": ["a", "b"]},
        }))


def test_oversized_standalone_input_is_rejected_before_read(tmp_path, monkeypatch) -> None:
    path = tmp_path / "oversized.jsonl"
    with path.open("wb") as handle:
        handle.seek(MAX_STANDALONE_CAN_INPUT_BYTES)
        handle.write(b"\n")
    monkeypatch.setattr(
        "factory.dataset.runtime.adapters.can_window._load_records_from_uri",
        lambda _uri: pytest.fail("oversized input must not be read"),
    )
    with pytest.raises(ValueError, match="1 GiB.*shard or sample"):
        list(CanWindowStageAdapter().execute([], {"input_uri": path.as_uri()}))
