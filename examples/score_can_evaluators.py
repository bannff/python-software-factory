"""Score trained CAN models with the full production evaluator suite.

Loads real + synthetic windowed data, trains LightGBM, LSTM, and TCN on
the combined dataset, holds out the last 20% as a temporal test split,
then scores every model with the six production evaluators wired into
``factory.evals.runtime.adapters.can_evaluator`` (auroc, auprc, brier,
lead_time, false_alarm, episode_recall).

Writes the per-model metric bundle to
``/Volumes/Crucial X9/can_data/comparison_results/evaluator_scores.json``
and prints a side-by-side comparison table.

Usage:
    python examples/score_can_evaluators.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

# Add the workspace to the path so we can import factory modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.evals.runtime.adapters.can_evaluator import evaluate_can_model

from _can_scoring_data import DEFAULT_DATA_DIR, load_combined, temporal_split
from _can_scoring_models import (
    DEFAULT_BATCH,
    DEFAULT_EPOCHS,
    LSTMClassifier,
    TCNClassifier,
    predict_torch,
    train_torch_model,
)

OUTPUT_PATH = DEFAULT_DATA_DIR / "evaluator_scores.json"
SEED = 42
LGBM_NUM_BOOST = 500
EVAL_METRICS = [
    ("accuracy", "{:.4f}"),
    ("precision", "{:.4f}"),
    ("recall", "{:.4f}"),
    ("f1", "{:.4f}"),
    ("auroc", "{:.4f}"),
    ("auprc", "{:.4f}"),
    ("brier", "{:.4f}"),
    ("lead_time", "{:.2f}"),
    ("false_alarm", "{:.4f}"),
    ("episode_recall", "{:.4f}"),
]


def train_lightgbm(
    X_train: np.ndarray, y_train: np.ndarray
) -> tuple[object, float]:
    """Train LightGBM on flattened windows; return (model, train_time_s)."""
    import lightgbm as lgb
    # LightGBM expects 2D: flatten the (window, features) axis.
    X_flat = X_train.reshape(X_train.shape[0], -1)
    model = lgb.LGBMClassifier(
        n_estimators=LGBM_NUM_BOOST, learning_rate=0.05,
        num_leaves=63, class_weight="balanced",
        min_child_samples=20, reg_alpha=0.1, reg_lambda=0.1,
        random_state=SEED, verbose=-1, n_jobs=1,
    )
    start = time.perf_counter()
    model.fit(X_flat, y_train)
    return model, time.perf_counter() - start


def predict_lightgbm(model: object, X_test: np.ndarray) -> np.ndarray:
    """Score held-out windows with the trained LightGBM model."""
    X_flat = X_test.reshape(X_test.shape[0], -1)
    return model.predict_proba(X_flat)[:, 1]


def random_scores(y_test: np.ndarray) -> np.ndarray:
    """Deterministic random baseline — uniform [0, 1] for honest comparison."""
    rng = np.random.default_rng(SEED)
    return rng.uniform(0.0, 1.0, size=y_test.shape[0])


def score_predictions(
    y_true: np.ndarray, y_score: np.ndarray
) -> dict[str, float]:
    """Run the full 6-evaluator production suite on one model's outputs."""
    y_pred = (y_score >= 0.5).astype(int)
    return evaluate_can_model(
        y_true.tolist(), y_pred.tolist(), y_score.tolist()
    )


def render_table(rows: list[dict]) -> str:
    """Render a fixed-width comparison table from per-model metric bundles."""
    name_w = max(len("model"), max(len(str(r["model"])) for r in rows))
    metric_w = max(max(len(k) for k, _ in EVAL_METRICS), 8)
    header_cells = [f"{'model':<{name_w}}"] + [
        f"{k:>{metric_w}}" for k, _ in EVAL_METRICS
    ]
    header = " | ".join(header_cells)
    sep = "-" * len(header)
    body: list[str] = []
    for row in rows:
        cells = [f"{row['model']:<{name_w}}"]
        for key, fmt in EVAL_METRICS:
            val = row["metrics"].get(key)
            rendered = fmt.format(val) if val is not None else "n/a"
            cells.append(f"{rendered:>{metric_w}}")
        body.append(" | ".join(cells))
    return "\n".join([header, sep, *body])


def run_torch(
    name: str, ctor, X_train, y_train, X_test, y_test, in_size
) -> dict:
    """Train one torch model, score it, return a results row."""
    print(f"\n{'=' * 60}\nTraining {name}\n{'=' * 60}")
    model = ctor(input_size=in_size)
    model, t = train_torch_model(
        model, X_train, y_train,
        epochs=DEFAULT_EPOCHS, batch_size=DEFAULT_BATCH,
    )
    print(f"  train_time: {t:.2f}s")
    return {
        "model": name,
        "train_time_s": round(t, 3),
        "metrics": score_predictions(y_test, predict_torch(model, X_test)),
    }


def main() -> None:
    """Train → predict → score → report across LightGBM, LSTM, TCN."""
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    print("=" * 60)
    print("Loading data")
    print("=" * 60)
    X, y = load_combined()
    print(f"  X: {X.shape}  y: {y.shape}  pos_rate: {y.mean():.4f}")

    X_train, y_train, X_test, y_test = temporal_split(X, y)
    print(f"  train: {X_train.shape[0]}  test: {X_test.shape[0]}")

    rows: list[dict] = []

    # ── LightGBM (sklearn-style 2D flatten) ──────────────────────────
    print("\n" + "=" * 60)
    print("Training LightGBM (flattened windows)")
    print("=" * 60)
    lgbm, lgbm_time = train_lightgbm(X_train, y_train)
    print(f"  train_time: {lgbm_time:.2f}s")
    rows.append({
        "model": "LightGBM",
        "train_time_s": round(lgbm_time, 3),
        "metrics": score_predictions(y_test, predict_lightgbm(lgbm, X_test)),
    })

    # ── LSTM + TCN (3D torch) ─────────────────────────────────────────
    rows.append(run_torch("LSTM", LSTMClassifier, X_train, y_train, X_test, y_test, X.shape[2]))
    rows.append(run_torch("TCN", TCNClassifier, X_train, y_train, X_test, y_test, X.shape[2]))

    # ── Random baseline (sanity check) ────────────────────────────────
    print("\n" + "=" * 60)
    print("Random baseline (uniform scores)")
    print("=" * 60)
    rows.append({
        "model": "Random",
        "train_time_s": 0.0,
        "metrics": score_predictions(y_test, random_scores(y_test)),
    })

    # ── Report ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Comparison: 6-evaluator production suite")
    print("=" * 60)
    print(render_table(rows))

    payload = {
        "test_samples": int(X_test.shape[0]),
        "test_positive_rate": float(y_test.mean()),
        "seed": SEED,
        "torch_epochs": DEFAULT_EPOCHS,
        "lgbm_num_boost": LGBM_NUM_BOOST,
        "models": rows,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
