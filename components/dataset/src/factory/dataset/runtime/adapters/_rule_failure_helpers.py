"""Rule-based failure-mode helpers (Epic 3, eight fault modes).

Extracted from :mod:`failure_injection` to keep that orchestrator under
the 200-LOC factory ceiling. Nothing here is part of the public brick
surface; the helpers may change without notice.

The eight modes mirror the original fault catalog:

* ``signal_drift``       — gradually shift one signal by +20% across a window.
* ``drop_to_zero``       — zero every signal in a 3-5 frame window.
* ``out_of_sequence``    — swap the timestamps of two adjacent frames.
* ``sensor_degradation`` — ramp noise from 0 to 3x normal over N frames.
* ``ecu_timeout``        — ECU stops transmitting throughout the window.
* ``signal_freeze``      — signal stuck at last reading for N frames.
* ``spike_noise``        — EMI-induced single-frame ±5σ spike.
* ``correlation_break``  — coupled signals decouple (swap values).
"""

from __future__ import annotations

from typing import Any

import numpy as np


_ALL_MODES: tuple[str, ...] = (
    "signal_drift", "drop_to_zero", "out_of_sequence",
    "sensor_degradation", "ecu_timeout", "signal_freeze",
    "spike_noise", "correlation_break",
)
_DEFAULT_MODES: tuple[str, ...] = _ALL_MODES  # Use all 8 modes by default


def _apply_drift(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    rng: np.random.Generator,
) -> None:
    """Linearly drift one signal by +20% across ``[start, end)``."""
    if end - start < 2:
        return
    target = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not target or not target["decoded_signals"]:
        return
    signal = str(rng.choice(sorted(target["decoded_signals"].keys())))
    span = end - start
    for i, rec in enumerate(records[start:end]):
        signals = rec.get("decoded_signals")
        if signals and signal in signals:
            signals[signal] = float(signals[signal]) * (
                1.0 + 0.2 * ((i + 1) / span)
            )


def _apply_drop_to_zero(
    records: list[dict[str, Any]], start: int, end: int,
) -> None:
    """Zero every signal in ``[start, end)``."""
    for r in records[start:end]:
        r["decoded_signals"] = {
            k: 0.0 for k in (r.get("decoded_signals") or {})
        }


def _apply_out_of_sequence(
    records: list[dict[str, Any]], start: int, end: int,
) -> None:
    """Swap the timestamps of two adjacent frames in the window."""
    if end - start < 2:
        return
    a, b = records[start], records[start + 1]
    a["timestamp_ns"], b["timestamp_ns"] = (
        b["timestamp_ns"],
        a["timestamp_ns"],
    )


def _apply_degradation(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    rng: np.random.Generator,
) -> None:
    """Ramp Gaussian noise from 0 to 3x signal std across the window."""
    target = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not target or not target["decoded_signals"]:
        return
    signal = str(rng.choice(sorted(target["decoded_signals"].keys())))
    base_vals = [r["decoded_signals"][signal] for r in records[start:end]
                 if r.get("decoded_signals") and signal in r["decoded_signals"]]
    if len(base_vals) < 2:
        return
    std = float(np.std(base_vals)) or 1.0
    span = end - start
    for i, rec in enumerate(records[start:end]):
        sigs = rec.get("decoded_signals")
        if sigs and signal in sigs:
            noise_scale = 3.0 * std * ((i + 1) / span)
            sigs[signal] = float(sigs[signal]) + float(rng.normal(0, noise_scale))


def _apply_ecu_timeout(
    records: list[dict[str, Any]],
    start: int,
    end: int,
) -> None:
    """Zero every existing signal throughout the timeout window."""
    _apply_drop_to_zero(records, start, end)


def _apply_signal_freeze(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    rng: np.random.Generator,
) -> None:
    """Hold one signal at its stable value immediately before the window."""
    target = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not target or not target["decoded_signals"]:
        return
    signal = str(rng.choice(sorted(target["decoded_signals"].keys())))
    event_start = records[start].get("decoded_signals") or {}
    if signal not in event_start:
        return
    predecessor = records[start - 1].get("decoded_signals") or {} if start else {}
    frozen_value = predecessor.get(signal, event_start[signal])
    for r in records[start:end]:
        sigs = r.get("decoded_signals")
        if sigs and signal in sigs:
            sigs[signal] = frozen_value


def _apply_spike(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    rng: np.random.Generator,
) -> None:
    """Inject a single-frame ±5σ spike on one signal."""
    idx = int(rng.integers(start, end))
    rec = records[idx]
    sigs = rec.get("decoded_signals")
    if not sigs:
        return
    signal = str(rng.choice(sorted(sigs.keys())))
    base = float(sigs[signal])
    sigs[signal] = base + float(rng.choice([-1, 1])) * 5.0 * abs(base or 1.0)


def _apply_correlation_break(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    rng: np.random.Generator,
) -> None:
    """Swap values between two correlated signals to break coupling."""
    target = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not target or not target["decoded_signals"]:
        return
    names = sorted(target["decoded_signals"].keys())
    if len(names) < 2:
        return
    a, b = rng.choice(names, size=2, replace=False)
    for r in records[start:end]:
        sigs = r.get("decoded_signals")
        if sigs and a in sigs and b in sigs:
            sigs[a], sigs[b] = float(sigs[b]), float(sigs[a])


_RULE_DISPATCH: dict[str, Any] = {
    "signal_drift": _apply_drift,
    "drop_to_zero": _apply_drop_to_zero,
    "out_of_sequence": _apply_out_of_sequence,
    "sensor_degradation": _apply_degradation,
    "ecu_timeout": _apply_ecu_timeout,
    "signal_freeze": _apply_signal_freeze,
    "spike_noise": _apply_spike,
    "correlation_break": _apply_correlation_break,
}
