#!/usr/bin/env python3
"""
Convert CAN failure data to windowed numpy arrays for time-series training.
"""
import numpy as np
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/.can_training")
WINDOW_SIZE = 10  # Number of consecutive frames per window
STRIDE = 5        # Step between windows

print("Loading sample dataset...")
df = pd.read_csv(OUTPUT_DIR / "can_failures_sample.csv")

# Sort by a synthetic time order (use row order as time proxy)
# In real CAN data, we'd sort by timestamp_ns
feature_cols = [c for c in df.columns if c.startswith("sig_")]
print(f"Features: {feature_cols}")

X_all = df[feature_cols].values.astype(np.float32)
y_all = df["is_failure"].values.astype(np.int64)

print(f"Total samples: {len(X_all)}")
print(f"Failure rate: {y_all.mean():.4f}")

# Create windows
n_samples = len(X_all)
n_windows = (n_samples - WINDOW_SIZE) // STRIDE + 1
print(f"Creating {n_windows} windows (window_size={WINDOW_SIZE}, stride={STRIDE})")

X_windows = np.zeros((n_windows, WINDOW_SIZE, len(feature_cols)), dtype=np.float32)
y_windows = np.zeros(n_windows, dtype=np.int64)

for i in range(n_windows):
    start = i * STRIDE
    end = start + WINDOW_SIZE
    X_windows[i] = X_all[start:end]
    # Label: if any frame in window is a failure, mark as failure
    y_windows[i] = 1 if y_all[start:end].sum() > 0 else 0

print(f"Windowed dataset shape: X={X_windows.shape}, y={y_windows.shape}")
print(f"Window failure rate: {y_windows.mean():.4f}")

# Save as .npy files
X_path = OUTPUT_DIR / "X_windows.npy"
y_path = OUTPUT_DIR / "y_windows.npy"
np.save(X_path, X_windows)
np.save(y_path, y_windows)

print(f"Saved X to {X_path} ({X_path.stat().st_size / 1e6:.1f} MB)")
print(f"Saved y to {y_path} ({y_path.stat().st_size / 1e6:.1f} MB)")

# Also create a smaller quick-test set
QUICK_SIZE = 20000
if n_windows > QUICK_SIZE:
    indices = np.random.RandomState(42).choice(n_windows, QUICK_SIZE, replace=False)
    X_quick = X_windows[indices]
    y_quick = y_windows[indices]
    X_quick_path = OUTPUT_DIR / "X_quick.npy"
    y_quick_path = OUTPUT_DIR / "y_quick.npy"
    np.save(X_quick_path, X_quick)
    np.save(y_quick_path, y_quick)
    print(f"Quick test set: X={X_quick.shape}, y={y_quick.shape}")
    print(f"Quick test failure rate: {y_quick.mean():.4f}")
