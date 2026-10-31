"""Contract tests for the MF4 ingest + DBC decode CAN stage adapter.

Exercises the real Toyota Legacy MF4 + DBC corpus located at
``~/Downloads/CAN Data/`` so we know the adapter handles actual binary
captures, not synthetic stubs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.can_ingest import CanIngestStageAdapter
from factory.dataset.runtime.ports import DatasetStagePort
from factory.dataset.runtime.validation import dispatch_validator

CAN_DATA_DIR = Path("/Users/danielrodrigo/Downloads/CAN Data")
MF4_FIXTURE = CAN_DATA_DIR / "00000001-6A0B6FCD.MF4"
DBC_FIXTURE = CAN_DATA_DIR / "dbc" / "toyota_legacy_combined.dbc"

REQUIRED_FIELDS = {
    "timestamp_ns",
    "vehicle_id",
    "trip_id",
    "bus_name",
    "arbitration_id",
    "is_extended",
    "is_fd",
    "dlc",
    "data_bytes",
    "frame_type",
    "error_state",
    "source_ecu",
    "capture_source",
    "decoded_signals",
    "dbc_message_name",
}


def _adapter() -> CanIngestStageAdapter:
    if not MF4_FIXTURE.exists() or not DBC_FIXTURE.exists():
        pytest.skip(f"MF4/DBC fixtures not found under {CAN_DATA_DIR}")
    return CanIngestStageAdapter(dbc_path=str(DBC_FIXTURE))


def _records(adapter: CanIngestStageAdapter) -> list[dict]:
    return list(
        adapter.execute(
            [],
            {
                "mf4_paths": [str(MF4_FIXTURE)],
                "dbc_path": str(DBC_FIXTURE),
            },
        )
    )


def test_satisfies_dataset_stage_port() -> None:
    """The adapter must implement the runtime stage port protocol contract."""
    adapter = _adapter()
    # The Protocol is not runtime_checkable, so we assert on the surface
    # rather than isinstance. Same guarantees for our purposes.
    assert callable(getattr(adapter, "execute", None))
    assert isinstance(adapter.name, str) and adapter.name
    assert isinstance(adapter.stage_version, str) and adapter.stage_version
    assert "mf4_paths" in adapter.allowed_config
    assert "dbc_path" in adapter.allowed_config
    # DatasetStagePort exists and our class has all the required attributes.
    assert hasattr(DatasetStagePort, "execute")


def test_parses_single_mf4_with_expected_frame_count() -> None:
    """The test fixture should yield exactly 9936 data frames (per data dictionary)."""
    records = _records(_adapter())
    assert len(records) == 9936


def test_decoded_signal_names_appear_for_known_id() -> None:
    """Arbitration ID 0x2C1 must decode to ENG1S01 with all 13 DBC signals."""
    records = _records(_adapter())
    eng1s01 = [r for r in records if r["arbitration_id"] == "0x2C1"]
    assert eng1s01, "Expected at least one frame with arbitration_id 0x2C1"

    sample = eng1s01[0]
    assert sample["dbc_message_name"] == "ENG1S01"
    assert sample["source_ecu"] == "CGW"
    assert sample["decoded_signals"] is not None
    assert "ETCSFB" in sample["decoded_signals"]
    assert "ENG01SUM" in sample["decoded_signals"]
    # The DBC defines exactly 13 signals for ENG1S01.
    assert len(sample["decoded_signals"]) == 13


def test_raw_bytes_for_unknown_id() -> None:
    """Arbitration IDs absent from the DBC must fall back to raw hex bytes."""
    records = _records(_adapter())
    raw = [r for r in records if r["decoded_signals"] is None]
    assert raw, "Expected at least one frame with no DBC match"

    sample = raw[0]
    assert sample["dbc_message_name"] is None
    assert sample["source_ecu"] is None
    # data_bytes must be a valid hex string of even length.
    assert isinstance(sample["data_bytes"], str)
    assert len(sample["data_bytes"]) % 2 == 0
    bytes.fromhex(sample["data_bytes"])  # raises on invalid hex


def test_every_record_has_required_fields() -> None:
    """Every yielded record must carry the canonical can_frame schema fields."""
    records = _records(_adapter())
    assert records
    for record in records:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record missing fields: {missing} -> {record}"
        assert record["capture_source"] == "mf4"
        assert record["frame_type"] == "data"
        assert record["error_state"] == "normal"
        assert record["trip_id"] == MF4_FIXTURE.stem
        assert record["vehicle_id"] == "local"
        assert isinstance(record["timestamp_ns"], int)
        assert record["timestamp_ns"] > 0
        assert record["arbitration_id"].startswith("0x")
        assert record["bus_name"].startswith("CAN")
        assert isinstance(record["dlc"], int)
        assert 0 <= record["dlc"] <= 8


def test_rejects_unknown_configuration_keys() -> None:
    """The adapter should fail closed on unsupported config keys."""
    adapter = _adapter()
    with pytest.raises(ValueError, match="Unsupported can_ingest configuration"):
        list(adapter.execute([], {"mf4_paths": ["x"], "dbc_path": "y", "rogue": True}))


def test_requires_mf4_paths_config() -> None:
    """An empty mf4_paths list is a contract violation."""
    adapter = _adapter()
    with pytest.raises(ValueError, match="mf4_paths"):
        list(adapter.execute([], {"dbc_path": "x"}))


def test_dispatch_validator_accepts_can_frame_records() -> None:
    """The dataset brick's can_frame validator must accept our canonical records."""
    records = _records(_adapter())[:5]
    validated: Iterator = dispatch_validator(records, record_schema="can_frame")
    materialized = list(validated)
    assert len(materialized) == 5
    assert materialized[0]["arbitration_id"] in {"0x442", "0x620", "0x440", "0x621", "0x2C1"}
