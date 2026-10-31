#!/usr/bin/env python3
"""
Prepare CAN failure prediction dataset for training.
Loads JSONL data, extracts features and labels, saves as CSV for MCP consumption.
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path("/Users/danielrodrigo/Workspace/python-factory/.dataset_store/artifacts/48501e24-a155-43d4-a168-0563cf7cb00b/dataset-50f5ddac2b7224fdc812826bf95b2146fe501538cb641e6b6aa14635a47c64ed.jsonl")
OUTPUT_DIR = Path("/Users/danielrodrigo/Workspace/python-factory/.can_training")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_RECORDS = 500000  # Sample for initial training

print("Loading dataset...")
records = []
count = 0
with open(DATA_PATH) as f:
    for line in f:
        if count >= MAX_RECORDS:
            break
        record = json.loads(line)
        signals = record.get("decoded_signals", {})
        row = {
            "is_failure": record.get("is_failure", 0),
        }
        # Add all decoded signals as features
        for key, value in signals.items():
            row[f"sig_{key}"] = float(value) if value is not None else 0.0
        records.append(row)
        count += 1
        if count % 100000 == 0:
            print(f"  Loaded {count} records...")

print(f"Loaded {len(records)} records")

df = pd.DataFrame(records)
print(f"\nDataset shape: {df.shape}")
print(f"\nFailure distribution:")
print(df["is_failure"].value_counts())
print(f"\nFailure rate: {df['is_failure'].mean():.4f}")
print(f"\nFeature columns: {[c for c in df.columns if c.startswith('sig_')]}")

# Save full dataset
full_path = OUTPUT_DIR / "can_failures_full.csv"
df.to_csv(full_path, index=False)
print(f"\nSaved full dataset to {full_path}")

# Also save a smaller balanced sample for quick testing
failures = df[df["is_failure"] == 1]
normals = df[df["is_failure"] == 0]

sample_size = min(50000, len(normals))
sampled_normals = normals.sample(n=sample_size, random_state=42)
sampled_df = pd.concat([failures, sampled_normals]).sample(frac=1, random_state=42)

sample_path = OUTPUT_DIR / "can_failures_sample.csv"
sampled_df.to_csv(sample_path, index=False)
print(f"Saved sample dataset ({len(sampled_df)} records) to {sample_path}")

# Save feature list
feature_cols = [c for c in df.columns if c.startswith("sig_")]
with open(OUTPUT_DIR / "feature_columns.txt", "w") as f:
    f.write("\n".join(feature_cols))
print(f"Feature columns: {feature_cols}")
