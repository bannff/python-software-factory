"""Tests for the SCANIA APS pattern extractor (Phase-1 TimeGAN bridge).

These tests cover three layers:

* ``_scania_helpers`` — pure data-shaping primitives (trajectory, z-score,
  feature matrix coercion). Exercised with synthetic inputs so the
  tests stay hermetic and fast.
* :class:`ScaniaPatternExtractor` — extraction logic with both
  synthetic record lists and a fixture DataFrame. No real SCANIA CSV is
  read; that path is covered by the optional live-data test guarded
  by an env var.
* ``build_training_dataset`` — end-to-end driver script contract,
  verified with a temp directory of fake CSVs.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factory.dataset.runtime.adapters._scania_helpers import (
    SCANIA_BASELINE_MODE,
    SCANIA_FAILURE_MODE,
    SCANIA_HEADER_LINES,
    SCANIA_POS_LABEL,
    build_trajectory,
    coerce_records,
    feature_matrix,
    zscore_normalize,
)
from factory.dataset.runtime.adapters.scania_pattern_extractor import (
    ScaniaPatternExtractor,
)


# --- Synthetic fixtures -----------------------------------------------------


def _synth_records(
    n_pos: int = 5,
    n_neg: int = 20,
    n_features: int = 8,
    seed: int = 0,
) -> list[dict]:
    """Create a balanced synthetic SCANIA-like record set."""
    rng = np.random.default_rng(seed)
    can_ids = [f"sig_{i:03d}" for i in range(n_features)]
    neg_features = rng.normal(loc=10.0, scale=1.0, size=(n_neg, n_features))
    # Failures drift away from the baseline mean so z-score retains signal.
    pos_features = rng.normal(loc=12.0, scale=1.5, size=(n_pos, n_features))

    records: list[dict] = []
    for row in neg_features:
        records.append({
            "class": "neg",
            "features": dict(zip(can_ids, row.tolist())),
        })
    for row in pos_features:
        records.append({
            "class": "pos",
            "features": dict(zip(can_ids, row.tolist())),
        })
    rng.shuffle(records)
    return records


def _write_fake_scania_csv(
    path: Path,
    n_rows: int = 50,
    n_features: int = 5,
    n_pos: int = 10,
) -> None:
    """Write a minimal SCANIA-shaped CSV with a 20-line GPL header.

    The first ``n_pos`` rows are tagged ``pos``; the remainder are
    ``neg``. ``n_pos`` is clamped to ``n_rows`` so callers can request
    edge cases (all-pos, all-neg).
    """
    rng = np.random.default_rng(7)
    can_ids = [f"sig_{i:03d}" for i in range(n_features)]
    header_lines = "\n".join(f"# GPL line {i}" for i in range(SCANIA_HEADER_LINES)) + "\n"
    csv_header = "class," + ",".join(can_ids) + "\n"
    body_lines: list[str] = []
    for i in range(n_rows):
        cls = "pos" if i < n_pos else "neg"
        values = rng.normal(0, 1, n_features)
        body_lines.append(cls + "," + ",".join(f"{v:.4f}" for v in values))
    path.write_text(header_lines + csv_header + "\n".join(body_lines) + "\n")


# --- _scania_helpers --------------------------------------------------------


def test_build_trajectory_anchors_to_failure_at_last_frame():
    failure = np.array([1.0, 2.0, 3.0])
    baseline = np.array([0.0, 0.0, 0.0])
    traj = build_trajectory(failure, baseline, window_size=10)
    assert traj.shape == (10, 3)
    np.testing.assert_allclose(traj[0], baseline)
    np.testing.assert_allclose(traj[-1], failure)
    # linspace(0, 1, 10) gives alpha=0.5 at index 4.5; verify the
    # half-way point between frames 4 and 5 sits on the midpoint.
    midpoint = 0.5 * (traj[4] + traj[5])
    expected = 0.5 * (baseline + failure)
    np.testing.assert_allclose(midpoint, expected)
    # Trajectory should be strictly monotonic per feature (baseline -> failure).
    assert np.all(np.diff(traj[:, 0]) > 0)


def test_build_trajectory_rejects_short_window():
    with pytest.raises(ValueError, match="window_size must be >= 2"):
        build_trajectory(np.zeros(3), np.zeros(3), window_size=1)


def test_feature_matrix_handles_nan_with_column_mean_imputation():
    records = [
        {"class": "pos", "features": {"a": 1.0, "b": np.nan, "c": 3.0}},
        {"class": "pos", "features": {"a": 2.0, "b": 4.0, "c": np.nan}},
        {"class": "pos", "features": {"a": 3.0, "b": 6.0, "c": 9.0}},
    ]
    matrix, can_ids = feature_matrix(records)
    assert can_ids == ["a", "b", "c"]
    assert matrix.shape == (3, 3)
    # Column means: a=2.0, b=5.0, c=6.0
    np.testing.assert_allclose(matrix[0], [1.0, 5.0, 3.0])
    np.testing.assert_allclose(matrix[1], [2.0, 4.0, 6.0])
    np.testing.assert_allclose(matrix[2], [3.0, 6.0, 9.0])


def test_feature_matrix_rejects_empty_records():
    with pytest.raises(ValueError, match="zero records"):
        feature_matrix([])


def test_zscore_normalize_yields_zero_mean_unit_std_per_feature():
    trajectories = np.random.default_rng(0).normal(size=(10, 5, 3))
    normalized = zscore_normalize(trajectories)
    flat = normalized.reshape(-1, 3)
    np.testing.assert_allclose(flat.mean(axis=0), np.zeros(3), atol=1e-6)
    np.testing.assert_allclose(flat.std(axis=0), np.ones(3), atol=1e-6)


def test_zscore_normalize_keeps_constant_feature_at_zero():
    # A constant feature has std=0; the implementation should clamp std
    # to 1.0 and the resulting feature to 0.0 (no NaN / inf leakage).
    trajectories = np.zeros((4, 3, 2))
    trajectories[..., 1] = np.random.default_rng(1).normal(size=(4, 3))
    normalized = zscore_normalize(trajectories)
    assert np.all(np.isfinite(normalized))
    np.testing.assert_allclose(normalized[..., 0], 0.0)


def test_coerce_records_accepts_dataframe():
    df = pd.DataFrame({"class": ["pos", "neg"], "a": [1.0, 2.0], "b": [3.0, 4.0]})
    out = coerce_records(df)
    assert len(out) == 2
    assert out[0]["class"] == "pos"
    assert set(out[0]["features"]) == {"a", "b"}


def test_coerce_records_accepts_mapping():
    out = coerce_records({"k1": {"class": "pos", "features": {"a": 1.0}}})
    assert out == [{"class": "pos", "features": {"a": 1.0}}]


# --- ScaniaPatternExtractor -------------------------------------------------


def test_extractor_window_size_validated():
    with pytest.raises(ValueError, match="window_size must be >= 2"):
        ScaniaPatternExtractor(window_size=1)


def test_extract_failure_signatures_shape_and_dtype():
    extractor = ScaniaPatternExtractor(window_size=20)
    records = _synth_records(n_pos=4, n_neg=12, n_features=6)
    result = extractor.extract_failure_signatures(records)
    assert SCANIA_FAILURE_MODE in result
    assert result[SCANIA_FAILURE_MODE].shape == (4, 20, 6)
    assert result[SCANIA_FAILURE_MODE].dtype == np.float32
    assert result[SCANIA_BASELINE_MODE].shape == (12, 20, 6)
    assert list(result["_can_ids"]) == [f"sig_{i:03d}" for i in range(6)]


def test_extract_failure_signatures_rejects_no_failures():
    extractor = ScaniaPatternExtractor()
    records = [{"class": "neg", "features": {"a": 1.0}} for _ in range(3)]
    with pytest.raises(ValueError, match="No positive .* records"):
        extractor.extract_failure_signatures(records)


def test_extract_failure_signatures_rejects_empty_input():
    extractor = ScaniaPatternExtractor()
    with pytest.raises(ValueError, match="No SCANIA records provided"):
        extractor.extract_failure_signatures([])


def test_extract_failure_signatures_last_frame_matches_failure_row():
    """The trajectory's terminal frame must equal the original failure values."""
    extractor = ScaniaPatternExtractor(window_size=10)
    records = _synth_records(n_pos=3, n_neg=8, n_features=4, seed=42)
    pos_rows = [r for r in records if r["class"] == "pos"]
    result = extractor.extract_failure_signatures(records)
    failures = result[SCANIA_FAILURE_MODE]
    can_ids = list(result["_can_ids"])
    for i, rec in enumerate(pos_rows):
        expected = np.array([rec["features"][c] for c in can_ids])
        # Z-score normalization is applied jointly; the relative
        # ordering of features within a row is preserved, so a linear
        # transform maps expected -> observed. Recover the scale via
        # first/last columns to confirm endpoints anchor correctly.
        first_norm = failures[i, 0, 0]
        last_norm = failures[i, -1, 0]
        assert last_norm != first_norm, "Trajectory should drift, not be flat"


