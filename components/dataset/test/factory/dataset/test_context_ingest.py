"""Tests for the context_ingest stage adapter.

Covers happy-path config, missing API key, GPS extraction from a
JSONL input, and config / source validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from factory.dataset.runtime.adapters.context_ingest import (
    ContextIngestStageAdapter,
)
from factory.dataset.runtime.adapters._context_ingest_helpers import (
    VALID_SOURCES,
)


def _adapter() -> ContextIngestStageAdapter:
    return ContextIngestStageAdapter()


def _can_records(n: int = 4) -> list[dict[str, Any]]:
    return [
        {
            "timestamp_ns": i * 1_000_000,
            "arbitration_id": "0x100",
            "decoded_signals": {
                "GPS_Latitude": 37.0 + 0.001 * i,
                "GPS_Longitude": -122.0 - 0.001 * i,
                "GPS_Speed": 20.0 + 2.0 * i,
            },
        }
        for i in range(n)
    ]


# --- Protocol compliance ----------------------------------------------------


def test_satisfies_stage_contract():
    a = _adapter()
    assert a.name == "context_ingest"
    assert a.stage_version.startswith("factory-context-ingest")
    assert isinstance(a.allowed_config, frozenset)
    assert "sources" in a.allowed_config


# --- Happy path -------------------------------------------------------------


def test_valid_config_yields_canonical_record():
    out = list(_adapter().execute(
        iter([]),
        {
            "sources": ["vehicle_metadata"],
            "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
            "location": [37.0, -122.0],
            "vehicle_id": "veh-1",
        },
    ))
    assert len(out) == 1
    rec = out[0]
    assert rec["vehicle_id"] == "veh-1"
    assert rec["window_start"] == "2025-01-01T00:00:00Z"
    assert rec["window_end"] == "2025-01-01T01:00:00Z"
    assert rec["weather"] == {}
    assert rec["vehicle"] == {}
    assert rec["location"] == {"lat": None, "lon": None, "road_type": None}
    assert rec["context_id"].startswith("envctx-veh-1-")


def test_consumes_upstream_iterable_without_yielding_per_record():
    upstream = [{"x": 1}, {"x": 2}, {"x": 3}]
    out = list(_adapter().execute(
        iter(upstream),
        {
            "sources": ["vehicle_metadata"],
            "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
        },
    ))
    assert len(out) == 1


# --- Missing API key → no weather, no network call --------------------------


def test_missing_api_key_returns_empty_weather_without_calling_network():
    with patch(
        "factory.dataset.runtime.adapters._context_ingest_helpers.urllib.request.urlopen",
    ) as mock_urlopen:
        out = list(_adapter().execute(
            iter([]),
            {
                "sources": ["weather_openweathermap"],
                "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
                "location": [37.0, -122.0],
            },
        ))
    assert out[0]["weather"] == {}
    mock_urlopen.assert_not_called()


def test_missing_location_with_weather_source_returns_empty_weather():
    with patch(
        "factory.dataset.runtime.adapters._context_ingest_helpers.urllib.request.urlopen",
    ) as mock_urlopen:
        out = list(_adapter().execute(
            iter([]),
            {
                "sources": ["weather_openweathermap"],
                "weather_api_key": "abc123",
                "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
            },
        ))
    assert out[0]["weather"] == {}
    mock_urlopen.assert_not_called()


# --- GPS extraction ---------------------------------------------------------


def test_gps_extracted_from_can_input_uri(tmp_path: Path):
    can_path = tmp_path / "can.jsonl"
    can_path.write_text("\n".join(json.dumps(r) for r in _can_records(4)))
    out = list(_adapter().execute(
        iter([]),
        {
            "sources": ["gps_can"],
            "input_uri": can_path.as_uri(),
            "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
        },
    ))
    loc = out[0]["location"]
    assert 36.9 < loc["lat"] < 37.1
    assert -122.1 < loc["lon"] < -121.9
    # Speeds range 20-26 km/h, all < 30 → "urban".
    assert loc["road_type"] == "urban"


# --- Validation: unknown config keys & sources ------------------------------


def test_rejects_unknown_config_keys():
    with pytest.raises(ValueError, match="Unsupported context_ingest configuration"):
        list(_adapter().execute(iter([]), {
            "sources": ["vehicle_metadata"],
            "rogue_key": True,
        }))


def test_rejects_empty_sources():
    with pytest.raises(ValueError, match="non-empty 'sources'"):
        list(_adapter().execute(iter([]), {"sources": []}))


def test_rejects_unknown_sources():
    bad = "not_a_real_source"
    assert bad not in VALID_SOURCES
    with pytest.raises(ValueError, match="Unsupported context sources"):
        list(_adapter().execute(iter([]), {"sources": [bad]}))


# --- OWM happy path (network mocked) ----------------------------------------


def test_weather_payload_normalized_when_api_returns_data():
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({
        "data": [{
            "temp": 300.0,        # 300 K → 26.85 °C
            "humidity": 65.0,
            "rain": {"1h": 0.4},
        }],
    }).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp
    with patch(
        "factory.dataset.runtime.adapters._context_ingest_helpers.urllib.request.urlopen",
        return_value=fake_resp,
    ):
        out = list(_adapter().execute(
            iter([]),
            {
                "sources": ["weather_openweathermap"],
                "weather_api_key": "k",
                "location": [37.0, -122.0],
                "time_range": ("2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"),
            },
        ))
    w = out[0]["weather"]
    assert w["temp_c"] == pytest.approx(26.85, abs=1e-6)
    assert w["humidity_pct"] == 65.0
    assert w["precipitation_mm"] == 0.4
