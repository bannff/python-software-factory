"""Contract tests for the can_synthesize stage adapter.

Chains ``CanIngestStageAdapter`` → ``CanProfileStageAdapter`` →
``CanSynthesizeStageAdapter`` against the real MF4 fixture so the SDV
fit, constraint clamping, and failure-mode labels are all exercised
end-to-end on actual decoded signals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.can_ingest import CanIngestStageAdapter
from factory.dataset.runtime.adapters.can_profile import CanProfileStageAdapter
from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
from factory.dataset.runtime.ports import DatasetStagePort

CAN_DATA_DIR = Path("/Users/danielrodrigo/Downloads/CAN Data")
MF4_FIXTURE = CAN_DATA_DIR / "00000001-6A0B6FCD.MF4"
DBC_FIXTURE = CAN_DATA_DIR / "dbc" / "toyota_legacy_combined.dbc"

REQUIRED_FIELDS = {
    "timestamp_ns", "vehicle_id", "trip_id", "bus_name", "arbitration_id",
    "is_extended", "is_fd", "dlc", "data_bytes", "frame_type", "error_state",
    "source_ecu", "capture_source", "decoded_signals", "dbc_message_name",
    "is_failure", "failure_mode", "failure_timestamp_ns",
}


def _ingested_records() -> list[dict]:
    if not (MF4_FIXTURE.exists() and DBC_FIXTURE.exists()):
        pytest.skip(f"MF4/DBC fixtures not found under {CAN_DATA_DIR}")
    ingest = CanIngestStageAdapter(dbc_path=str(DBC_FIXTURE))
    return list(
        ingest.execute(
            [],
            {"mf4_paths": [str(MF4_FIXTURE)], "dbc_path": str(DBC_FIXTURE)},
        )
    )


def _synthesize(
    records: list[dict],
    *,
    multiplier: int = 10,
    failure_rate: float = 0.1,
    seed: int = 42,
    failure_modes: tuple[str, ...] | None = None,
) -> tuple[list[dict], dict]:
    schema = list(CanProfileStageAdapter().execute(records, {}))[0]
    config: dict = {
        "multiplier": multiplier, "failure_rate": failure_rate, "seed": seed,
        "constraint_schema": schema,
    }
    if failure_modes is not None:
        config["failure_modes"] = list(failure_modes)
    return list(CanSynthesizeStageAdapter().execute(records, config)), schema


# --- Adapter surface -------------------------------------------------------


def test_satisfies_dataset_stage_port() -> None:
    adapter = CanSynthesizeStageAdapter()
    assert callable(getattr(adapter, "execute", None))
    assert adapter.name == "can_synthesize"
    assert adapter.stage_version
    assert {"multiplier", "failure_rate", "constraint_schema"} <= adapter.allowed_config
    assert hasattr(DatasetStagePort, "execute")


def test_rejects_unknown_configuration_keys() -> None:
    with pytest.raises(ValueError, match="Unsupported can_synthesize configuration"):
        list(CanSynthesizeStageAdapter().execute(_ingested_records(), {"multiplier": 2, "rogue": True}))


def test_rejects_invalid_multiplier_and_failure_rate() -> None:
    records = _ingested_records()
    with pytest.raises(ValueError, match="multiplier"):
        list(CanSynthesizeStageAdapter().execute(records, {"multiplier": 0}))
    with pytest.raises(ValueError, match="failure_rate"):
        list(CanSynthesizeStageAdapter().execute(records, {"failure_rate": 1.5}))


def test_empty_records_produces_empty_output() -> None:
    assert list(CanSynthesizeStageAdapter().execute(iter([]), {"multiplier": 5})) == []


# --- End-to-end behavior ---------------------------------------------------


def test_synthesize_yields_approximately_nx_decoded_input() -> None:
    """With multiplier=10, output should be ~10x the decoded input count."""
    records = _ingested_records()
    decoded = [r for r in records if r.get("decoded_signals")]
    synth, _ = _synthesize(records, multiplier=10)
    assert synth
    assert abs(len(synth) - 10 * len(decoded)) <= 0.05 * len(synth)


def test_multiplier_one_yields_one_record_per_decoded_frame() -> None:
    """Edge case: multiplier=1 should produce exactly N_decoded records."""
    records = _ingested_records()
    decoded = [r for r in records if r.get("decoded_signals")]
    synth, _ = _synthesize(records, multiplier=1)
    assert len(synth) == len(decoded)


def test_every_synthetic_record_has_required_fields() -> None:
    synth, _ = _synthesize(_ingested_records(), multiplier=2)
    assert synth
    for r in synth:
        missing = REQUIRED_FIELDS - set(r.keys())
        assert not missing, f"Missing fields: {missing} -> {r}"
        assert r["capture_source"] == "synthetic"
        assert r["is_failure"] in (0, 1)
        assert (r["failure_mode"] is None) == (r["is_failure"] == 0)
        assert (r["failure_timestamp_ns"] is None) == (r["is_failure"] == 0)
        assert isinstance(r["timestamp_ns"], int)
        assert r["arbitration_id"].startswith("0x")
        assert r["decoded_signals"] is not None


def test_synthetic_signals_within_constraint_bounds() -> None:
    """Healthy records must respect the profile's [min, max] (failures exempt)."""
    synth, schema = _synthesize(_ingested_records(), multiplier=2, failure_rate=0.0)
    violations = 0
    for r in synth:
        signals_meta = (schema["can_ids"].get(r["arbitration_id"]) or {}).get("signals") or {}
        for name, value in (r.get("decoded_signals") or {}).items():
            meta = signals_meta.get(name) or {}
            lo, hi = meta.get("min"), meta.get("max")
            if lo is not None and value < lo - 1e-6:
                violations += 1
            if hi is not None and value > hi + 1e-6:
                violations += 1
    assert violations == 0, f"Found {violations} out-of-bounds values"


