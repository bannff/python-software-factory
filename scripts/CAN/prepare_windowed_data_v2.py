#!/usr/bin/env python3
"""
Create properly balanced windowed CAN failure dataset.
"""
import numpy as np
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/.can_training")
WINDOW_SIZE = 10
STRIDE = 5

print("Loading full dataset...")
df = pd.read_csv(OUTPUT_DIR / "can_failures_full.csv")

feature_cols = [c for c in df.columns if c.startswith("sig_")]
print(f"Features: {feature_cols}")
print(f"Total records: {len(df)}")
print(f"Failure rate: {df['is_failure'].mean():.4f}")

# Create windows
X_all = df[feature_cols].values.astype(np.float32)
y_all = df["is_failure"].values.astype(np.int64)
n_samples = len(X_all)

n_windows = (n_samples - WINDOW_SIZE) // STRIDE + 1
print(f"Creating {n_windows} windows")

X_windows = np.zeros((n_windows, WINDOW_SIZE, len(feature_cols)), dtype=np.float32)
y_windows = np.zeros(n_windows, dtype=np.int64)

for i in range(n_windows):
    start = i * STRIDE
    end = start + WINDOW_SIZE
    X_windows[i] = X_all[start:end]
    y_windows[i] = 1 if y_all[start:end].sum() > 0 else 0

print(f"Windowed shape: X={X_windows.shape}, y={y_windows.shape}")
print(f"Window failure rate: {y_windows.mean():.4f}")

# Split into train (80%) and test (20%)
n_train = int(n_windows * 0.8)
indices = np.random.RandomState(42).permutation(n_windows)
train_idx = indices[:n_train]
test_idx = indices[n_train:]

X_train, y_train = X_windows[train_idx], y_windows[train_idx]
X_test, y_test = X_windows[test_idx], y_windows[test_idx]

print(f"\nTrain: X={X_train.shape}, y={y_train.shape}, failure_rate={y_train.mean():.4f}")
print(f"Test:  X={X_test.shape}, y={y_test.shape}, failure_rate={y_test.mean():.4f}")

# Save
np.save(OUTPUT_DIR / "X_train.npy", X_train)
np.save(OUTPUT_DIR / "y_train.npy", y_train)
np.save(OUTPUT_DIR / "X_test.npy", X_test)
np.save(OUTPUT_DIR / "y_test.npy", y_test)

print(f"\nSaved to {OUTPUT_DIR}")
print("Files: X_train.npy, y_train.npy, X_test.npy, y_test.npy")
