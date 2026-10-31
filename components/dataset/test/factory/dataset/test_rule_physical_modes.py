"""Tests for the physical failure-mode primitives in :mod:`_physical_failure_modes`.

These tests exercise the eight physically-plausible fault modes that
replace the legacy mathematically-perfect rule modes. Each mode is
called directly via :data:`PHYSICAL_RULE_DISPATCH` so we can assert on
per-mode behavior without going through the full
:func:`inject_failures` orchestrator.

The 8 modes covered:

* ``signal_drift``       — slow bias + pink noise on one signal
* ``drop_to_zero``       — 1-2 signals clamped near their physical minimum
* ``out_of_sequence``    — copy signal values from one frame to the next
* ``sensor_degradation`` — Gumbel-distributed right-skewed noise cluster
* ``ecu_timeout``        — target signal key is REMOVED for 2/3 of window
* ``signal_freeze``      — held to base value ± quantisation LSB
* ``spike_noise``        — exponential-decay ringing across multiple frames
* ``correlation_break``  — two signals drift toward independent noise
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from factory.dataset.runtime.adapters._physical_failure_modes import (
    PHYSICAL_RULE_DISPATCH,
    _clamp,
    _validate_physical_plausibility,
)


# All 8 mode names — keep this in sync with PHYSICAL_RULE_DISPATCH.
ALL_MODES: tuple[str, ...] = (
    "signal_drift",
    "drop_to_zero",
    "out_of_sequence",
    "sensor_degradation",
    "ecu_timeout",
    "signal_freeze",
    "spike_noise",
    "correlation_break",
)


def _make_records(n: int = 100) -> list[dict]:
    """Build a 100-record stream with three decoded signals."""
    return [
        {
            "timestamp_ns": i * 1_000_000,
            "arbitration_id": "0x25",
            "decoded_signals": {
                "A": float(i) + 100.0,
                "B": float(i) * 2.0 + 50.0,
                "C": 100.0 + float(i % 5),
            },
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for i in range(n)
    ]


def _signal_meta() -> dict[str, dict[str, float]]:
    """Per-signal min/max/std used to constrain injected values."""
    return {
        "A": {"min": 0.0, "max": 1000.0, "std": 10.0},
        "B": {"min": 0.0, "max": 2000.0, "std": 20.0},
        "C": {"min": 0.0, "max": 500.0, "std": 5.0},
    }


def _run_mode(mode: str, records: list[dict], *, signal_meta) -> None:
    """Invoke a single physical mode over the full record range."""
    handler = PHYSICAL_RULE_DISPATCH[mode]
    rng = np.random.default_rng(42)
    handler(records, 0, len(records), rng, signal_meta)


# --- 1. Dispatch integrity ---------------------------------------------------


def test_all_modes_import_correctly():
    """All 8 documented modes must be present in the dispatch table."""
    for mode in ALL_MODES:
        assert mode in PHYSICAL_RULE_DISPATCH, (
            f"Mode {mode!r} missing from PHYSICAL_RULE_DISPATCH"
        )
    # Belt-and-braces: the dispatch table should contain exactly these modes.
    assert set(PHYSICAL_RULE_DISPATCH.keys()) == set(ALL_MODES)


# --- 2-3. signal_meta plumbing ----------------------------------------------


@pytest.mark.parametrize("mode", ALL_MODES)
def test_all_modes_accept_signal_meta(mode: str):
    """Every mode must run cleanly with a populated signal_meta dict."""
    records = _make_records(100)
    _run_mode(mode, records, signal_meta=_signal_meta())
    # No exception, no NaN — basic sanity.
    for r in records:
        sigs = r["decoded_signals"]
        for v in sigs.values():
            assert not math.isnan(float(v)), f"Mode {mode} produced NaN"


@pytest.mark.parametrize("mode", ALL_MODES)
def test_all_modes_work_without_signal_meta(mode: str):
    """Every mode must run cleanly with signal_meta=None."""
    records = _make_records(100)
    _run_mode(mode, records, signal_meta=None)
    for r in records:
        sigs = r["decoded_signals"]
        for v in sigs.values():
            assert not math.isnan(float(v)), f"Mode {mode} produced NaN"


# --- 4. Final-pass clamp -----------------------------------------------------


def test_validate_physical_plausibility_clamps():
    """Values outside [min, max] must be clamped back into the envelope."""
    records = _make_records(5)
    # Plant out-of-range values for signal A (max 1000) and B (max 2000).
    records[0]["decoded_signals"]["A"] = 9999.0
    records[1]["decoded_signals"]["B"] = -500.0
    records[2]["decoded_signals"]["A"] = -1.0
    records[3]["decoded_signals"]["B"] = 1e9
    # A value already in range should be untouched.
    records[4]["decoded_signals"]["A"] = 500.0

    _validate_physical_plausibility(records, 0, 5, _signal_meta())

    assert records[0]["decoded_signals"]["A"] == 1000.0
    assert records[1]["decoded_signals"]["B"] == 0.0
    assert records[2]["decoded_signals"]["A"] == 0.0
    assert records[3]["decoded_signals"]["B"] == 2000.0
    assert records[4]["decoded_signals"]["A"] == 500.0

    # Direct _clamp exercise: open-ended meta must leave the value alone.
    assert _clamp(42.0, {"min": None, "max": None, "std": 1.0}) == 42.0
    # And a fully bounded meta clamps to the min bound.
    assert _clamp(-5.0, {"min": 0.0, "max": 10.0, "std": 1.0}) == 0.0


# --- 5-8. Per-mode physical invariants --------------------------------------


def test_signal_drift_is_not_linear():
    """Drift adds pink (cumulative) noise on top of a slow ramp — verify
    the residual against a perfect linear fit is non-trivial for the
    signal the mode actually picks."""
    records = _make_records(100)
    meta = _signal_meta()
    # Snapshot the original values so we can detect which signal the
    # mode actually mutated (it picks one uniformly at random).
    originals = {sig: np.array([r["decoded_signals"][sig] for r in records])
                 for sig in ("A", "B", "C")}

    rng = np.random.default_rng(42)
    PHYSICAL_RULE_DISPATCH["signal_drift"](
        records, 0, len(records), rng, meta,
    )

    # For each signal, fit a straight line to the mutated series and
    # measure the residual RMS. Pink noise over 100 frames should push
    # the chosen signal's residual well above the floating-point floor.
    x = np.arange(len(records), dtype=float)
    found_noisy = False
    for sig in ("A", "B", "C"):
        series = np.array([r["decoded_signals"][sig] for r in records])
        slope, intercept = np.polyfit(x, series, 1)
        fitted = slope * x + intercept
        residual_rms = float(np.sqrt(np.mean((series - fitted) ** 2)))
        # Confirm the signal was actually mutated before judging noise.
        max_dev = float(np.max(np.abs(series - originals[sig])))
        if max_dev < 0.01:
            continue  # mode didn't pick this signal
        assert residual_rms > 0.1, (
            f"signal_drift on {sig!r} should be noisy, "
            f"got residual_rms={residual_rms}"
        )
        found_noisy = True
    assert found_noisy, "signal_drift must mutate at least one signal"


def test_drop_to_zero_is_partial():
    """``drop_to_zero`` picks 1-2 signals to clamp, not all of them."""
    records = _make_records(100)
    _run_mode("drop_to_zero", records, signal_meta=_signal_meta())

    # Count how many of the 3 signals were driven to their minimum.
    floored_counts = {sig: 0 for sig in ("A", "B", "C")}
    for r in records:
        for sig in floored_counts:
            v = r["decoded_signals"][sig]
            if v <= 0.05:  # near the (jittered) floor of 0
                floored_counts[sig] += 1

    floored_signals = sum(1 for c in floored_counts.values() if c > 50)
    assert 1 <= floored_signals <= 2, (
        f"drop_to_zero should affect 1-2 signals, floored={floored_counts}"
    )


def test_out_of_sequence_preserves_timestamps():
    """``out_of_sequence`` mutates signal values only — never timestamps."""
    records = _make_records(100)
    original_ts = [r["timestamp_ns"] for r in records]
    _run_mode("out_of_sequence", records, signal_meta=None)
    # Timestamps must be byte-identical and strictly monotonic.
    assert [r["timestamp_ns"] for r in records] == original_ts
    timestamps = np.array([r["timestamp_ns"] for r in records])
    diffs = np.diff(timestamps)
    assert (diffs > 0).all(), "Timestamps must remain strictly increasing"


def test_spike_produces_ringing():
    """``spike_noise`` injects a primary spike with exponential decay,
    so several neighbouring frames should also be visibly affected."""
    records = _make_records(100)
    # Snapshot baselines so we can measure deviation per record.
    baselines = {
        sig: np.array([r["decoded_signals"][sig] for r in records])
        for sig in ("A", "B", "C")
    }
    _run_mode("spike_noise", records, signal_meta=_signal_meta())

    # Per-record max absolute deviation from baseline across all signals.
    max_dev = np.zeros(len(records))
    for i, r in enumerate(records):
        for sig in ("A", "B", "C"):
            dev = abs(r["decoded_signals"][sig] - float(baselines[sig][i]))
            if dev > max_dev[i]:
                max_dev[i] = dev

    # A pure single-frame spike would leave only one record elevated.
    # With exponential ringing, we expect a clear cluster of affected frames.
    affected = int((max_dev > 0.5).sum())
    assert affected >= 3, (
        f"spike_noise should ring across multiple frames, "
        f"got only {affected} affected frames"
    )


# --- 9. Numeric hygiene -----------------------------------------------------


@pytest.mark.parametrize("mode", ALL_MODES)
def test_modes_never_produce_nan(mode: str):
    """No mode may emit NaN — even with edge-case signal_meta."""
    records = _make_records(100)
    # Stress with mixed meta: some signals bounded, some unbounded,
    # some with std=0. The clamp layer should still keep values finite.
    meta = {
        "A": {"min": 0.0, "max": 1000.0, "std": 10.0},
        "B": {"min": None, "max": None, "std": 0.0},
        "C": {"min": -50.0, "max": 50.0, "std": 1e-9},
    }
    _run_mode(mode, records, signal_meta=meta)
    for r in records:
        for sig, v in r["decoded_signals"].items():
            assert not math.isnan(float(v)), (
                f"Mode {mode} produced NaN for signal {sig!r}"
            )
            assert not math.isinf(float(v)), (
                f"Mode {mode} produced Inf for signal {sig!r}"
            )
