#!/usr/bin/env python3
"""
Create flattened windowed data for LightGBM (2D) and keep 3D for LNN.
"""
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/.can_training")

print("Loading windowed data...")
X_train = np.load(OUTPUT_DIR / "X_train.npy")
y_train = np.load(OUTPUT_DIR / "y_train.npy")
X_test = np.load(OUTPUT_DIR / "X_test.npy")
y_test = np.load(OUTPUT_DIR / "y_test.npy")

print(f"Original shapes: X_train={X_train.shape}, X_test={X_test.shape}")

# Flatten for LightGBM: (n_samples, window_size * n_features)
n_train, window_size, n_features = X_train.shape
X_train_flat = X_train.reshape(n_train, -1)
X_test_flat = X_test.reshape(X_test.shape[0], -1)

print(f"Flattened shapes: X_train={X_train_flat.shape}, X_test={X_test_flat.shape}")

# Save flattened versions
np.save(OUTPUT_DIR / "X_train_flat.npy", X_train_flat)
np.save(OUTPUT_DIR / "X_test_flat.npy", X_test_flat)

print("Saved: X_train_flat.npy, X_test_flat.npy")
print(f"Train failure rate: {y_train.mean():.4f}")
print(f"Test failure rate: {y_test.mean():.4f}")
