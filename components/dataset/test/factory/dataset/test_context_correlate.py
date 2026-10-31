"""Tests for the context_correlate stage adapter."""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from factory.dataset.runtime.adapters.context_correlate import (
    ContextCorrelateStageAdapter,
    DEFAULT_MIN_CORRELATION,
)
from factory.dataset.runtime.adapters._context_correlate_helpers import (
    compute_correlation,
)


def _adapter() -> ContextCorrelateStageAdapter:
    return ContextCorrelateStageAdapter()


def _build_records(n: int = 20, seed: int = 0) -> list[dict[str, Any]]:
    """First half: warm normal records. Second half: cold battery failures
    → Pearson(temp_c, battery) ≈ -1.
    """
    rng = np.random.default_rng(seed)
    return [
        {
            "context": {"temp_c": float(15.0 + rng.normal(0, 1.0) if i < n // 2
                                            else -10.0 + rng.normal(0, 1.0))},
            "failure_mode": None if i < n // 2 else "battery_degradation",
        }
        for i in range(n)
    ]


def _heatmap(records: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "context_features": ["temp_c"],
        "failure_modes": ["battery_degradation"],
    }
    cfg.update(overrides)
    out = list(_adapter().execute(records, cfg))
    sidecars = [r for r in out if r.get("record_type") == "context_correlation_heatmap"]
    assert len(sidecars) == 1
    return sidecars[0]


# --- Contract & validation --------------------------------------------------


def test_satisfies_stage_contract():
    a = _adapter()
    assert a.name == "context_correlate"
    assert a.stage_version.startswith("factory-context-correlate")
    assert isinstance(a.allowed_config, frozenset)


def test_rejects_unknown_config_keys():
    with pytest.raises(ValueError, match="Unsupported context_correlate"):
        list(_adapter().execute(
            [], {"context_features": ["t"], "failure_modes": ["x"], "rogue": True},
        ))


def test_rejects_unknown_method():
    with pytest.raises(ValueError, match="Unsupported correlation method"):
        list(_adapter().execute(
            [], {"context_features": ["t"], "failure_modes": ["x"], "method": "kendall"},
        ))


@pytest.mark.parametrize("field", ["context_features", "failure_modes"])
def test_rejects_empty_lists(field):
    cfg = {"context_features": ["t"], "failure_modes": ["battery_degradation"], field: []}
    with pytest.raises(ValueError, match=f"non-empty '{field}'"):
        list(_adapter().execute([], cfg))


def _pair(sidecar: dict[str, Any], feature: str, mode: str) -> dict[str, Any]:
    return next(
        pair for pair in sidecar["heatmap"]
        if pair["context_feature"] == feature and pair["failure_mode"] == mode
    )


def test_pearson_picks_up_strong_negative_correlation():
    entry = _pair(_heatmap(_build_records(n=40, seed=0), method="pearson"),
                  "temp_c", "battery_degradation")
    assert entry["correlation"] < -0.5
    assert entry["method"] == "pearson"


def test_helper_pearson_matches_numpy():
    rng = np.random.default_rng(0)
    x = rng.normal(size=100)
    y = 2.0 * x + 0.01 * rng.normal(size=100)
    r = compute_correlation(x, y, "pearson")
    assert r == pytest.approx(float(np.corrcoef(x, y)[0, 1]), abs=1e-9)


def test_spearman_uses_ranks():
    x = np.arange(1.0, 9.0)
    assert compute_correlation(x, x ** 2, "spearman") == pytest.approx(1.0, abs=1e-9)


def test_spearman_handles_ties():
    x = np.array([1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
    y = np.array([1.0, 2.0, 2.0, 3.0, 3.0, 4.0])
    assert -1.0 <= compute_correlation(x, y, "spearman") <= 1.0
    assert compute_correlation(x, x, "spearman") == pytest.approx(1.0, abs=1e-9)


def test_spearman_via_adapter():
    sidecar = _heatmap(_build_records(n=30, seed=1), method="spearman")
    assert sidecar["method"] == "spearman"
    assert abs(_pair(sidecar, "temp_c", "battery_degradation")["correlation"]) > 0.5


def test_nan_value_does_not_poison_pair():
    records = _build_records(n=30, seed=0)
    for r in records[:5]:
        r["context"]["temp_c"] = None
    assert _pair(_heatmap(records), "temp_c", "battery_degradation")["correlation"] < -0.5


def test_all_nan_skips_pair():
    records = _build_records(n=10, seed=0)
    for r in records:
        r["context"] = None
    assert _heatmap(records)["heatmap"] == []


def test_constant_feature_is_skipped():
    records = _build_records(n=20, seed=0)
    for r in records:
        r["context"]["humidity_pct"] = 50.0
    sidecar = _heatmap(records, context_features=["temp_c", "humidity_pct"])
    pairs = {(p["context_feature"], p["failure_mode"]) for p in sidecar["heatmap"]}
    assert ("humidity_pct", "battery_degradation") not in pairs
    assert ("temp_c", "battery_degradation") in pairs


def test_constant_failure_mode_is_skipped():
    records = _build_records(n=20, seed=0)
    for r in records:
        r["failure_mode"] = "battery_degradation"
    assert _heatmap(records)["heatmap"] == []


def test_min_correlation_threshold_filters_weak_pairs():
    rng = np.random.default_rng(0)
    records = [
        {
            "context": {"temp_c": float(rng.normal(0, 1.0))},
            "failure_mode": "battery_degradation" if i % 2 == 0 else None,
        }
        for i in range(40)
    ]
    sidecar = _heatmap(records, min_correlation=0.99)
    assert sidecar["heatmap"] == []
    assert sidecar["min_correlation"] == 0.99


def test_min_correlation_uses_absolute_value_for_signed_methods():
    sidecar = _heatmap(_build_records(n=40, seed=2), min_correlation=0.5)
    assert abs(_pair(sidecar, "temp_c", "battery_degradation")["correlation"]) >= 0.5


def test_min_correlation_default_value():
    assert DEFAULT_MIN_CORRELATION == 0.3


# --- Pass-through behavior --------------------------------------------------


def test_passes_through_input_records_unchanged():
    records = _build_records(n=10, seed=0)
    cfg = {"context_features": ["temp_c"], "failure_modes": ["battery_degradation"]}
    out = list(_adapter().execute(records, cfg))
    assert out[: len(records)] == records
    assert out[-1]["record_type"] == "context_correlation_heatmap"


def test_empty_records_yields_nothing():
    cfg = {"context_features": ["temp_c"], "failure_modes": ["battery_degradation"]}
    assert list(_adapter().execute([], cfg)) == []
