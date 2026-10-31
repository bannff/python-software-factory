"""End-to-end example: Train LightGBM, LSTM, and TCN on windowed CAN JSONL data.

This script demonstrates the complete workflow:
1. Inspect the JSONL file to understand the data shape
2. Convert JSONL → NPY for both 3D (torch) and 2D (sklearn) layouts
3. Train all three model architectures
4. Compare model performance

Usage:
    python examples/train_can_models.py /path/to/windows.jsonl /path/to/output
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the workspace to the path so we can import factory modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from factory.machine_learning import (
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    convert_jsonl_to_npy,
    get_runtime,
    inspect_jsonl_windows,
)


def main(jsonl_path: str, output_dir: str) -> None:
    """Train LightGBM, LSTM, and TCN on windowed CAN data."""

    # ── Step 1: Inspect the data ──────────────────────────────────────────
    print("=" * 60)
    print("Step 1: Inspecting JSONL data")
    print("=" * 60)

    info = inspect_jsonl_windows(jsonl_path)
    print(f"  n_samples:      {info['n_samples']}")
    print(f"  window_size:    {info['window_size']}")
    print(f"  n_features:     {info['n_features']}")
    print(f"  label_dist:     {info['label_distribution']}")
    print(f"  signal_names:   {info['signal_names'][:5]}...")

    window_size = info["window_size"]
    n_features = info["n_features"]

    # ── Step 2: Convert JSONL → NPY ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 2: Converting JSONL → NPY")
    print("=" * 60)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 3D layout for LSTM/TCN: (n_samples, window_size, n_features)
    X_3d_uri, y_3d_uri = convert_jsonl_to_npy(
        jsonl_path,
        output_path / "torch",
        layout="3d",
        prefix="can",
    )
    print(f"  3D arrays (torch):  {X_3d_uri}")

    # 2D layout for LightGBM: (n_samples, window_size * n_features)
    X_2d_uri, y_2d_uri = convert_jsonl_to_npy(
        jsonl_path,
        output_path / "sklearn",
        layout="2d",
        prefix="can",
    )
    print(f"  2D arrays (sklearn): {X_2d_uri}")

    # ── Step 3: Configure training ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 3: Configuring training")
    print("=" * 60)

    # Config for 500-timestep windows with variable features
    config = TimeSeriesTrainingConfig(
        window_size=window_size,       # Match the actual window size
        stride=50,                     # Not used for pre-windowed data
        batch_size=32,                 # Reasonable for 25K samples
        epochs=50,                     # With early stopping
        learning_rate=1e-3,            # Default Adam LR
        validation_split=0.2,          # 20% for validation
        seed=42,                       # Reproducibility
        early_stopping_patience=10,    # Stop if no improvement for 10 epochs
    )
    print(f"  window_size:       {config.window_size}")
    print(f"  batch_size:        {config.batch_size}")
    print(f"  epochs:            {config.epochs}")
    print(f"  learning_rate:     {config.learning_rate}")
    print(f"  validation_split:  {config.validation_split}")
    print(f"  early_stopping:    {config.early_stopping_patience}")

    # ── Step 4: Train models ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 4: Training models")
    print("=" * 60)

    runtime = get_runtime()
    trainer = runtime.get_timeseries_trainer(backend="torch")

    # Train LightGBM (uses 2D arrays)
    print("\n  Training LightGBM...")
    lgbm_job = trainer.train(
        model_type=TimeSeriesModelType.lightgbm,
        X_uri=X_2d_uri,
        y_uri=y_2d_uri,
        config=config,
        experiment_name="can-failure-prediction",
    )
    print(f"    job_id:  {lgbm_job.id}")
    print(f"    status:  {lgbm_job.status}")
    print(f"    auroc:   {lgbm_job.metrics.get('auroc', 'N/A'):.4f}")

    # Train LSTM (uses 3D arrays)
    print("\n  Training LSTM...")
    lstm_job = trainer.train(
        model_type=TimeSeriesModelType.lstm,
        X_uri=X_3d_uri,
        y_uri=y_3d_uri,
        config=config,
        experiment_name="can-failure-prediction",
    )
    print(f"    job_id:  {lstm_job.id}")
    print(f"    status:  {lstm_job.status}")
    print(f"    auroc:   {lstm_job.metrics.get('auroc', 'N/A'):.4f}")

    # Train TCN (uses 3D arrays)
    print("\n  Training TCN...")
    tcn_job = trainer.train(
        model_type=TimeSeriesModelType.tcn,
        X_uri=X_3d_uri,
        y_uri=y_3d_uri,
        config=config,
        experiment_name="can-failure-prediction",
    )
    print(f"    job_id:  {tcn_job.id}")
    print(f"    status:  {tcn_job.status}")
    print(f"    auroc:   {tcn_job.metrics.get('auroc', 'N/A'):.4f}")

    # ── Step 5: Compare models ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 5: Comparing models")
    print("=" * 60)

    comparison = trainer.compare_models(
        [lgbm_job.id, lstm_job.id, tcn_job.id],
        metric="auroc",
    )
    print(f"  Best model: {comparison['best_model_id']}")
    print(f"  Metric:     {comparison['metric']}")
    print("\n  Rankings:")
    for i, model in enumerate(comparison["models"], 1):
        print(f"    {i}. {model['id'][:8]}... ({model['model_type']}) "
              f"auroc={model['auroc']:.4f}")

    # ── Step 6: List all trained models ───────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 6: All trained models")
    print("=" * 60)

    models = trainer.list_models()
    for m in models:
        print(f"  {m['id'][:8]}... | {m['model_type']:10s} | "
              f"auroc={m.get('auroc', 'N/A')} | {m['model_path']}")

    print("\n" + "=" * 60)
    print("Done! Models trained and saved.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <jsonl_path> <output_dir>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
