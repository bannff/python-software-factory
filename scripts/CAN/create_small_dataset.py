#!/usr/bin/env python3
"""
Create smaller dataset for LNN training.
"""
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/.can_training")

print("Loading windowed data...")
X_train = np.load(OUTPUT_DIR / "X_train.npy")
y_train = np.load(OUTPUT_DIR / "y_train.npy")

print(f"Original: X_train={X_train.shape}")

# Take smaller subset for LNN
SUBSET_SIZE = 10000
indices = np.random.RandomState(42).permutation(len(X_train))[:SUBSET_SIZE]
X_small = X_train[indices]
y_small = y_train[indices]

print(f"Subset: X={X_small.shape}, y={y_small.shape}")
print(f"Failure rate: {y_small.mean():.4f}")

np.save(OUTPUT_DIR / "X_train_small.npy", X_small)
np.save(OUTPUT_DIR / "y_train_small.npy", y_small)
print("Saved X_train_small.npy, y_train_small.npy")
