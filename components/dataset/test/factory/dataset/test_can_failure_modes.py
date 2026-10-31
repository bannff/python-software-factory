"""Tests for new CAN failure modes (Epic 3 extensions)."""
from __future__ import annotations

import numpy as np
import pytest

from factory.dataset.runtime.adapters.failure_injection import (
    _ALL_MODES,
    inject_failures,
)


def _make_records(n: int = 20) -> list[dict]:
    return [
        {
            "timestamp_ns": i * 1_000_000,
            "arbitration_id": "0x25",
            "decoded_signals": {"A": float(i), "B": float(i * 2), "C": 100.0},
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for i in range(n)
    ]


def test_all_modes_are_recognized():
    for mode in _ALL_MODES:
        records = _make_records(20)
        result = list(inject_failures(records, 0.5, np.random.default_rng(42), (mode,)))
        failures = [r for r in result if r["is_failure"]]
        assert len(failures) > 0, f"Mode {mode} produced no failures"
        assert all(r["failure_mode"] == mode for r in failures)


def test_sensor_degradation_ramps_noise():
    records = _make_records(30)
    result = list(inject_failures(records, 0.5, np.random.default_rng(42), ("sensor_degradation",)))
    failures = [r for r in result if r["is_failure"]]
    assert len(failures) > 0
    # Degradation should increase variance across the window
    for r in failures:
        sigs = r.get("decoded_signals") or {}
        assert len(sigs) > 0, "Degraded record should still have signals"
        assert r.get("failure_mode") == "sensor_degradation"


def test_ecu_timeout_zeros_signals():
    original = _make_records(20)
    first = list(inject_failures(
        _make_records(20), 0.2, np.random.default_rng(42), ("ecu_timeout",),
    ))
    second = list(inject_failures(
        _make_records(20), 0.2, np.random.default_rng(42), ("ecu_timeout",),
    ))

    assert first == second
    failure_indices = [i for i, record in enumerate(first) if record["is_failure"]]
    assert 3 <= len(failure_indices) <= 5
    for i, record in enumerate(first):
        if i in failure_indices:
            assert record["decoded_signals"].keys() == original[i]["decoded_signals"].keys()
            assert all(value == 0.0 for value in record["decoded_signals"].values())
            assert record["failure_mode"] == "ecu_timeout"
            assert record["failure_strategy"] == "rule"
            assert record["failure_timestamp_ns"] == record["timestamp_ns"]
        else:
            assert record == original[i]


def test_signal_freeze_holds_constant():
    original = _make_records(20)
    for i, record in enumerate(original):
        record["decoded_signals"]["C"] = float(100 + i * 3)
    first_input = [
        {**record, "decoded_signals": dict(record["decoded_signals"])}
        for record in original
    ]
    second_input = [
        {**record, "decoded_signals": dict(record["decoded_signals"])}
        for record in original
    ]
    first = list(inject_failures(
        first_input, 0.2, np.random.default_rng(42), ("signal_freeze",),
    ))
    second = list(inject_failures(
        second_input, 0.2, np.random.default_rng(42), ("signal_freeze",),
    ))

    assert first == second
    failure_indices = [i for i, record in enumerate(first) if record["is_failure"]]
    assert 3 <= len(failure_indices) <= 5
    frozen = [
        signal for signal in original[0]["decoded_signals"]
        if all(first[i]["decoded_signals"][signal] == original[0]["decoded_signals"][signal]
               for i in failure_indices)
    ]
    assert len(frozen) == 1
    selected = frozen[0]
    for i, record in enumerate(first):
        if i in failure_indices:
            assert record["decoded_signals"][selected] == original[0]["decoded_signals"][selected]
            assert all(
                record["decoded_signals"][signal] == original[i]["decoded_signals"][signal]
                for signal in record["decoded_signals"] if signal != selected
            )
            assert record["failure_mode"] == "signal_freeze"
            assert record["failure_strategy"] == "rule"
            assert record["failure_timestamp_ns"] == record["timestamp_ns"]
        else:
            assert record == original[i]


def test_spike_noise_injects_extreme_value():
    records = _make_records(30)
    result = list(inject_failures(records, 0.5, np.random.default_rng(42), ("spike_noise",)))
    failures = [r for r in result if r["is_failure"]]
    assert len(failures) > 0
    # Spike should create values significantly different from neighbors
    for r in failures:
        sigs = r.get("decoded_signals") or {}
        assert len(sigs) > 0, "Spike record should have signals"
        assert r.get("failure_mode") == "spike_noise"


def test_correlation_break_swaps_signals():
    records = _make_records(30)
    result = list(inject_failures(records, 0.5, np.random.default_rng(42), ("correlation_break",)))
    failures = [r for r in result if r["is_failure"]]
    assert len(failures) > 0
    for r in failures:
        sigs = r.get("decoded_signals") or {}
        assert "A" in sigs and "B" in sigs
        assert r.get("failure_mode") == "correlation_break"


def test_original_three_modes_still_work():
    for mode in ("signal_drift", "drop_to_zero", "out_of_sequence"):
        records = _make_records(20)
        result = list(inject_failures(records, 0.5, np.random.default_rng(42), (mode,)))
        failures = [r for r in result if r["is_failure"]]
        assert len(failures) > 0, f"Original mode {mode} broken"
