---
name: can-data-guide
description: Critical knowledge about CAN data location, size, and utilization — MANDATORY reading for all CAN-related agents
---
# CAN Data Guide — CRITICAL KNOWLEDGE

**Every agent working with CAN data MUST read this first.**

## The Data You Have (NOT what you think)

| Dataset | Location | Size | Records | Status |
|---------|----------|------|---------|--------|
| **Decoded CAN frames** | `/Volumes/Crucial X9/can_data/decoded_data/` | **131 GB** | **100M+** | **UNUSED — THIS IS YOUR PRIMARY TRAINING SOURCE** |
| Per-CAN-ID windows | `/Volumes/Crucial X9/can_data/per_can_id/` | 360 MB | 20,500 | ⚠️ Tiny subset (500 per ID) |
| MF4 raw captures | `/Volumes/Crucial X9/can_data/mf4_files/` | 7.5 GB | ~100 files | Source data |
| Realistic synthetic | `projects/companion_x/data/realistic_synthetic/` | ~50 MB | 5 CAN IDs | SCANIA-pattern failures |

## What NOT To Do

❌ **DO NOT use `per_can_id/` for training** — only 500 samples per CAN ID (0.02% of available data)
❌ **DO NOT train from scratch each iteration** — use `continue_train()` with `classifier_feedback`
❌ **DO NOT use simple injection** (drop-to-zero, freeze) — use realistic patterns from `generate_realistic_failures.py`
❌ **DO NOT combine datasets** — different feature schemas (23 CAN signals vs 170 SCANIA sensors)

## What TO Do

✅ **Process the 131GB `decoded_data/` through the full pipeline:**
```
decoded_data/*.jsonl (131GB, 100M+ records)
  → can_ingest (parse JSONL)
  → can_profile (compute boundaries)
  → can_synthesize (multiply with multiplier=10-50)
  → can_window (create 100-frame windows)
  → can_augment (jitter/scale)
  → Training-ready NPY arrays
```

✅ **Use the dataset brick to multiply data:**
```python
dataset_submit_generation(
    recipe_uri="recipe://local/can-synthesize@1",
    config={"multiplier": 50, "failure_rate": 0.15, ...}
)
```

✅ **Use realistic failure patterns:**
```python
# Generate failures based on real SCANIA patterns
python projects/companion_x/scripts/generate_realistic_failures.py
```

✅ **Use recursive GAN loop (not from scratch):**
```python
# Iteration 1: cold start
job = ml_train_timeseries(model_type="timegan", X_uri=...)

# Iteration 2+: continue with feedback
job = ml_continue_timeseries(model_id=..., classifier_feedback={"auroc": 0.8})
```

## Key Files

| File | Purpose |
|------|---------|
| `projects/companion_x/scripts/generate_realistic_failures.py` | SCANIA-pattern failure injection |
| `scripts/run_gan_loop_recursive.py` | Recursive GAN loop with feedback |
| `components/machine_learning/.../timegan_loss.py` | Dual-objective loss |
| `.agents/steering/can-failure-prediction.md` | Steering doc with honest assessment |

## Why This Matters

The bottleneck was NEVER data volume — it was data utilization. We have 100M+ decoded CAN records sitting unused. The `per_can_id/` directory only has 500 samples per CAN ID because that's what we extracted for quick experiments. We should be processing the full 131GB through the pipeline.

With 100M+ records × 15% failure rate = 15M+ failure examples, that's more than enough for TimeGAN to learn temporal patterns. With real failure patterns (SCANIA-derived), AUROC should be 0.70-0.80+.