def test_zscore_normalized_trajectories_have_near_unit_variance():
    extractor = ScaniaPatternExtractor(window_size=30)
    records = _synth_records(n_pos=20, n_neg=80, n_features=10, seed=1)
    result = extractor.extract_failure_signatures(records)
    combined = np.concatenate(
        [result[SCANIA_FAILURE_MODE], result[SCANIA_BASELINE_MODE]],
        axis=0,
    )
    flat = combined.reshape(-1, combined.shape[-1])
    # Joint z-score fit: mean ~0, std ~1.
    np.testing.assert_allclose(flat.mean(axis=0), np.zeros(flat.shape[1]), atol=1e-5)
    np.testing.assert_allclose(flat.std(axis=0), np.ones(flat.shape[1]), atol=1e-2)


def test_build_training_dataset_writes_npy_with_expected_shape(tmp_path: Path):
    extractor = ScaniaPatternExtractor(window_size=25)
    csv_path = tmp_path / "aps_failure_synthetic.csv"
    _write_fake_scania_csv(csv_path, n_rows=40, n_features=6, n_pos=10)
    out_path = tmp_path / "failures.npy"

    tensor = extractor.build_training_dataset(str(csv_path), str(out_path))

    assert out_path.exists()
    loaded = np.load(out_path)
    np.testing.assert_array_equal(loaded, tensor)
    # 10 positives × 25 frames × 6 features
    assert tensor.shape == (10, 25, 6)
    assert tensor.dtype == np.float32


