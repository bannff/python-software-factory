"""End-to-end source availability invariants for context projected into CAN X."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.can_window import CanWindowStageAdapter
from factory.dataset.runtime.adapters.context_augment import ContextAugmentStageAdapter
from factory.dataset.runtime.adapters.context_ingest import ContextIngestStageAdapter

T0_NS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
FIELDS = ["lat", "lon", "odometer_km", "battery_health_pct"]


def _write(path: Path, records: dict | list[dict]) -> str:
    rows = records if isinstance(records, list) else [records]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path.as_uri()


def _source(tmp_path: Path, kind: str) -> tuple[str, list[float | None]]:
    timestamps = {
        "observed_at_ns": T0_NS - 20_000_000,
        "available_at_ns": T0_NS - 10_000_000,
    }
    if kind == "gps":
        rows = [{
            "timestamp_ns": T0_NS - (30 - index * 10) * 1_000_000,
            "decoded_signals": {"GPS_Latitude": 37.0, "GPS_Longitude": -122.0},
        } for index in range(2)]
        return _write(tmp_path / "gps.jsonl", rows), [37.0, -122.0, None, None]
    vehicle = {"vehicle_id": "v", "odometer_km": 100.0, **timestamps}
    expected = [None, None, 100.0, None]
    if kind == "vehicle_full":
        vehicle["battery_health_pct"] = 90.0
        expected[-1] = 90.0
    return _write(tmp_path / f"{kind}.json", vehicle), expected


@pytest.mark.parametrize("kind", ["vehicle_full", "gps", "vehicle_partial"])
def test_only_timestamped_source_values_enter_context_plane(
    tmp_path: Path, kind: str,
) -> None:
    source_uri, expected = _source(tmp_path, kind)
    source_name = "gps_can" if kind == "gps" else "vehicle_metadata"
    context = list(ContextIngestStageAdapter().execute([], {
        "sources": [source_name], "input_uri": source_uri, "vehicle_id": "v",
        "time_range": ["2025-01-01T00:00:00Z", "2025-01-01T00:00:01Z"],
    }))[0]
    context_uri = _write(tmp_path / "context.jsonl", context)
    frames = [{
        "timestamp_ns": T0_NS + offset * 1_000_000,
        "vehicle_id": "v", "arbitration_id": "0x1",
        "decoded_signals": {"speed": float(offset)}, "is_failure": 0,
    } for offset in (0, 10, 20)]
    augmented = list(ContextAugmentStageAdapter().execute(frames, {
        "context_uri": context_uri, "context_fields": FIELDS,
    }))
    projected = list(CanWindowStageAdapter().execute(augmented, {
        "window_size_ms": 20, "step_size_ms": 20, "grid_resolution_ms": 10,
        "observation_cutoff_ms": 20, "label_horizon_ms": 10,
        "signal_columns": ["speed"], "context_columns": FIELDS,
        "context_feature_policy": {
            "use_context": True, "prior_data_allowlist": FIELDS,
        },
    }))[0]
    assert projected["context"]["columns"] == FIELDS
    assert projected["context"]["values"] == [expected, expected]
