"""Tests for the context_augment stage adapter."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from factory.dataset.runtime.adapters.context_augment import (
    ContextAugmentStageAdapter,
)


def _iso(t: datetime) -> str:
    return t.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ctx(start: datetime, end: datetime, *, temp_c: float = 20.0) -> dict[str, Any]:
    return {
        "context_id": "envctx-v", "vehicle_id": "v",
        "window_start": _iso(start), "window_end": _iso(end),
        "weather": {"temp_c": temp_c, "humidity_pct": 50.0, "precipitation_mm": 0.0},
        "location": {"lat": 37.0, "lon": -122.0, "road_type": "urban"},
        "driving": {}, "vehicle": {"odometer_km": 1000.0, "battery_health_pct": 90.0},
    }


def _frame(ts: datetime) -> dict[str, Any]:
    return {
        "timestamp_ns": int(ts.timestamp() * 1_000_000_000),
        "arbitration_id": "0x100", "decoded_signals": {"speed": 50.0},
    }


def _write_jsonl(records: list[dict[str, Any]]) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for r in records:
        tmp.write(json.dumps(r) + "\n")
    tmp.flush(); tmp.close()
    return Path(tmp.name).as_uri()


A = ContextAugmentStageAdapter  # short alias used below
T0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def test_satisfies_stage_contract():
    a = A()
    assert a.name == "context_augment"
    assert a.stage_version.startswith("factory-context-augment")
    assert isinstance(a.allowed_config, frozenset)


def test_rejects_unknown_config_keys():
    with pytest.raises(ValueError, match="Unsupported context_augment configuration"):
        list(A().execute([], {"merge_strategy": "nearest", "rogue": True}))


def test_rejects_invalid_merge_or_fill_strategy():
    with pytest.raises(ValueError, match="Unsupported merge_strategy"):
        list(A().execute([], {"merge_strategy": "fancy"}))
    with pytest.raises(ValueError, match="Unsupported fill_strategy"):
        list(A().execute([], {"merge_strategy": "nearest", "fill_strategy": "median"}))


def test_rejects_non_positive_max_time_delta():
    with pytest.raises(ValueError, match="max_time_delta_s must be > 0"):
        list(A().execute([], {"merge_strategy": "nearest", "max_time_delta_s": 0}))


def test_nearest_picks_window_containing_frame():
    warm = _ctx(T0, T0 + 10 * M, temp_c=25.0)
    cold = _ctx(T0 + 20 * M, T0 + 30 * M, temp_c=-5.0)
    out = list(A().execute(
        [_frame(T0 + 5 * M)],
        {"merge_strategy": "nearest", "context_fields": ["temp_c"],
         "context_uri": _write_jsonl([warm, cold])},
    ))
    assert out[0]["context"]["temp_c"] == 25.0


def test_nearest_picks_window_with_smallest_edge_gap():
    a = _ctx(T0, T0 + 5 * M, temp_c=10.0)
    b = _ctx(T0 + 10 * M, T0 + 15 * M, temp_c=20.0)
    out = list(A().execute(
        [_frame(T0 + 5 * M + timedelta(seconds=5))],
        {"merge_strategy": "nearest", "context_fields": ["temp_c"],
         "context_uri": _write_jsonl([a, b])},
    ))
    assert out[0]["context"]["temp_c"] in (10.0, 20.0)


def test_interpolate_blends_at_midpoint():
    a = _ctx(T0, T0 + 5 * M, temp_c=0.0)
    b = _ctx(T0 + 25 * M, T0 + 30 * M, temp_c=20.0)
    out = list(A().execute(
        [_frame(T0 + 12 * M + timedelta(seconds=30))],   # halfway between starts
        {"merge_strategy": "interpolate", "context_fields": ["temp_c"],
         "context_uri": _write_jsonl([a, b])},
    ))
    assert out[0]["context"]["temp_c"] == pytest.approx(10.0, abs=1e-6)


def test_interpolate_uses_one_sided_record_when_no_bracket():
    a = _ctx(T0, T0 + 10 * M, temp_c=5.0)
    out = list(A().execute(
        [_frame(T0 + 11 * M)],
        {"merge_strategy": "interpolate", "context_fields": ["temp_c"],
         "max_time_delta_s": 3600.0, "context_uri": _write_jsonl([a])},
    ))
    assert out[0]["context"]["temp_c"] == 5.0


def test_last_known_picks_most_recent_window_at_or_before_frame():
    old = _ctx(T0, T0 + 10 * M, temp_c=10.0)
    new = _ctx(T0 + 10 * M, T0 + 20 * M, temp_c=20.0)
    out = list(A().execute(
        [_frame(T0 + 25 * M)],
        {"merge_strategy": "last_known", "context_fields": ["temp_c"],
         "context_uri": _write_jsonl([old, new])},
    ))
    assert out[0]["context"]["temp_c"] == 20.0


def test_last_known_falls_back_to_first_window_for_early_frame():
    first = _ctx(T0, T0 + 10 * M, temp_c=7.0)
    second = _ctx(T0 + 10 * M, T0 + 20 * M, temp_c=22.0)
    out = list(A().execute(
        [_frame(T0 - M)],
        {"merge_strategy": "last_known", "context_fields": ["temp_c"],
         "max_time_delta_s": 3600.0, "context_uri": _write_jsonl([first, second])},
    ))
    assert out[0]["context"]["temp_c"] == 7.0


def test_fill_null_leaves_missing_fields_as_none():
    ctx = _ctx(T0, T0 + 10 * M, temp_c=20.0)
    ctx["weather"] = {}
    out = list(A().execute(
        [_frame(T0 + timedelta(hours=10))],
        {"merge_strategy": "nearest",
         "context_fields": ["temp_c", "humidity_pct", "precipitation_mm"],
         "fill_strategy": "null", "max_time_delta_s": 60.0,
         "context_uri": _write_jsonl([ctx])},
    ))
    assert out[0]["context"] == {"temp_c": None, "humidity_pct": None, "precipitation_mm": None}


def test_fill_mean_uses_field_means_when_no_match():
    a = _ctx(T0, T0 + 10 * M, temp_c=10.0)
    b = _ctx(T0 + 10 * M, T0 + 20 * M, temp_c=20.0)
    out = list(A().execute(
        [_frame(T0 + timedelta(hours=10))],
        {"merge_strategy": "nearest", "context_fields": ["temp_c"],
         "fill_strategy": "mean", "max_time_delta_s": 60.0,
         "context_uri": _write_jsonl([a, b])},
    ))
    assert out[0]["context"]["temp_c"] == pytest.approx(15.0, abs=1e-6)


def test_fill_last_known_uses_chronologically_latest_value():
    old = _ctx(T0, T0 + 10 * M, temp_c=10.0)
    new = _ctx(T0 + 10 * M, T0 + 20 * M, temp_c=22.0)
    out = list(A().execute(
        [_frame(T0 + timedelta(hours=10))],
        {"merge_strategy": "nearest", "context_fields": ["temp_c"],
         "fill_strategy": "last_known", "max_time_delta_s": 60.0,
         "context_uri": _write_jsonl([old, new])},
    ))
    assert out[0]["context"]["temp_c"] == 22.0


def test_max_time_delta_blocks_distant_and_allows_close_frames():
    ctx = _ctx(T0, T0 + 10 * M, temp_c=5.0)
    cfg = {"merge_strategy": "nearest", "context_fields": ["temp_c"],
           "fill_strategy": "null", "max_time_delta_s": 300.0,
           "context_uri": _write_jsonl([ctx])}
    # 2h past window, 5min ceiling — must be blocked.
    far = list(A().execute([_frame(T0 + timedelta(hours=2))], cfg))
    assert far[0]["context"]["temp_c"] is None
    # 60s past window — within the 5min ceiling, must be allowed.
    near = list(A().execute([_frame(T0 + 10 * M + timedelta(seconds=60))], cfg))
    assert near[0]["context"]["temp_c"] == 5.0


def test_provenance_retains_source_declared_availability() -> None:
    ctx = _ctx(T0, T0 + 10 * M)
    observed = int(T0.timestamp() * 1_000_000_000)
    available = observed + 1_000_000
    ctx.update({"observed_at_ns": observed, "available_at_ns": available})
    out = list(A().execute(
        [_frame(T0 + M)],
        {"context_fields": ["temp_c"], "context_uri": _write_jsonl([ctx])},
    ))[0]
    assert out["context_provenance"]["observed_at_ns"] == observed
    assert out["context_provenance"]["available_at_ns"] == available
