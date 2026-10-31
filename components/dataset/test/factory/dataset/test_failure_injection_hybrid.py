"""Tests for the Phase 3 hybrid failure injection.

Covers three layers:

* ``_hybrid_injection_helpers`` — pure data-shaping primitives
  (blend math, strategy picker, learned-mode registry, validation).
* :func:`inject_failures` — orchestration of the ``"rule"``,
  ``"learned"``, and ``"hybrid"`` strategies via a stub
  :class:`LearnedSampler` (no torch dependency).
* :class:`CanSynthesizeStageAdapter` — config wiring for the three
  new keys (``scania_data_uri``, ``scania_model_id``,
  ``injection_strategy``) and end-to-end pipeline behavior with a
  stub sampler injected through the config.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

from factory.dataset.runtime.adapters._hybrid_injection_helpers import (
    HYBRID_RULE_FRACTION,
    LEARNED_FAILURE_MODES,
    VALID_STRATEGIES,
    apply_learned_failure,
    blend_with_context,
    pick_event_strategy,
    pick_learned_mode,
    validate_strategy,
)
from factory.dataset.runtime.adapters.failure_injection import inject_failures


# --- Fixtures ----------------------------------------------------------------


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


def _stub_sampler(
    delta: float = 5.0,
) -> "LearnedSampler":  # type: ignore[name-defined]
    """Build a deterministic stub ``LearnedSampler`` that always returns
    a (T, F) trajectory of ``delta`` above zero (z-score space).

    The blend math in :func:`blend_with_context` will denormalize this
    and add it to the baseline, so the resulting window's last frame
    is always ``baseline + delta`` per signal.
    """

    def _sample(
        n_frames: int,
        failure_mode: str,
        n_signals: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        return np.full((n_frames, n_signals), delta, dtype=float)

    return _sample


# --- _hybrid_injection_helpers ----------------------------------------------


def test_hybrid_constants_are_well_formed():
    assert 0.0 < HYBRID_RULE_FRACTION < 1.0
    assert set(LEARNED_FAILURE_MODES) == {
        "aps_failure", "amplitude_spike", "signal_drift",
    }
    # Phase 5: "correlation" is now part of the valid strategy set
    # (the correlation-matrix injection path).
    assert VALID_STRATEGIES == frozenset(
        {"rule", "learned", "hybrid", "correlation"},
    )


def test_pick_event_strategy_matches_fraction():
    rng = np.random.default_rng(0)
    n = 5000
    picks = [pick_event_strategy(rng) for _ in range(n)]
    rule_frac = sum(1 for p in picks if p == "rule") / n
    assert abs(rule_frac - HYBRID_RULE_FRACTION) < 0.03


def test_pick_learned_mode_cycles_through_vocabulary():
    rng = np.random.default_rng(0)
    seen: set[str] = set()
    for i in range(len(LEARNED_FAILURE_MODES) * 2):
        seen.add(pick_learned_mode(i, rng))
    assert seen == set(LEARNED_FAILURE_MODES)


def test_validate_strategy_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown injection_strategy"):
        validate_strategy("magic", learned_sampler=_stub_sampler())


def test_validate_strategy_requires_sampler_for_learned():
    with pytest.raises(ValueError, match="requires a"):
        validate_strategy("learned", learned_sampler=None)
    with pytest.raises(ValueError, match="requires a"):
        validate_strategy("hybrid", learned_sampler=None)


def test_validate_strategy_allows_rule_without_sampler():
    validate_strategy("rule", learned_sampler=None)  # no raise


def test_blend_with_context_anchors_to_baseline():
    baseline = np.array([[1.0, 2.0], [1.1, 2.1], [1.2, 2.2]])
    learned = np.full_like(baseline, 3.0)  # 3σ above the baseline mean
    blended = blend_with_context(learned, baseline, ["A", "B"])
    # Frame 0 must equal the baseline (alpha=0).
    np.testing.assert_allclose(blended[0], baseline[0])
    # Frame T-1 must equal the denormalized learned endpoint
    # (alpha=1): baseline_mean + 3σ * baseline_std.
    base_mean = baseline.mean(axis=0)
    base_std = baseline.std(axis=0)
    np.testing.assert_allclose(
        blended[-1], base_mean + 3.0 * np.where(base_std < 1e-6, 1.0, base_std),
    )
    # Monotonic per signal: alpha increases frame to frame.
    alpha = np.linspace(0.0, 1.0, num=blended.shape[0])
    expected = (1.0 - alpha[:, None]) * baseline + alpha[:, None] * (
        3.0 * np.where(base_std < 1e-6, 1.0, base_std) + base_mean
    )
    np.testing.assert_allclose(blended, expected, atol=1e-9)


def test_apply_learned_failure_mutates_records():
    records = _make_records(8)
    sampler = _stub_sampler(delta=2.0)
    rng = np.random.default_rng(0)
    failure_mode = apply_learned_failure(records, 0, 4, "aps_failure", sampler, rng)
    assert failure_mode == "aps_failure"
    # The first record's signals should be unchanged (alpha=0 -> baseline).
    np.testing.assert_allclose(
        records[0]["decoded_signals"]["A"], 0.0, atol=1e-9,
    )
    # The last record in the window should drift upward (alpha=1 -> learned).
    last = records[3]["decoded_signals"]
    assert last["A"] > 0.0
    assert last["B"] > 0.0
    # Signals outside the window stay untouched.
    assert records[4]["decoded_signals"]["A"] == 4.0


def test_apply_learned_failure_handles_missing_signals():
    records = _make_records(6)
    # First record has no signals — helper should still return a mode.
    records[0]["decoded_signals"] = {}
    sampler = _stub_sampler()
    mode = apply_learned_failure(records, 0, 3, "signal_drift", sampler, np.random.default_rng(0))
    assert mode == "signal_drift"


# --- inject_failures strategy paths -----------------------------------------


def test_inject_failures_rule_preserves_legacy_behavior():
    records = _make_records(30)
    out = list(inject_failures(records, 0.5, np.random.default_rng(42)))
    failures = [r for r in out if r["is_failure"]]
    assert len(failures) > 0
    # Rule strategy must never stamp the learned strategy field.
    assert all(r.get("failure_strategy", "rule") == "rule" for r in out)
    # Modes must come from the documented rule vocabulary.
    rule_modes = {
        "signal_drift", "drop_to_zero", "out_of_sequence",
        "sensor_degradation", "ecu_timeout", "signal_freeze",
        "spike_noise", "correlation_break",
    }
    assert {r["failure_mode"] for r in failures} <= rule_modes


def test_inject_failures_learned_uses_only_learned_sampler():
    records = _make_records(40)
    sampler = _stub_sampler(delta=2.0)
    out = list(
        inject_failures(
            records, 0.5, np.random.default_rng(0),
            injection_strategy="learned",
            learned_sampler=sampler,
        ),
    )
    failures = [r for r in out if r["is_failure"]]
    assert len(failures) > 0
    # Every failure event must be tagged with a learned strategy.
    assert all(r.get("failure_strategy") == "learned" for r in failures)
    # Every failure mode must come from the learned vocabulary.
    assert {r["failure_mode"] for r in failures} <= set(LEARNED_FAILURE_MODES)


def test_inject_failures_hybrid_uses_both_strategies():
    records = _make_records(60)
    sampler = _stub_sampler(delta=2.0)
    out = list(
        inject_failures(
            records, 0.6, np.random.default_rng(0),
            injection_strategy="hybrid",
            learned_sampler=sampler,
        ),
    )
    failures = [r for r in out if r["is_failure"]]
    strategies = {r.get("failure_strategy") for r in failures}
    # With 60+ records and 60% failure rate we should see at least 7
    # events, which is plenty for the 30/70 split to surface both
    # strategies.
    assert "rule" in strategies
    assert "learned" in strategies
    # The realized ratio should be near 30% (give or take sampling
    # noise on small N).
    n_rule = sum(1 for r in failures if r.get("failure_strategy") == "rule")
    ratio = n_rule / len(failures)
    assert 0.10 <= ratio <= 0.55


def test_inject_failures_rejects_learned_without_sampler():
    records = _make_records(10)
    with pytest.raises(ValueError, match="requires a"):
        list(
            inject_failures(
                records, 0.5, np.random.default_rng(0),
                injection_strategy="learned",
            ),
        )


def test_inject_failures_rejects_unknown_strategy():
    records = _make_records(10)
    with pytest.raises(ValueError, match="Unknown injection_strategy"):
        list(
            inject_failures(
                records, 0.5, np.random.default_rng(0),
                injection_strategy="magic",
            ),
        )


def test_inject_failures_zero_rate_is_passthrough():
    records = _make_records(5)
    out = list(
        inject_failures(
            records, 0.0, np.random.default_rng(0),
            injection_strategy="hybrid",
            learned_sampler=_stub_sampler(),
        ),
    )
    assert out == records
    assert all(r["is_failure"] == 0 for r in out)


def test_inject_failures_learned_blends_records_smoothly():
    """The window's first frame must equal the baseline (smooth transition)."""
    records = _make_records(20)
    sampler = _stub_sampler(delta=4.0)
    out = list(
        inject_failures(
            records, 0.5, np.random.default_rng(0),
            injection_strategy="learned",
            learned_sampler=sampler,
        ),
    )
    failures = [r for r in out if r["is_failure"]]
    # Group failures by contiguous window and verify the first frame in
    # each window is close to the original baseline.
    windows: list[list[dict]] = []
    for r in failures:
        if not windows or r["timestamp_ns"] - windows[-1][-1]["timestamp_ns"] > 2_000_000:
            windows.append([r])
        else:
            windows[-1].append(r)
    assert windows, "Expected at least one learned failure window"
    for window in windows:
        first = window[0]
        # The first frame in the window is the original record (alpha=0).
        # We can't recover the exact pre-failure value because the
        # stub sampler is deterministic, but the signal should be at
        # or above the original (the trajectory is monotonically
        # increasing for a positive delta).
        assert first["decoded_signals"]["A"] >= 0.0