def test_different_seeds_produce_different_outputs() -> None:
    """Compare 0x2C1 (continuous signals) — binary signals collapse across seeds."""
    records = _ingested_records()
    a, _ = _synthesize(records, multiplier=2, seed=1)
    b, _ = _synthesize(records, multiplier=2, seed=2)

    def _first_eng1s01(items):
        for r in items:
            if r.get("arbitration_id") == "0x2C1":
                sigs = r.get("decoded_signals") or {}
                if any(abs(v) > 1e-3 for v in sigs.values()):
                    return r
        return None

    ra, rb = _first_eng1s01(a), _first_eng1s01(b)
    assert ra is not None and rb is not None
    assert ra["decoded_signals"] != rb["decoded_signals"]


def test_failure_rate_controls_fraction_of_failures() -> None:
    records = _ingested_records()
    low, _ = _synthesize(records, multiplier=2, failure_rate=0.02, seed=7)
    high, _ = _synthesize(records, multiplier=2, failure_rate=0.30, seed=7)
    fail_low = sum(1 for r in low if r["is_failure"])
    fail_high = sum(1 for r in high if r["is_failure"])
    assert fail_high > fail_low
    # 3-5 record windows amplify the rate; bound loosely on the high side.
    assert fail_low <= 0.5 * len(low)
    assert fail_high <= 0.8 * len(high)


def test_failure_labels_match_documented_modes() -> None:
    synth, _ = _synthesize(_ingested_records(), multiplier=2, failure_rate=0.20, seed=3)
    allowed = {"signal_drift", "drop_to_zero", "out_of_sequence"}
    for r in synth:
        if r["is_failure"]:
            assert r["failure_mode"] in allowed
            assert r["failure_timestamp_ns"] == r["timestamp_ns"]


def test_decoded_signals_none_records_are_skipped() -> None:
    """Records with no DBC match must not appear in the synthetic stream."""
    records = _ingested_records()
    non_decoded_ids = {r["arbitration_id"] for r in records if not r.get("decoded_signals")}
    if not non_decoded_ids:
        pytest.skip("No non-decoded records in the fixture")
    synth, _ = _synthesize(records, multiplier=2)
    assert {r["arbitration_id"] for r in synth}.isdisjoint(non_decoded_ids)
