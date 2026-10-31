"""Physically-plausible CAN failure modes (Epic 3 v2).

Replaces the mathematically-perfect rule modes in
:mod:`_rule_failure_helpers` with corruptions that look like real
bus faults. The legacy modes zero every signal, swap timestamps, or
inject exactly-5σ spikes — patterns a model can detect by the
injection method itself rather than by the underlying failure
(observed AUROC ~0.5). These v2 modes respect per-signal metadata
(min/max/std), use bounded magnitude, and only mutate a subset of
signals per event. Modes: signal_drift, drop_to_zero, out_of_sequence,
sensor_degradation, ecu_timeout, signal_freeze, spike_noise,
correlation_break.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _meta(signal_meta, name):
    if not signal_meta:
        return {"min": None, "max": None, "std": 1.0}
    return signal_meta.get(name) or {"min": None, "max": None, "std": 1.0}


def _clamp(value, meta):
    lo, hi = meta.get("min"), meta.get("max")
    if lo is not None:
        value = max(value, float(lo))
    if hi is not None:
        value = min(value, float(hi))
    return value


def _names(records, start, end):
    for r in records[start:end]:
        sigs = r.get("decoded_signals")
        if sigs:
            return sorted(sigs.keys())
    return []


def _validate_physical_plausibility(records, start, end, signal_meta):
    """Final-pass clamp: guarantee every value stays within [min, max]."""
    if not signal_meta:
        return
    for rec in records[start:end]:
        sigs = rec.get("decoded_signals")
        if not sigs:
            continue
        for k in list(sigs):
            m = signal_meta.get(k)
            if m:
                sigs[k] = _clamp(float(sigs[k]), m)
# --- mode functions ---------------------------------------------------------
def _physical_signal_drift(records, start, end, rng, signal_meta=None):
    names = _names(records, start, end)
    if not names: return
    sig = names[int(rng.integers(0, len(names)))]
    m = _meta(signal_meta, sig)
    n = max(end - start, 1)
    # Pink noise: cumulative sum of white noise (Voss-McCartney trick).
    pink = np.cumsum(rng.normal(0.0, max(abs(float(m.get("std") or 1.0)) * 0.02, 1e-6), n))
    for i, rec in enumerate(records[start:end]):
        s = rec.get("decoded_signals")
        if not s or sig not in s: continue
        drift = float(s[sig]) * (1.0 + rng.uniform(0.05, 0.40) * (i / n))
        s[sig] = _clamp(drift + float(pink[i]), m)
def _physical_drop_to_zero(records, start, end, rng, signal_meta=None):
    names = _names(records, start, end)
    if not names: return
    for sig in rng.choice(names, size=int(rng.integers(1, min(3, len(names) + 1))), replace=False):
        m = _meta(signal_meta, sig)
        # Floor near (not exactly) the signal's physical minimum, ±5% jitter.
        floor = float(m.get("min") or 0.0) * float(rng.uniform(0.95, 1.05))
        for rec in records[start:end]:
            s = rec.get("decoded_signals")
            if s and sig in s: s[sig] = _clamp(floor, m)
def _physical_out_of_sequence(records, start, end, rng, signal_meta=None):
    # Copy signal values only — never touch timestamps (stream stays monotonic).
    if end - start < 2: return
    src_off = int(rng.integers(0, end - start - 1))
    src = records[start + src_off].get("decoded_signals")
    dst = records[start + src_off + 1].get("decoded_signals")
    if not src or dst is None: return
    for k, v in src.items():
        dst[k] = _clamp(float(v), _meta(signal_meta, k))
def _physical_sensor_degradation(records, start, end, rng, signal_meta=None):
    # Gumbel (right-skewed) models sensor aging better than symmetric
    # Gaussian — reads high more often than low, only intermittently.
    names = _names(records, start, end)
    if len(names) < 2: return
    cluster = list(rng.choice(names, size=int(rng.integers(2, min(4, len(names)) + 1)), replace=False))
    for rec in records[start:end]:
        s = rec.get("decoded_signals")
        if not s or rng.random() >= 0.6: continue
        for sig in cluster:
            if sig not in s: continue
            m = _meta(signal_meta, sig)
            std = max(abs(float(m.get("std") or 1.0)), 1e-6)
            s[sig] = _clamp(float(s[sig]) + float(rng.gumbel(0.0, std * rng.uniform(0.5, 3.0))), m)
def _physical_ecu_timeout(records, start, end, rng, signal_meta=None):
    # Target reappears at 2/3 with a fresh rng.uniform(min, max) value
    # — modelling the ECU re-acquiring bus arbitration after a brown-out.
    n = end - start
    if n < 3: return
    names = _names(records, start, end)
    if not names: return
    target = names[int(rng.integers(0, len(names)))]
    others = [x for x in names if x != target]
    resume = start + (n * 2) // 3
    for i, rec in enumerate(records[start:end]):
        s = rec.get("decoded_signals")
        if not s: continue
        if i < resume - start:
            s.pop(target, None)
            if others and rng.random() < 0.3:
                s.pop(others[int(rng.integers(0, len(others)))], None)
        elif i == resume - start:
            m = _meta(signal_meta, target)
            s[target] = float(rng.uniform(float(m.get("min") or 0.0), float(m.get("max") or 100.0)))
def _physical_signal_freeze(records, start, end, rng, signal_meta=None):
    # 12-bit ADC over [min, max] has LSB (max-min)/4096; a stuck
    # sensor still reports quantisation noise. 10% wider glitch.
    t = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not t or not t["decoded_signals"]: return
    sig = str(rng.choice(sorted(t["decoded_signals"].keys())))
    m = _meta(signal_meta, sig)
    lo, hi = float(m.get("min") or 0.0), float(m.get("max") or 1.0)
    lsb = (hi - lo) / 4096.0 if hi > lo else 1e-6
    base = float(t["decoded_signals"].get(sig, 0.0))
    std = max(abs(float(m.get("std") or lsb * 5.0)), lsb, 1e-9)
    for rec in records[start:end]:
        s = rec.get("decoded_signals")
        if not s or sig not in s: continue
        if rng.random() < 0.1:
            v = base + float(rng.normal(0.0, 0.5 * std))
        else:
            v = base + (1.0 if rng.random() < 0.5 else -1.0) * int(rng.integers(1, 4)) * lsb
        s[sig] = _clamp(v, m)
def _physical_spike_noise(records, start, end, rng, signal_meta=None):
    # Peak at frame i; decays exp(-rate*|t-i|). Primary carries full
    # magnitude; cluster neighbours get smaller shares with random
    # sign — models an EMI burst coupling into adjacent lines.
    names = _names(records, start, end)
    if len(names) < 2: return
    cluster = list(rng.choice(names, size=int(rng.integers(2, min(4, len(names)) + 1)), replace=False))
    n = end - start
    primary_i = int(rng.integers(0, n))
    std_p = max(abs(float(_meta(signal_meta, cluster[0]).get("std") or 1.0)), 1e-6)
    mag = float(rng.uniform(2.0, 8.0)) * std_p
    rate = float(rng.uniform(0.5, 1.5))
    for j, sig in enumerate(cluster):
        m = _meta(signal_meta, sig)
        scale = 1.0 / (1.0 + 0.5 * j)
        sign = 1.0 if (j == 0 or rng.random() < 0.5) else -1.0
        for i, rec in enumerate(records[start:end]):
            s = rec.get("decoded_signals")
            if not s or sig not in s: continue
            decay = float(np.exp(-rate * abs(i - primary_i)))
            s[sig] = _clamp(float(s[sig]) + sign * mag * scale * decay, m)
def _physical_correlation_break(records, start, end, rng, signal_meta=None):
    # Linear ramp simulates a connector losing its shared ground ref.
    t = next((r for r in records[start:end] if r.get("decoded_signals")), None)
    if not t or not t["decoded_signals"]: return
    names = sorted(t["decoded_signals"].keys())
    if len(names) < 2: return
    a, b = (str(x) for x in rng.choice(names, size=2, replace=False))
    ma, mb = _meta(signal_meta, a), _meta(signal_meta, b)
    sa = max(abs(float(ma.get("std") or 1.0)), 1e-6)
    sb = max(abs(float(mb.get("std") or 1.0)), 1e-6)
    n = end - start
    for i, rec in enumerate(records[start:end]):
        s = rec.get("decoded_signals")
        if not s or a not in s or b not in s: continue
        alpha = (i + 1) / n
        s[a] = _clamp((1.0 - alpha) * float(s[a]) + alpha * float(rng.normal(0.0, sa * 2.0)), ma)
        s[b] = _clamp((1.0 - alpha) * float(s[b]) + alpha * float(rng.normal(0.0, sb * 2.0)), mb)
PHYSICAL_RULE_DISPATCH: dict[str, Any] = {
    "signal_drift": _physical_signal_drift,
    "drop_to_zero": _physical_drop_to_zero,
    "out_of_sequence": _physical_out_of_sequence,
    "sensor_degradation": _physical_sensor_degradation,
    "ecu_timeout": _physical_ecu_timeout,
    "signal_freeze": _physical_signal_freeze,
    "spike_noise": _physical_spike_noise,
    "correlation_break": _physical_correlation_break,
}
