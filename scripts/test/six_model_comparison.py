"""End-to-end experiment: train all 6 time-series models on the
injected 15% CAN failure dataset and report a comparison table.

Models trained (in order):
  - LightGBM (sklearn baseline, sklearn aggregator)
  - LSTM (PyTorch, torch adapter)
  - TCN (PyTorch, torch adapter)
  - PatchTST (NEW — patch transformer)
  - Chronos-2 (NEW — T5-style foundation model)
  - LNN (NEW — Liquid Time-Constant Network)

Each model is trained on the same temporal split so the AUROC /
F1 / etc. numbers are directly comparable. Metrics are persisted to
``scripts/output/six_model_comparison.json`` for downstream analysis.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Bound this standalone experiment's CPU use; runtime compatibility comes
# from the workspace package contract, not environment-variable masking.
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

X_URI = "/Volumes/Crucial X9/can_data/injected_131gb_v2/X_injected.npy"
Y_URI = "/Volumes/Crucial X9/can_data/injected_131gb_v2/y_injected.npy"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    # Keep optional heavyweight adapters off the cold path until this
    # standalone portfolio experiment actually runs.
    from factory.machine_learning.runtime.ports import (
        TimeSeriesModelType, TimeSeriesTrainingConfig,
    )
    from factory.machine_learning.runtime.adapters.sklearn_timeseries import (
        SklearnTimeSeriesAdapter,
    )
    from factory.machine_learning.runtime.adapters.torch_timeseries import (
        TorchTimeSeriesAdapter,
    )
    from factory.machine_learning.runtime.adapters.patchtst_timeseries import (
        PatchTSTTimeSeriesAdapter,
    )
    from factory.machine_learning.runtime.adapters.chronos_timeseries import (
        ChronosTimeSeriesAdapter,
    )
    from factory.machine_learning.runtime.adapters.lnn_timeseries import (
        LnnTimeSeriesAdapter,
    )

    # Common config: same window_size, same validation split, same seed.
    # window_size=50 matches the dataset (already windowed into 50-step
    # sequences); batch_size=64 fits comfortably in 16GB RAM for the
    # 60-channel input; epochs=30 with patience=5 prevents overfitting
    # while still giving the transformer / liquid models enough time to
    # converge.
    cfg = TimeSeriesTrainingConfig(
        window_size=50, batch_size=64, epochs=30,
        learning_rate=1e-3, validation_split=0.2, seed=42,
        early_stopping_patience=5,
    )

    # Each family gets its own adapter instance so registries and model
    # roots remain isolated; framework coexistence is package-managed.
    adapters = {
        "lightgbm": ("sklearn", SklearnTimeSeriesAdapter(tracker=None)),
        "lstm":     ("torch",   TorchTimeSeriesAdapter(tracker=None)),
        "tcn":      ("torch",   TorchTimeSeriesAdapter(tracker=None)),
        "patchtst": ("torch",   PatchTSTTimeSeriesAdapter()),
        "chronos":  ("torch",   ChronosTimeSeriesAdapter()),
        "lnn":      ("torch",   LnnTimeSeriesAdapter()),
    }

    # Build a model_type lookup keyed by name.
    model_types = {
        "lightgbm": TimeSeriesModelType.lightgbm,
        "lstm":     TimeSeriesModelType.lstm,
        "tcn":      TimeSeriesModelType.tcn,
        "patchtst": TimeSeriesModelType.patchtst,
        "chronos":  TimeSeriesModelType.chronos,
        "lnn":      TimeSeriesModelType.lnn,
    }

    results: dict[str, dict] = {}
    for name in ["lightgbm", "lstm", "tcn", "patchtst", "chronos", "lnn"]:
        backend, adapter = adapters[name]
        mt = model_types[name]
        print(f"\n=== Training {name} ({backend}) ===", flush=True)
        t0 = time.time()
        try:
            job = adapter.train(mt, X_URI, Y_URI, config=cfg, experiment_name=f"can-15pct-{name}")
            elapsed = time.time() - t0
            metrics = dict(job.metrics)
            metrics["train_time_sec"] = round(elapsed, 1)
            metrics["model_type"] = name
            results[name] = metrics
            print(
                f"  AUROC={metrics.get('auroc', 0):.4f}  "
                f"F1={metrics.get('f1', 0):.4f}  "
                f"Acc={metrics.get('accuracy', 0):.4f}  "
                f"({elapsed:.1f}s)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - t0
            results[name] = {"error": str(exc), "train_time_sec": round(elapsed, 1)}
            print(f"  FAILED: {exc}", flush=True)

    # Build a sorted comparison table.
    print("\n" + "=" * 78)
    print(f"{'Model':<10}  {'AUROC':>7}  {'F1':>7}  {'Acc':>7}  {'Prec':>6}  {'Rec':>6}  {'Time(s)':>8}")
    print("-" * 78)
    rows = []
    for name in ["lightgbm", "lstm", "tcn", "patchtst", "chronos", "lnn"]:
        m = results.get(name, {})
        if "error" in m:
            row = f"{name:<10}  {'ERR':>7}  {'ERR':>7}  {'ERR':>7}  {'ERR':>6}  {'ERR':>6}  {m.get('train_time_sec', 0):>8.1f}"
        else:
            row = (
                f"{name:<10}  "
                f"{m.get('auroc', 0):>7.4f}  "
                f"{m.get('f1', 0):>7.4f}  "
                f"{m.get('accuracy', 0):>7.4f}  "
                f"{m.get('precision', 0):>6.4f}  "
                f"{m.get('recall', 0):>6.4f}  "
                f"{m.get('train_time_sec', 0):>8.1f}"
            )
        rows.append(row)
        print(row)
    print("=" * 78)

    # Persist the full result set for downstream analysis.
    out_path = OUTPUT_DIR / "six_model_comparison.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nFull metrics saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