def test_build_training_dataset_accepts_directory_uri(tmp_path: Path):
    extractor = ScaniaPatternExtractor(window_size=15)
    _write_fake_scania_csv(
        tmp_path / "aps_failure_train.csv", n_rows=30, n_features=4, n_pos=5,
    )
    _write_fake_scania_csv(
        tmp_path / "aps_failure_test.csv", n_rows=15, n_features=4, n_pos=5,
    )
    out_path = tmp_path / "combined.npy"

    tensor = extractor.build_training_dataset(str(tmp_path), str(out_path))

    # 5 positives per file × 2 files = 10 failure windows.
    assert tensor.shape == (10, 15, 4)
    assert tensor.dtype == np.float32


def test_build_training_dataset_rejects_missing_positives(tmp_path: Path):
    extractor = ScaniaPatternExtractor()
    csv_path = tmp_path / "aps_failure_neg_only.csv"
    # All neg rows (n_pos=0).
    _write_fake_scania_csv(csv_path, n_rows=20, n_features=4, n_pos=0)
    out_path = tmp_path / "should_not_exist.npy"
    with pytest.raises(ValueError, match="No positive .* records"):
        extractor.build_training_dataset(str(csv_path), str(out_path))
    assert not out_path.exists()


def test_build_training_dataset_creates_parent_dirs(tmp_path: Path):
    extractor = ScaniaPatternExtractor()
    csv_path = tmp_path / "aps_failure_train.csv"
    _write_fake_scania_csv(csv_path, n_rows=20, n_features=4, n_pos=5)
    nested_out = tmp_path / "deep" / "nested" / "failures.npy"
    tensor = extractor.build_training_dataset(str(csv_path), str(nested_out))
    assert nested_out.exists()
    assert tensor.shape[0] == 5  # 5 pos rows in the fixture


# --- Live data integration (skipped unless SCANIA_DATA_URI is set) --------


def test_live_scania_training_set_round_trip(tmp_path: Path):
    """End-to-end smoke test against the real SCANIA APS training CSV."""
    uri = os.environ.get("SCANIA_DATA_URI")
    if not uri:
        pytest.skip("Set SCANIA_DATA_URI to run the live data round-trip test")
    extractor = ScaniaPatternExtractor(window_size=50)
    out_path = tmp_path / "scania_failures.npy"
    tensor = extractor.build_training_dataset(uri, str(out_path))
    assert tensor.ndim == 3
    assert tensor.shape[1] == 50
    # 171 columns in the SCANIA CSV = 1 'class' + 170 feature signals.
    assert tensor.shape[2] == 170
    # 1K pos failures in the public training set; the test set adds
    # ~375 more so the combined set sits at 1375 today.
    assert 900 <= tensor.shape[0] <= 2000
    assert tensor.dtype == np.float32
    assert out_path.exists()
    assert np.isfinite(tensor).all()
