"""CAN ML Training Script - Train and compare LightGBM, Chronos-2, and LNN models."""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

import numpy as np
import joblib

# Add the workspace to path
sys.path.insert(0, "/Users/danielrodrigo/Workspace/python-factory/components/machine_learning/src")

from factory.machine_learning.runtime.ports import (
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
)
from factory.machine_learning.runtime.adapters.timeseries_metrics import (
    compute_classification_metrics,
)
from factory.machine_learning.runtime.adapters.temporal_split import (
    temporal_split_with_shuffle_fallback,
)

# Data paths
X_FLAT_URI = "/Volumes/Crucial X9/can_data/per_can_id/25_X_flat.npy"
X_3D_URI = "/Volumes/Crucial X9/can_data/per_can_id/25_X.npy"
Y_URI = "/Volumes/Crucial X9/can_data/per_can_id/25_y.npy"

# Model storage
MODEL_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/can_ml_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    """Load CAN ID 0x25 data."""
    X_flat = np.load(X_FLAT_URI)
    X_3d = np.load(X_3D_URI)
    y = np.load(Y_URI).ravel()
    print(f"Data loaded: X_flat={X_flat.shape}, X_3d={X_3d.shape}, y={y.shape}")
    print(f"Class distribution: {np.bincount(y.astype(int))}")
    return X_flat, X_3d, y


def train_lightgbm(X_flat, y, seed=42):
    """Train LightGBM baseline model."""
    print("\n" + "="*60)
    print("STEP 1: Training LightGBM (baseline)")
    print("="*60)
    
    try:
        from lightgbm import LGBMClassifier
        
        cfg = TimeSeriesTrainingConfig(window_size=100, seed=seed)
        X_train, y_train, X_val, y_val = temporal_split_with_shuffle_fallback(
            X_flat, y, cfg.validation_split, cfg.seed,
        )
        
        model = LGBMClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=seed, verbose=-1,
        )
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_val)
        y_score = model.predict_proba(X_val)[:, 1]
        metrics = compute_classification_metrics(y_val, y_pred, y_score)
        
        job_id = str(uuid.uuid4())
        model_path = str(MODEL_DIR / f"lightgbm_{job_id}.joblib")
        joblib.dump(model, model_path)
        
        print(f"LightGBM trained successfully!")
        print(f"  AUROC: {metrics.get('auroc', 'N/A'):.4f}")
        print(f"  Model saved: {model_path}")
        
        return {
            "model_type": "lightgbm",
            "status": "success",
            "auroc": metrics.get("auroc"),
            "model_id": job_id,
            "model_path": model_path,
            "metrics": metrics,
        }
    except Exception as e:
        print(f"LightGBM training failed: {e}")
        return {
            "model_type": "lightgbm",
            "status": "failure",
            "auroc": None,
            "error": str(e),
        }


def train_chronos(X_3d, y, seed=42):
    """Train Chronos-2 model."""
    print("\n" + "="*60)
    print("STEP 2: Training Chronos-2")
    print("="*60)
    
    try:
        # Check if HuggingFace token is available
        import os
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not hf_token:
            print("Chronos-2 requires HuggingFace authentication.")
            print("Please set HF_TOKEN environment variable or run: huggingface-cli login")
            return {
                "model_type": "chronos",
                "status": "failure",
                "auroc": None,
                "error": "HuggingFace token required. Set HF_TOKEN env var or run: huggingface-cli login",
            }
        
        from factory.machine_learning.runtime.adapters.chronos_timeseries import ChronosTimeSeriesAdapter
        
        cfg = TimeSeriesTrainingConfig(window_size=100, seed=seed)
        
        # Chronos adapter needs a tracker (can be None for local)
        adapter = ChronosTimeSeriesAdapter(tracker=None)
        
        job = adapter.train(
            model_type=TimeSeriesModelType.chronos,
            X_uri=X_3D_URI,
            y_uri=Y_URI,
            config=cfg,
            experiment_name="can-chronos-test",
        )
        
        print(f"Chronos-2 trained successfully!")
        auroc = job.metrics.get('auroc')
        auroc_str = f"{auroc:.4f}" if auroc else "N/A"
        print(f"  AUROC: {auroc_str}")
        print(f"  Model path: {job.model_path}")
        
        return {
            "model_type": "chronos",
            "status": "success",
            "auroc": job.metrics.get("auroc"),
            "model_id": job.id,
            "model_path": job.model_path,
            "metrics": job.metrics,
        }
    except Exception as e:
        print(f"Chronos-2 training failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "model_type": "chronos",
            "status": "failure",
            "auroc": None,
            "error": str(e),
        }


def train_lnn(X_3d, y, seed=42):
    """Train LNN (Liquid Time-Constant Network) model."""
    print("\n" + "="*60)
    print("STEP 3: Training LNN")
    print("="*60)
    
    try:
        from factory.machine_learning.runtime.adapters.lnn_timeseries import LnnTimeSeriesAdapter
        
        cfg = TimeSeriesTrainingConfig(window_size=100, seed=seed)
        
        # LNN adapter needs a tracker (can be None for local)
        adapter = LnnTimeSeriesAdapter(tracker=None)
        
        job = adapter.train(
            model_type=TimeSeriesModelType.lnn,
            X_uri=X_3D_URI,
            y_uri=Y_URI,
            config=cfg,
            experiment_name="can-lnn-test",
        )
        
        print(f"LNN trained successfully!")
        auroc = job.metrics.get('auroc')
        auroc_str = f"{auroc:.4f}" if auroc else "N/A"
        print(f"  AUROC: {auroc_str}")
        print(f"  Model path: {job.model_path}")
        
        return {
            "model_type": "lnn",
            "status": "success",
            "auroc": job.metrics.get("auroc"),
            "model_id": job.id,
            "model_path": job.model_path,
            "metrics": job.metrics,
        }
    except Exception as e:
        print(f"LNN training failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "model_type": "lnn",
            "status": "failure",
            "auroc": None,
            "error": str(e),
        }


def compare_models(results):
    """Compare all trained models."""
    print("\n" + "="*60)
    print("STEP 4: Model Comparison")
    print("="*60)
    
    successful = [r for r in results if r["status"] == "success"]
    
    if not successful:
        print("No models trained successfully. Cannot compare.")
        return
    
    print(f"\n{'Model Type':<15} {'Status':<10} {'AUROC':<10}")
    print("-" * 35)
    
    for r in results:
        auroc_str = f"{r['auroc']:.4f}" if r.get('auroc') else "N/A"
        print(f"{r['model_type']:<15} {r['status']:<10} {auroc_str:<10}")
    
    if successful:
        best = max(successful, key=lambda x: x.get('auroc') or 0)
        print(f"\nBest model: {best['model_type']} (AUROC: {best.get('auroc', 'N/A'):.4f})")


def main():
    """Main training pipeline."""
    print("="*60)
    print("CAN ID 0x25 ML Training Pipeline")
    print("="*60)
    
    # Load data
    X_flat, X_3d, y = load_data()
    
    results = []
    
    # Step 1: LightGBM
    lgbm_result = train_lightgbm(X_flat, y)
    results.append(lgbm_result)
    
    # Step 2: Chronos-2
    chronos_result = train_chronos(X_3d, y)
    results.append(chronos_result)
    
    # Step 3: LNN
    lnn_result = train_lnn(X_3d, y)
    results.append(lnn_result)
    
    # Step 4: Compare
    compare_models(results)
    
    # Save report
    report_path = MODEL_DIR / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved to: {report_path}")
    
    return results


if __name__ == "__main__":
    results = main()
