"""Validate synthetic-CAN-label AUROC claims (0.97-1.00, per
`.agents/steering/can-failure-prediction.md`) against REAL failure-record
labels from the UCI "APS Failure at Scania Trucks" dataset.

This is a throwaway, standalone validation script — not part of the brick
surface. It follows the same direct-import precedent as
`projects/companion_x/train_can.py` / `evaluate_can.py`.

Leakage-purity discipline (see report at bottom of `main()`):
  (a) Imputation medians are computed from the TRAIN CSV only, then the
      SAME vector is applied to both train and test. Test rows never
      contribute to the median.
  (b) The held-out test CSV is loaded, imputed (with train medians) and
      converted to .npy — but it is NEVER passed to `.train()`. It is only
      used in a single, separate `.predict()` call after training
      completes. `y_test` is kept aside in Python and never touches any
      training code path.
  (c) Row counts (60000 train / 16000 test) are asserted immediately after
      the header-skip parse, before any other processing.
  (d) The raw class balance of the test CSV is printed immediately after
      parsing, before imputation/resampling/any transformation.
  (e) `scale_pos_weight` is computed from TRAIN counts only and forwarded
      via `TimeSeriesTrainingConfig(extra=...)` — no resampling of train or
      test ever occurs.

Usage:
    uv run python projects/companion_x/validate_real_failure_labels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(
    "/Users/wdaniero/workplace/python-factory/projects/companion_x/data/real_failure_validation",
)
TRAIN_CSV = DATA_DIR / "aps_failure_training_set.csv"
TEST_CSV = DATA_DIR / "aps_failure_test_set.csv"
RUN_DIR = Path("/tmp/aps_real_run")

EXPECTED_TRAIN_ROWS = 60_000
EXPECTED_TEST_ROWS = 16_000
UCI_DOCUMENTED_TEST_POS = 375
UCI_DOCUMENTED_TEST_NEG = 15_625

# 2016 UCI leaderboard reference costs (top-3), cited for context only —
# this script does not attempt to reproduce their exact preprocessing.
UCI_LEADERBOARD_REFERENCE_COSTS = [9920, 10900, 11480]

# Synthetic-injection AUROC claim from the steering doc, cited as source.
SYNTHETIC_AUROC_CLAIM = (0.97, 1.00)
SYNTHETIC_AUROC_SOURCE = ".agents/steering/can-failure-prediction.md"


def _find_header_row(path: Path) -> int:
    """Return the 0-based line index of the row starting with 'class,'."""
    with path.open() as fh:
        for i, line in enumerate(fh):
            if line.startswith("class,"):
                return i
    raise ValueError(f"No 'class,' header row found in {path}")


def _load_aps_csv(path: Path) -> pd.DataFrame:
    """Load one APS CSV, skipping the license preamble, with 'na' -> NaN."""
    header_row = _find_header_row(path)
    print(f"  [{path.name}] header found at line {header_row + 1} (0-indexed {header_row})")
    df = pd.read_csv(path, skiprows=header_row, na_values=["na"])
    return df


def _class_to_binary(series: pd.Series) -> np.ndarray:
    mapping = {"pos": 1, "neg": 0}
    if not set(series.unique()) <= set(mapping):
        raise ValueError(f"Unexpected class labels: {series.unique()}")
    return series.map(mapping).to_numpy(dtype=np.int64)


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    print("=== STEP 1-2: Load real UCI APS Failure CSVs + assert shape/balance ===")
    train_df = _load_aps_csv(TRAIN_CSV)
    test_df = _load_aps_csv(TEST_CSV)

    # (c) Row-count assertions, immediately after parse.
    assert len(train_df) == EXPECTED_TRAIN_ROWS, (
        f"Expected {EXPECTED_TRAIN_ROWS} train rows, got {len(train_df)}"
    )
    assert len(test_df) == EXPECTED_TEST_ROWS, (
        f"Expected {EXPECTED_TEST_ROWS} test rows, got {len(test_df)}"
    )
    print(f"  Row counts CONFIRMED: train={len(train_df)}, test={len(test_df)}")

    y_train_raw = _class_to_binary(train_df["class"])
    y_test_raw = _class_to_binary(test_df["class"])

    # (d) Raw class balance, printed before any transformation.
    train_pos, train_neg = int(y_train_raw.sum()), int((y_train_raw == 0).sum())
    test_pos, test_neg = int(y_test_raw.sum()), int((y_test_raw == 0).sum())
    print(f"  RAW train class balance: pos={train_pos}, neg={train_neg}")
    print(f"  RAW test class balance:  pos={test_pos}, neg={test_neg}")
    print(
        f"  UCI documented test balance: pos={UCI_DOCUMENTED_TEST_POS}, "
        f"neg={UCI_DOCUMENTED_TEST_NEG}",
    )
    if (test_pos, test_neg) != (UCI_DOCUMENTED_TEST_POS, UCI_DOCUMENTED_TEST_NEG):
        print(
            "  ** DEVIATION FLAGGED ** empirically loaded test balance does not "
            "exactly match the documented UCI numbers (see actual counts above).",
        )
    else:
        print("  Test balance MATCHES documented UCI numbers exactly.")

    feature_cols = [c for c in train_df.columns if c != "class"]
    X_train_df = train_df[feature_cols].astype(float)
    X_test_df = test_df[feature_cols].astype(float)

    print("\n=== STEP 3: TRAIN-ONLY median imputation ===")
    # (a) Medians computed from TRAIN ONLY. This is the sole source of the
    # imputation vector; it is applied identically to train and test.
    train_medians = X_train_df.median(axis=0)
    print(f"  Imputation median vector computed from: {TRAIN_CSV.name} (train only)")
    print(f"  Median vector length: {len(train_medians)} (one per feature column)")
    print(f"  Sample medians (first 5 features): {train_medians.head(5).to_dict()}")
    n_train_na = int(X_train_df.isna().sum().sum())
    n_test_na = int(X_test_df.isna().sum().sum())
    print(f"  NaN cells before imputation: train={n_train_na}, test={n_test_na}")

    X_train_imputed = X_train_df.fillna(train_medians)
    X_test_imputed = X_test_df.fillna(train_medians)  # SAME train-derived vector
    assert X_train_imputed.isna().sum().sum() == 0
    assert X_test_imputed.isna().sum().sum() == 0
    print("  Imputation applied. No NaNs remain in either split.")

    X_train_arr = X_train_imputed.to_numpy(dtype=np.float64)
    X_test_arr = X_test_imputed.to_numpy(dtype=np.float64)

    print("\n=== STEP 4: scale_pos_weight from TRAIN class counts (no resampling) ===")
    scale_pos_weight = train_neg / train_pos
    print(f"  train_neg={train_neg}, train_pos={train_pos}")
    print(f"  scale_pos_weight = n_neg_train / n_pos_train = {scale_pos_weight:.4f}")
    print("  No SMOTE / resampling applied to train or test at any point.")

    print("\n=== STEP 5: Persist train/test arrays to .npy ===")
    x_train_uri = RUN_DIR / "X_train.npy"
    y_train_uri = RUN_DIR / "y_train.npy"
    x_test_uri = RUN_DIR / "X_test.npy"
    y_test_uri = RUN_DIR / "y_test.npy"  # held aside, never fed to .train()
    np.save(x_train_uri, X_train_arr)
    np.save(y_train_uri, y_train_raw.astype(np.float64))
    np.save(x_test_uri, X_test_arr)
    np.save(y_test_uri, y_test_raw.astype(np.float64))
    print(f"  Saved: {x_train_uri}, {y_train_uri}")
    print(f"  Saved (held-out, NOT used in training): {x_test_uri}, {y_test_uri}")

    print("\n=== STEP 6: Train LightGBM via factory.machine_learning.interface ===")
    from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
    from factory.machine_learning.runtime.adapters.sklearn_timeseries import (
        SklearnTimeSeriesAdapter,
    )
    from factory.machine_learning.runtime.ports import (
        TimeSeriesModelType,
        TimeSeriesTrainingConfig,
    )

    tracker = MemoryTracker()
    adapter = SklearnTimeSeriesAdapter(tracker=tracker)
    config = TimeSeriesTrainingConfig(
        window_size=1,  # non-windowed tabular data; adapter does its own val split
        validation_split=0.2,
        seed=42,
        extra={"scale_pos_weight": scale_pos_weight},
    )
    job = adapter.train(
        TimeSeriesModelType.lightgbm,
        f"file://{x_train_uri}",
        f"file://{y_train_uri}",
        config=config,
        experiment_name="aps-real-failure-validation",
    )
    print(f"  Job id: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Internal val-split metrics (NOT the official test set): {job.metrics}")

    print(
        "\n=== STEP 7: Score against OFFICIAL held-out test CSV "
        "(FIRST touch of test set) ===",
    )
    pred_uri = adapter.predict(job.id, f"file://{x_test_uri}")
    pred_path = pred_uri.replace("file://", "")
    npz = np.load(pred_path)
    y_pred_test = npz["y_pred"]
    y_score_test = npz["y_score"] if "y_score" in npz else None
    print(f"  Predictions written to: {pred_uri}")
    print(f"  y_test loaded separately from: {y_test_uri} (never passed to .train())")

    print("\n=== STEP 8: Compute metrics via evaluate_can_model() ===")
    sys.path.insert(
        0,
        str(Path(__file__).resolve().parents[2] / "components" / "evals" / "src"),
    )
    from factory.evals.runtime.adapters.can_evaluator import evaluate_can_model

    metrics = evaluate_can_model(y_test_raw, y_pred_test, y_score_test)
    print(f"  Real-test metrics: {metrics}")

    print("\n=== STEP 9: UCI cost metric @ threshold 0.5 ===")
    fp = int(((y_pred_test == 1) & (y_test_raw == 0)).sum())
    fn = int(((y_pred_test == 0) & (y_test_raw == 1)).sum())
    tp = int(((y_pred_test == 1) & (y_test_raw == 1)).sum())
    tn = int(((y_pred_test == 0) & (y_test_raw == 0)).sum())
    total_cost = 10 * fp + 500 * fn
    print(f"  Confusion: TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"  total_cost = 10*FP + 500*FN = 10*{fp} + 500*{fn} = {total_cost}")
    print(f"  UCI 2016 leaderboard reference (top-3, lower=better): {UCI_LEADERBOARD_REFERENCE_COSTS}")

    print("\n" + "=" * 70)
    print("FINAL REPORT: real-data metrics vs. synthetic claims vs. leaderboard")
    print("=" * 70)
    auroc = metrics.get("auroc")
    print(f"REAL-DATA AUROC:      {auroc}")
    print(f"REAL-DATA AUPRC:      {metrics.get('auprc')}")
    print(f"REAL-DATA Brier:      {metrics.get('brier')}")
    print(f"REAL-DATA F1:         {metrics['f1']}")
    print(f"REAL-DATA Accuracy:   {metrics['accuracy']}")
    print(f"REAL-DATA Precision:  {metrics['precision']}")
    print(f"REAL-DATA Recall:     {metrics['recall']}")
    print(f"REAL-DATA UCI cost:   {total_cost}  (leaderboard ref: {UCI_LEADERBOARD_REFERENCE_COSTS})")
    print(
        f"SYNTHETIC AUROC CLAIM: {SYNTHETIC_AUROC_CLAIM[0]}-{SYNTHETIC_AUROC_CLAIM[1]} "
        f"(source: {SYNTHETIC_AUROC_SOURCE})",
    )

    if auroc is not None:
        lo, hi = SYNTHETIC_AUROC_CLAIM
        gap = lo - auroc
        if auroc >= lo - 0.02:
            verdict = "COMPARABLE to the synthetic AUROC claim."
        elif gap < 0.15:
            verdict = "MODERATELY LOWER than the synthetic AUROC claim."
        else:
            verdict = "DRAMATICALLY LOWER than the synthetic AUROC claim."
        print(f"\nVERDICT: Real-data AUROC ({auroc:.4f}) is {verdict}")
    else:
        print("\nVERDICT: AUROC unavailable (single-class y_score edge case).")

    print("\n" + "=" * 70)
    print("LEAKAGE-PURITY CHECKLIST")
    print("=" * 70)
    print(f"(a) Imputation train-only:  medians computed from {TRAIN_CSV.name} only; "
          f"same vector applied to both splits. PASS")
    print(f"(b) Test never seen pre-scoring: test .npy built independently, only "
          f"consumed by adapter.predict(job.id, ...) AFTER job={job.id} completed "
          f"training. .train() call args were X_train/y_train URIs only. PASS")
    print(f"(c) Row counts: train={len(train_df)} (expected {EXPECTED_TRAIN_ROWS}), "
          f"test={len(test_df)} (expected {EXPECTED_TEST_ROWS}). PASS")
    print(f"(d) Test class balance unmodified: raw pos={test_pos}/neg={test_neg} "
          f"printed pre-processing, no resampling applied anywhere. PASS")
    print("(e) See separate pytest run below for existing-test sanity check.")


if __name__ == "__main__":
    main()
