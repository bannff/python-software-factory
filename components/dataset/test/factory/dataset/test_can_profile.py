"""Contract tests for the can_profile stage adapter.

Chains ``CanIngestStageAdapter`` → ``CanProfileStageAdapter`` against the
real MF4 fixture so we validate the constraint schema against actual
decoded signals, not synthetic stubs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.can_ingest import CanIngestStageAdapter
from factory.dataset.runtime.adapters.can_profile import CanProfileStageAdapter
from factory.dataset.runtime.ports import DatasetStagePort

CAN_DATA_DIR = Path("/Users/danielrodrigo/Downloads/CAN Data")
MF4_FIXTURE = CAN_DATA_DIR / "00000001-6A0B6FCD.MF4"
DBC_FIXTURE = CAN_DATA_DIR / "dbc" / "toyota_legacy_combined.dbc"


def _fixtures_present() -> bool:
    return MF4_FIXTURE.exists() and DBC_FIXTURE.exists()


def _profile(
    *,
    correlation_threshold: float = 0.7,
    window_ms: int = 10,
) -> dict:
    if not _fixtures_present():
        pytest.skip(f"MF4/DBC fixtures not found under {CAN_DATA_DIR}")
    ingest = CanIngestStageAdapter(dbc_path=str(DBC_FIXTURE))
    profile = CanProfileStageAdapter()
    records = ingest.execute(
        [],
        {"mf4_paths": [str(MF4_FIXTURE)], "dbc_path": str(DBC_FIXTURE)},
    )
    schemas = list(
        profile.execute(
            records,
            {"window_ms": window_ms, "correlation_threshold": correlation_threshold},
        )
    )
    assert len(schemas) == 1, f"Expected one schema, got {len(schemas)}"
    return schemas[0]


def test_satisfies_dataset_stage_port() -> None:
    if not _fixtures_present():
        pytest.skip("MF4/DBC fixtures not found")
    adapter = CanProfileStageAdapter()
    assert callable(getattr(adapter, "execute", None))
    assert adapter.name == "can_profile"
    assert adapter.stage_version
    assert "window_ms" in adapter.allowed_config
    assert "correlation_threshold" in adapter.allowed_config
    assert hasattr(DatasetStagePort, "execute")


def test_schema_has_expected_top_level_shape() -> None:
    schema = _profile()
    assert schema["version"] == "1"
    assert isinstance(schema["can_ids"], dict)
    assert schema["can_ids"], "Expected at least one CAN ID"
    summary = schema["summary"]
    assert {"total_can_ids", "total_signals", "total_frames", "time_span_seconds"} <= set(summary)


def test_0x2C1_has_thirteen_signals() -> None:
    schema = _profile()
    eng1s01 = schema["can_ids"]["0x2C1"]
    assert eng1s01["message_name"] == "ENG1S01"
    assert len(eng1s01["signals"]) == 13
    # Spot-check known DBC signal names.
    assert {"ETCSFB", "ENG01SUM"}.issubset(set(eng1s01["signals"].keys()))


def test_signal_boundaries_within_physical_ranges() -> None:
    schema = _profile()
    for can_id, entry in schema["can_ids"].items():
        for name, s in entry["signals"].items():
            assert s["min"] <= s["max"], f"{can_id}/{name}: min > max"
            assert s["std"] >= 0.0, f"{can_id}/{name}: negative std"
            assert s["delta_max"] >= 0.0, f"{can_id}/{name}: negative delta"
            assert s["null_count"] >= 0
            # Sanity: a signal observed on the bus should have at least one
            # non-null sample and a finite mean.
            assert s["mean"] == s["mean"]  # not NaN


def test_correlations_in_valid_range() -> None:
    schema = _profile()
    for can_id, entry in schema["can_ids"].items():
        for triple in entry["correlations"]:
            a, b, r = triple
            assert isinstance(a, str) and isinstance(b, str) and a != b
            assert -1.0 <= r <= 1.0, f"{can_id} {a}/{b}: invalid r={r}"
            # Threshold was 0.7 — every emitted pair must clear it.
            assert abs(r) >= 0.7


def test_correlation_threshold_filters_weak_pairs() -> None:
    # 0.99 threshold should emit very few (often zero) pairs.
    high = _profile(correlation_threshold=0.99)
    low = _profile(correlation_threshold=0.0)
    high_count = sum(len(e["correlations"]) for e in high["can_ids"].values())
    low_count = sum(len(e["correlations"]) for e in low["can_ids"].values())
    assert high_count <= low_count


def test_frame_rates_positive_and_reasonable() -> None:
    schema = _profile()
    for can_id, entry in schema["can_ids"].items():
        rate = entry["frame_rate_hz"]
        # The test capture is ~77ms; some IDs burst at >1kHz which is
        # legitimate for a dense stress capture. We bound the upper limit
        # generously to detect unit-conversion or off-by-ns errors.
        assert 0.1 <= rate <= 100_000.0, f"{can_id} rate {rate} Hz out of range"
        assert entry["frame_count"] > 0


def test_summary_counts_match_can_ids() -> None:
    schema = _profile()
    summary = schema["summary"]
    assert summary["total_can_ids"] == len(schema["can_ids"])
    assert summary["total_signals"] == sum(
        len(e["signals"]) for e in schema["can_ids"].values()
    )
    # total_frames counts the full capture (raw + decoded); it must be >=
    # the sum of decoded per-CAN-ID frame counts.
    decoded_total = sum(e["frame_count"] for e in schema["can_ids"].values())
    assert summary["total_frames"] >= decoded_total
    assert summary["time_span_seconds"] >= 0.0


def test_rejects_unknown_configuration_keys() -> None:
    if not _fixtures_present():
        pytest.skip("MF4/DBC fixtures not found")
    adapter = CanProfileStageAdapter()
    with pytest.raises(ValueError, match="Unsupported can_profile configuration"):
        list(adapter.execute(iter([]), {"window_ms": 10, "rogue": True}))


def test_empty_records_produces_empty_schema() -> None:
    adapter = CanProfileStageAdapter()
    schema = list(adapter.execute(iter([]), {}))[0]
    assert schema["version"] == "1"
    assert schema["can_ids"] == {}
    assert schema["summary"]["total_can_ids"] == 0
    assert schema["summary"]["total_frames"] == 0
    assert schema["summary"]["total_signals"] == 0
    assert schema["summary"]["time_span_seconds"] == 0.0
