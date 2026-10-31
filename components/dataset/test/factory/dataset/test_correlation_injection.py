"""Tests for the Phase 5 correlation-based failure injection.

Covers four layers:

* :mod:`_correlation_matrix_helpers` — pure data-shaping primitives
  (matrix normalization, envelope generation, root cluster picking).
* :mod:`_correlation_injection_helpers` — the orchestrator that
  mutates records with a gradual, correlation-driven corruption and
  the strategy validator.
* :func:`inject_failures` — orchestration of the new
  ``"correlation"`` strategy in the existing pipeline.
* :class:`CanSynthesizeStageAdapter` — config wiring for the
  ``correlation_matrix`` / ``correlation_matrix_uri`` /
  ``onset_frames`` / ``decay_frames`` keys.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from factory.dataset.runtime.adapters._correlation_injection_helpers import (
    apply_correlation_failure,
    validate_correlation_strategy,
)
from factory.dataset.runtime.adapters._correlation_matrix_helpers import (
    DEFAULT_CORRELATION_THRESHOLD,
    build_envelope,
    normalize_correlation_matrix,
    pick_root_cluster,
)
from factory.dataset.runtime.adapters.failure_injection import (
    CORRELATION_FAILURE_MODE,
    inject_failures,
)


# --- Fixtures ----------------------------------------------------------------


def _make_records(n: int = 20) -> list[dict[str, Any]]:
    """Build a small, deterministic record stream with three signals.

    Signal A and B are strongly correlated (A == 2*i, B == 2*i + 0.1,
    so |r| ~= 1.0); C is constant. This shape is enough to exercise
    every helper without a real CAN fixture.
    """
    return [
        {
            "timestamp_ns": i * 1_000_000,
            "arbitration_id": "0x25",
            "decoded_signals": {
                "A": float(2 * i),
                "B": float(2 * i + 0.1),
                "C": 100.0,
            },
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for i in range(n)
    ]


# --- _correlation_matrix_helpers --------------------------------------------


def test_normalize_accepts_triple_list():
    pairs = [("A", "B", 0.9), ("B", "C", -0.8)]
    out = normalize_correlation_matrix(pairs, ["A", "B", "C"])
    assert out == {("A", "B"): 0.9, ("B", "C"): -0.8}


def test_normalize_accepts_dict_with_tuple_keys():
    matrix = {("A", "B"): 0.7, ("B", "C"): 0.85}
    out = normalize_correlation_matrix(matrix, ["A", "B", "C"])
    assert out == {("A", "B"): 0.7, ("B", "C"): 0.85}


def test_normalize_accepts_2d_array():
    arr = np.array([
        [1.0, 0.9, 0.0],
        [0.9, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    out = normalize_correlation_matrix(arr, ["A", "B", "C"])
    assert out == {("A", "B"): 0.9}


def test_normalize_returns_empty_for_none():
    assert normalize_correlation_matrix(None, ["A", "B"]) == {}


def test_normalize_returns_empty_for_unknown_shape():
    # 1D array, wrong-size 2D, or non-iterable strings -> empty.
    assert normalize_correlation_matrix(np.array([1, 2, 3]), ["A"]) == {}
    assert normalize_correlation_matrix(np.zeros((2, 2)), ["A", "B", "C"]) == {}
    assert normalize_correlation_matrix("not a matrix", ["A", "B"]) == {}


def test_normalize_rejects_2d_array_with_wrong_signal_count():
    arr = np.eye(3)
    out = normalize_correlation_matrix(arr, ["A", "B"])
    assert out == {}


def test_build_envelope_linear_shape():
    env = build_envelope(20, onset_frames=5, decay_frames=5, mode="linear")
    assert env.shape == (20,)
    # First onset frame at 0.0 (or near), first sustained frame at 1.0.
    assert env[0] == pytest.approx(0.0, abs=1e-6)
    assert env[5] == pytest.approx(1.0, abs=1e-6)
    assert env[14] == pytest.approx(1.0, abs=1e-6)
    # Last frame should be 0.0 (decay finishes by frame 19).
    assert env[-1] == pytest.approx(0.0, abs=1e-6)


def test_build_envelope_sigmoid_smooth():
    env = build_envelope(20, onset_frames=5, decay_frames=5, mode="sigmoid")
    # Sigmoid ramps should NOT be linear — the midpoint of the onset
    # should sit near 0.5 (logistic(0)=0.5), not 0.5*N.
    assert env.shape == (20,)
    assert 0.0 < env[2] < 1.0
    # The sigmoid's midpoint frame should be very close to 0.5.
    assert abs(env[2] - 0.5) < 0.01


def test_build_envelope_clamps_to_window():
    # Onset + decay > n_frames should be clipped to fit.
    env = build_envelope(5, onset_frames=10, decay_frames=10, mode="linear")
    assert env.shape == (5,)
    assert env[0] == 0.0
    assert env[-1] == 0.0


def test_build_envelope_zero_frames_returns_empty():
    assert build_envelope(0).shape == (0,)


def test_pick_root_cluster_returns_root_and_neighbors():
    rng = np.random.default_rng(0)
    pairs = {("A", "B"): 0.9, ("A", "C"): 0.8, ("B", "C"): 0.85}
    cluster = pick_root_cluster(pairs, ["A", "B", "C"], rng)
    assert cluster[0] in {"A", "B", "C"}
    # Every other member must be coupled to the root.
    root = cluster[0]
    for n in cluster[1:]:
        assert (root, n) in pairs or (n, root) in pairs


def test_pick_root_cluster_falls_back_to_single_signal():
    """Sparse matrices produce a single-signal pick (no neighbors)."""
    rng = np.random.default_rng(0)
    cluster = pick_root_cluster({}, ["A", "B", "C"], rng)
    assert len(cluster) == 1
    assert cluster[0] in {"A", "B", "C"}


def test_pick_root_cluster_empty_signal_names():
    rng = np.random.default_rng(0)
    assert pick_root_cluster({("A", "B"): 0.9}, [], rng) == []


def test_pick_root_cluster_respects_threshold():
    """Pairs below threshold are ignored."""
    rng = np.random.default_rng(0)
    pairs = {("A", "B"): 0.5}  # below the 0.7 default
    cluster = pick_root_cluster(pairs, ["A", "B"], rng)
    # No strong pairs -> single-signal fallback.
    assert len(cluster) == 1


# --- _correlation_injection_helpers -----------------------------------------


def test_validate_correlation_strategy_accepts_rule():
    validate_correlation_strategy("rule", correlation_matrix=None)


def test_validate_correlation_strategy_accepts_correlation_with_matrix():
    validate_correlation_strategy(
        "correlation", correlation_matrix=[("A", "B", 0.9)],
    )


def test_validate_correlation_strategy_rejects_correlation_without_matrix():
    with pytest.raises(ValueError, match="requires a non-None"):
        validate_correlation_strategy("correlation", correlation_matrix=None)


def test_apply_correlation_failure_mutates_root_signal():
    records = _make_records(20)
    matrix = [("A", "B", 0.9)]
    out_mode = apply_correlation_failure(
        records, start=0, end=10, failure_mode="correlation_failure",
        correlation_matrix=matrix, onset_frames=3, decay_frames=3, rng=np.random.default_rng(0),
    )
    assert out_mode == "correlation_failure"
    # First three frames are at the bottom of the onset ramp (intensity
    # very small) — they should be near the original baseline.
    # Frame at index 5 is the start of the sustained plateau (intensity 1.0)
    # so it should differ noticeably from the original.
    original_a = [2.0 * i for i in range(20)]
    for i in range(0, 3):
        # Onset ramp — may be perturbed but bounded by small envelope.
        assert abs(records[i]["decoded_signals"]["A"] - original_a[i]) < 50.0
    # The sustained region (frame 3..6) should show meaningful corruption.
    sustained_deltas = [
        abs(records[i]["decoded_signals"]["A"] - original_a[i])
        for i in range(3, 7)
    ]
    assert max(sustained_deltas) > 1.0
    # C (constant, uncorrelated) should not be touched.
    for r in records[:10]:
        assert r["decoded_signals"]["C"] == 100.0


def test_apply_correlation_failure_corrupts_multiple_signals():
    """The whole point of correlation injection: root + neighbors move together."""
    records = _make_records(20)
    matrix = [("A", "B", 0.9)]
    rng = np.random.default_rng(7)
    apply_correlation_failure(
        records, start=0, end=10, failure_mode="correlation_failure",
        correlation_matrix=matrix, onset_frames=3, decay_frames=3, rng=rng,
    )
    # The correlation between A and B's deltas in the sustained region
    # should be strongly positive — both moved by the same shared shock.
    original_a = [2.0 * i for i in range(20)]
    original_b = [2.0 * i + 0.1 for i in range(20)]
    deltas_a = [records[i]["decoded_signals"]["A"] - original_a[i] for i in range(3, 7)]
    deltas_b = [records[i]["decoded_signals"]["B"] - original_b[i] for i in range(3, 7)]
    # Sign agreement: most frame-level deltas should share sign because
    # the same shock hits both signals.
    pos = sum(1 for a, b in zip(deltas_a, deltas_b) if a * b > 0)
    assert pos >= 3, f"Expected co-moving A/B deltas, got {deltas_a} / {deltas_b}"


def test_apply_correlation_failure_preserves_sign_for_negative_correlation():
    """Anti-coupled signals should move in the OPPOSITE direction of the root."""
    records = _make_records(20)
    matrix = [("A", "B", -0.9)]
    apply_correlation_failure(
        records, start=0, end=10, failure_mode="correlation_failure",
        correlation_matrix=matrix, onset_frames=3, decay_frames=3,
        rng=np.random.default_rng(42),
    )
    original_a = [2.0 * i for i in range(20)]
    original_b = [2.0 * i + 0.1 for i in range(20)]
    deltas_a = [records[i]["decoded_signals"]["A"] - original_a[i] for i in range(3, 7)]
    deltas_b = [records[i]["decoded_signals"]["B"] - original_b[i] for i in range(3, 7)]
    # For negative correlation, signs should be opposite in the
    # sustained plateau. We sample several frames; at least most
    # should disagree on sign.
    disagree = sum(1 for a, b in zip(deltas_a, deltas_b) if a * b < 0)
    assert disagree >= 3, f"Expected anti-phase A/B deltas, got {deltas_a} / {deltas_b}"


def test_apply_correlation_failure_envelope_zero_at_onset_start():
    """Frame 0 of the window should be untouched (envelope = 0)."""
    records = _make_records(20)
    matrix = [("A", "B", 0.9)]
    apply_correlation_failure(
        records, start=0, end=10, failure_mode="correlation_failure",
        correlation_matrix=matrix, onset_frames=3, decay_frames=3,
        rng=np.random.default_rng(0),
    )
    # Frame 0 is at envelope == 0.0 -> no corruption at all.
    assert records[0]["decoded_signals"]["A"] == 0.0
    assert records[0]["decoded_signals"]["B"] == 0.1


def test_apply_correlation_failure_handles_no_correlations():
    """A sparse matrix degrades to a single-signal pick (no exception)."""
    records = _make_records(20)
    apply_correlation_failure(
        records, start=0, end=10, failure_mode="correlation_failure",
        correlation_matrix=None, onset_frames=3, decay_frames=3,
        rng=np.random.default_rng(0),
    )
    # No exception raised, at least one signal in the window is mutated.
    # We can't assert which one because the cluster pick is random when
    # the matrix is empty (any of A/B/C could be the root).
    window = records[:10]
    any_mutation = any(
        any(
            abs(r["decoded_signals"][name] - (
                {"A": 2.0 * i, "B": 2.0 * i + 0.1, "C": 100.0}[name]
            )) > 0.0
            for name in ("A", "B", "C")
        )
        for i, r in enumerate(window)
    )
    assert any_mutation, "expected at least one signal in the window to be mutated"


def test_apply_correlation_failure_handles_short_window():
    """A 1-frame window should be a no-op (returns the mode unchanged)."""
    records = _make_records(5)
    out = apply_correlation_failure(
        records, start=0, end=1, failure_mode="correlation_failure",
        correlation_matrix=[("A", "B", 0.9)], rng=np.random.default_rng(0),
    )
    assert out == "correlation_failure"
    # No mutation: record untouched.
    assert records[0]["decoded_signals"]["A"] == 0.0


def test_apply_correlation_failure_outside_window_untouched():
    records = _make_records(20)
    apply_correlation_failure(
        records, start=2, end=8, failure_mode="correlation_failure",
        correlation_matrix=[("A", "B", 0.9)], onset_frames=2, decay_frames=2,
        rng=np.random.default_rng(0),
    )
    # Frames outside [2, 8) must match the original baseline exactly.
    for i in (0, 1, 8, 9, 10, 19):
        assert records[i]["decoded_signals"]["A"] == 2.0 * i


# --- inject_failures strategy paths -----------------------------------------


def test_inject_failures_correlation_strategy_tags_records():
    records = _make_records(40)
    matrix = [("A", "B", 0.9), ("B", "C", 0.8)]
    out = list(
        inject_failures(
            records, failure_rate=0.5, rng=np.random.default_rng(0),
            injection_strategy="correlation", correlation_matrix=matrix,
            onset_frames=3, decay_frames=3,
        ),
    )
    failures = [r for r in out if r["is_failure"]]
    assert failures, "Expected at least one failure event"
    # Every correlation-strategy event must use the correlation label.
    assert all(r["failure_strategy"] == "correlation" for r in failures)
    assert all(r["failure_mode"] == CORRELATION_FAILURE_MODE for r in failures)
    # At least one record should show real corruption (non-trivial
    # delta) on the root signal.
    has_corruption = any(
        abs(r["decoded_signals"]["A"] - 2.0 * (r["timestamp_ns"] // 1_000_000)) > 0.1
        for r in failures
    )
    assert has_corruption


def test_inject_failures_correlation_requires_matrix():
    records = _make_records(20)
    with pytest.raises(ValueError, match="requires a non-None"):
        list(
            inject_failures(
                records, failure_rate=0.5, rng=np.random.default_rng(0),
                injection_strategy="correlation", correlation_matrix=None,
            ),
        )


def test_inject_failures_correlation_zero_rate_is_passthrough():
    records = _make_records(10)
    out = list(
        inject_failures(
            records, failure_rate=0.0, rng=np.random.default_rng(0),
            injection_strategy="correlation",
            correlation_matrix=[("A", "B", 0.9)],
        ),
    )
    assert out == records
    assert all(r["is_failure"] == 0 for r in out)


# --- can_synthesize config wiring ------------------------------------------


def test_can_synthesize_allowed_config_includes_phase5_keys():
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
    cfg = CanSynthesizeStageAdapter.allowed_config
    assert "injection_strategy" in cfg
    assert "correlation_matrix" in cfg
    assert "correlation_matrix_uri" in cfg
    assert "onset_frames" in cfg
    assert "decay_frames" in cfg


def test_can_synthesize_rejects_unknown_keys_keeps_phase5():
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
    with pytest.raises(ValueError, match="Unsupported can_synthesize configuration"):
        list(
            CanSynthesizeStageAdapter().execute(
                [], {"multiplier": 2, "rogue": True},
            ),
        )


def test_can_synthesize_correlation_runs_end_to_end(tmp_path: Path):
    """Full end-to-end: input records → SDV → correlation injection."""
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter

    # Minimal schema with correlations for CAN ID 0x100.
    schema = {
        "can_ids": {
            "0x100": {
                "message_name": "TestMsg",
                "frame_rate_hz": 10.0,
                "frame_count": 2,
                "signals": {
                    "speed": {"min": 0.0, "max": 200.0, "mean": 50.0, "std": 10.0, "null_count": 0, "delta_max": 1.0},
                    "rpm": {"min": 0.0, "max": 8000.0, "mean": 2000.0, "std": 200.0, "null_count": 0, "delta_max": 50.0},
                },
                "correlations": [("speed", "rpm", 0.95)],
            },
        },
    }
    template_records = [
        {
            "timestamp_ns": i * 1_000_000,
            "vehicle_id": "veh",
            "trip_id": "trip",
            "bus_name": "CAN1",
            "arbitration_id": "0x100",
            "is_extended": False,
            "is_fd": False,
            "dlc": 8,
            "data_bytes": "00" * 8,
            "frame_type": "data",
            "error_state": "normal",
            "source_ecu": "ECU1",
            "capture_source": "test",
            "decoded_signals": {"speed": float(i * 10), "rpm": float(i * 200)},
            "dbc_message_name": "TestMsg",
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for i in range(6)
    ]
    out = list(
        CanSynthesizeStageAdapter().execute(
            template_records,
            {
                "multiplier": 4,
                "failure_rate": 0.3,
                "seed": 5,
                "constraint_schema": schema,
                "injection_strategy": "correlation",
                "onset_frames": 3,
                "decay_frames": 3,
            },
        ),
    )
    assert out, "synthesize should produce records"
    failures = [r for r in out if r["is_failure"]]
    # With 4x multiplier, 6 templates, we get 24 records total.
    assert len(out) == 24
    # 30% failure rate should produce at least one correlation event.
    assert any(r.get("failure_strategy") == "correlation" for r in failures)
    # Every correlation-strategy record must carry the documented label.
    corr = [r for r in failures if r.get("failure_strategy") == "correlation"]
    assert all(r["failure_mode"] == CORRELATION_FAILURE_MODE for r in corr)


def test_can_synthesize_correlation_matrix_uri_loads_json(tmp_path: Path):
    """``correlation_matrix_uri`` loads a precomputed matrix from JSON."""
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
    from factory.dataset.runtime.adapters.can_synthesize_uri_helpers import (
        load_correlation_matrix_from_uri,
    )

    payload = [["speed", "rpm", 0.85]]  # JSON serializes tuples as lists
    matrix_file = tmp_path / "corr.json"
    matrix_file.write_text(json.dumps(payload))
    loaded = load_correlation_matrix_from_uri(str(matrix_file))
    assert loaded == payload
    # The normalizer downstream accepts both tuples and lists as
    # pair-keyed entries; the test just verifies the URI loader
    # round-trips the raw JSON.

    template_records = [
        {
            "timestamp_ns": i * 1_000_000,
            "vehicle_id": "veh",
            "trip_id": "trip",
            "bus_name": "CAN1",
            "arbitration_id": "0x100",
            "is_extended": False,
            "is_fd": False,
            "dlc": 8,
            "data_bytes": "00" * 8,
            "frame_type": "data",
            "error_state": "normal",
            "source_ecu": "ECU1",
            "capture_source": "test",
            "decoded_signals": {"speed": float(i * 10), "rpm": float(i * 200)},
            "dbc_message_name": "TestMsg",
            "is_failure": 0,
            "failure_mode": None,
            "failure_timestamp_ns": None,
        }
        for i in range(8)
    ]
    out = list(
        CanSynthesizeStageAdapter().execute(
            template_records,
            {
                "multiplier": 3,
                "failure_rate": 0.4,
                "seed": 11,
                "injection_strategy": "correlation",
                "correlation_matrix_uri": matrix_file.as_uri(),
                "onset_frames": 2,
                "decay_frames": 2,
            },
        ),
    )
    assert out
    failures = [r for r in out if r["is_failure"]]
    assert any(r.get("failure_strategy") == "correlation" for r in failures)


def test_can_synthesize_correlation_uri_rejects_traversal(tmp_path: Path):
    """``../`` in the URI must be rejected to defend against path traversal."""
    from factory.dataset.runtime.adapters.can_synthesize_uri_helpers import (
        load_correlation_matrix_from_uri,
    )
    with pytest.raises(ValueError, match="Path traversal"):
        load_correlation_matrix_from_uri(str(tmp_path / ".." / "secret.json"))


def test_can_synthesize_correlation_clamps_onset_decay_to_non_negative():
    """A negative onset/decay value should clamp to 0, not raise."""
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter

    records = _make_records(6)
    records = [{**r, "vehicle_id": "v", "trip_id": "t", "bus_name": "CAN1",
                "is_extended": False, "is_fd": False, "dlc": 8,
                "data_bytes": "00" * 8, "frame_type": "data",
                "error_state": "normal", "source_ecu": "ECU1",
                "capture_source": "test", "dbc_message_name": "M"}
               for r in records]
    out = list(
        CanSynthesizeStageAdapter().execute(
            records,
            {
                "multiplier": 2,
                "failure_rate": 0.3,
                "seed": 1,
                "correlation_matrix": [("A", "B", 0.9)],
                "injection_strategy": "correlation",
                "onset_frames": -5,
                "decay_frames": -3,
            },
        ),
    )
    assert out  # no exception


def test_can_synthesize_correlation_without_matrix_raises():
    """The config-layer must propagate the missing-matrix error loudly."""
    from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter

    records = _make_records(6)
    with pytest.raises(ValueError, match="requires a non-None"):
        list(
            CanSynthesizeStageAdapter().execute(
                records,
                {
                    "multiplier": 2,
                    "failure_rate": 0.3,
                    "seed": 1,
                    "injection_strategy": "correlation",
                },
            ),
        )