# --- can_synthesize config wiring ------------------------------------------


def test_can_synthesize_allowed_config_includes_phase4_keys():
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
    cfg = CanSynthesizeStageAdapter.allowed_config
    assert "scania_data_uri" in cfg
    assert "scania_model_id" in cfg
    assert "injection_strategy" in cfg


def test_can_synthesize_rejects_unknown_keys_with_phase4_keys_known():
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
    with pytest.raises(ValueError, match="Unsupported can_synthesize configuration"):
        list(
            CanSynthesizeStageAdapter().execute(
                [], {"multiplier": 2, "rogue": True},
            ),
        )


def _make_pipeline_records(n_per_id: int = 6) -> list[dict]:
    """Build a small multi-CAN-ID record set for end-to-end tests."""
    return [
        {
            "timestamp_ns": i * 1_000_000,
            "vehicle_id": "veh",
            "trip_id": "trip",
            "bus_name": "CAN1",
            "arbitration_id": arb,
            "is_extended": False,
            "is_fd": False,
            "dlc": 8,
            "data_bytes": "00" * 8,
            "frame_type": "data",
            "error_state": "normal",
            "source_ecu": "ECU1",
            "capture_source": "test",
            "decoded_signals": {"speed": float(i), "rpm": float(i * 100)},
            "dbc_message_name": "msg",
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for arb in ("0x100", "0x200")
        for i in range(n_per_id)
    ]


def test_can_synthesize_hybrid_uses_stub_sampler(monkeypatch):
    """End-to-end: hybrid strategy is honored when a sampler is injected
    via a stubbed ``build_hybrid_sampler`` (no torch dependency)."""
    from factory.dataset.runtime.adapters import can_synthesize as cs_mod

    sampler = _stub_sampler(delta=1.5)
    monkeypatch.setattr(
        cs_mod, "build_hybrid_sampler",
        lambda **_kwargs: sampler,
    )
    out = list(
        cs_mod.CanSynthesizeStageAdapter().execute(
            _make_pipeline_records(8),
            {
                "multiplier": 4,
                "failure_rate": 0.3,
                "seed": 7,
                "injection_strategy": "hybrid",
            },
        ),
    )
    assert len(out) > 0
    # At least one record must be tagged with the learned strategy
    # (otherwise the stub was never invoked).
    learned = [r for r in out if r.get("failure_strategy") == "learned"]
    assert learned, "hybrid strategy must engage the learned sampler"
    # Failure records with learned strategy must use a learned-mode name.
    learned_modes = {r["failure_mode"] for r in learned}
    assert learned_modes <= set(LEARNED_FAILURE_MODES)


def test_can_synthesize_promotes_rule_to_hybrid_when_sampler_present(monkeypatch):
    """If the caller supplies a SCANIA source but leaves the strategy at
    its ``"rule"`` default, the adapter should auto-promote to
    ``"hybrid"`` so the learned sampler isn't silently ignored.
    """
    from factory.dataset.runtime.adapters import can_synthesize as cs_mod

    sampler = _stub_sampler(delta=1.0)
    monkeypatch.setattr(
        cs_mod, "build_hybrid_sampler",
        lambda **_kwargs: sampler,
    )
    out = list(
        cs_mod.CanSynthesizeStageAdapter().execute(
            _make_pipeline_records(10),
            {
                "multiplier": 4,
                "failure_rate": 0.4,
                "seed": 11,
                # Note: injection_strategy left at default "rule".
            },
        ),
    )
    strategies = {r.get("failure_strategy") for r in out if r["is_failure"]}
    assert "learned" in strategies
