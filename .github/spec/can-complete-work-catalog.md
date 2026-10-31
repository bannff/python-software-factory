# CAN Failure Prediction — Complete Work Catalog

**Presentation-ready summary of all work done**
**Date:** 2026-07-23
**Presenter:** Daniel Rodrigo

---

## 1. Project Overview

**Goal:** Predict vehicle failures by analyzing CAN bus telemetry data

**Approach:** Agent-driven pipeline using the control-plane runtime substrate with multiple model architectures and synthetic data generation

**Key Insight:** CAN data is high-frequency binary time-series, not conversational text — needs parallel "Signal Pipeline"

---

## 2. Data Inventory

### Data Sources

| Source | Size | Records | Format | Status |
|--------|------|---------|--------|--------|
| **MF4 raw captures** | 7.5 GB | ~100 files | MF4 | ✅ Primary source |
| **Decoded CAN frames** | 131 GB | 100M+ | JSONL | ✅ Processed |
| **Per-CAN-ID windows** | 360 MB | 20,500 | NPY | ✅ Training-ready |
| **Training data** | 263 MB | 59 files | NPY+JSONL | ✅ Augmented |
| **DBC files** | 552 KB | 9 files | DBC | ✅ Signal decoding |
| **SCANIA APS** | 56 MB | 60,000 | CSV | ✅ Real failures |
| **Car-Hacking** | 2.8M records | CSV | Public | ⚠️ Download failed |

### Data Pipeline

```
MF4 (7.5GB) → DBC decode → JSONL (131GB) → Windowing → NPY (360MB) → Training
```

### Critical Finding

**131GB of decoded CAN data is 100% normal driving (no failures).**
- Models trained on this data can't learn failure patterns
- Synthetic injection is the only training signal
- SCANIA APS provides real failure patterns for realistic injection

---

## 3. Model Architectures

### Models Implemented

| Model | Type | Pros | Cons | Best For | Our AUROC |
|-------|------|------|------|----------|-----------|
| **LightGBM** | Gradient-boosted trees | Fast, interpretable, works on small data | Can't learn temporal sequences | Baseline, production | 0.54-0.64 |
| **LSTM** | Recurrent neural network | Learns temporal dependencies | Needs more data, slower | Complex patterns | 0.50-0.59 |
| **TCN** | Temporal convolutional | Ultra-low latency, parallelizable | Fixed receptive field | Real-time inference | 0.39-0.86 |
| **TimeGAN** | Adversarial generative | Learns temporal dynamics | Unstable, data-hungry | Synthetic data | N/A |

### Model Comparison Results

| Experiment | LightGBM | LSTM | TCN | Best | Notes |
|------------|----------|------|-----|------|-------|
| Simple injection (500 samples) | 0.642 | 0.559 | **0.864** | TCN | First run |
| Recursive improvement | 0.503 | 0.574 | **0.605** | TCN | Same model continues |
| Realistic SCANIA patterns | 0.560 | **0.800** | 0.740 | LSTM | +0.15 improvement |

**Key Insight:** Data quality > Model architecture. LSTM wins on realistic patterns, TCN wins on simple injection.

---

## 4. Training Methods

### Methods Implemented

| Method | Description | Status | AUROC |
|--------|-------------|--------|-------|
| **Per-CAN-ID training** | Train separate model for each CAN ID | ✅ Implemented | 0.50-0.86 |
| **Synthetic injection** | Inject 8 failure modes into normal data | ✅ Implemented | 0.50-0.60 |
| **Realistic SCANIA patterns** | Use real failure patterns from SCANIA trucks | ✅ Implemented | 0.70-0.80 |
| **TimeGAN synthesis** | GAN learns temporal patterns from real failures | ✅ Implemented | 0.50-0.60 |
| **Recursive GAN loop** | Continue training same model across iterations | ✅ Implemented | +0.12 improvement |

### Synthetic Failure Modes

| Mode | Description | Realistic? |
|------|-------------|------------|
| **dropout** | Signal drops to zero | ❌ Low |
| **drift** | Signal gradually increases/decreases | ⚠️ Medium |
| **stuck_value** | Signal frozen at constant value | ❌ Low |
| **spike** | Sudden amplitude spike | ⚠️ Medium |
| **correlation_break** | Break correlation between signals | ⚠️ Medium |
| **out_of_sequence** | Frames arrive out of order | ❌ Low |
| **sensor_degradation** | Signal becomes noisy | ⚠️ Medium |
| **ecu_timeout** | ECU stops responding | ❌ Low |

---

## 5. Experiments Run

### Experiment Matrix

| Experiment | Samples | Injection | Models | AUROC Range | Key Finding |
|------------|---------|-----------|--------|-------------|-------------|
| **Baseline (500 samples)** | 500/ID | Simple | LGB/LSTM/TCN | 0.50-0.60 | Near random |
| **Recursive GAN (8 iterations)** | 500/ID | TimeGAN | LGB/LSTM/TCN | 0.39-0.66 | TCN +0.12 |
| **Realistic SCANIA** | 500/ID | SCANIA patterns | LGB/RF/GB | 0.70-0.80 | Best so far |
| **Full dataset (424K)** | 424K | None | LGB | N/A | 0% failure rate |

### Key Results

| Metric | Simple Injection | SCANIA Patterns | Improvement |
|--------|------------------|-----------------|-------------|
| **Avg AUROC** | 0.50-0.60 | 0.70-0.80 | **+0.15** |
| **Best model** | TCN (0.86) | RandomForest (0.80) | Architecture shift |
| **Failure diversity** | 8 modes | 8 + SCANIA-learned | More realistic |

---

## 6. Infrastructure Built

### Bricks Extended

| Brick | New Features | Files |
|-------|--------------|-------|
| **dataset** | can_synthesize, can_augment, scania_pattern_extractor | 6 adapters |
| **machine_learning** | TimeGAN, ConditionalTimeGAN, recursive training | 8 adapters |
| **evals** | can_auroc, can_auprc, can_brier + 3 more | 6 evaluators |
| **agent** | can-analyst, can-gan-loop skills | 2 skills |

### MCP Tools Added

| Tool | Purpose |
|------|---------|
| `ml_train_timeseries` | Train LightGBM/LSTM/TCN/TimeGAN |
| `ml_continue_timeseries` | Continue training with feedback |
| `ml_sample_timeseries` | Generate synthetic data |
| `evals_evaluate_computational` | Score with CAN evaluators |
| `dataset_submit_generation` | Process CAN data pipeline |

### Files Created

| File | LOC | Purpose |
|------|-----|---------|
| `timegan.py` | 199 | TimeGAN adapter |
| `timegan_loss.py` | 128 | Dual-objective loss |
| `timegan_conditional.py` | 200 | Conditional TimeGAN |
| `scania_pattern_extractor.py` | 181 | SCANIA pattern extraction |
| `failure_injection.py` | 173 | Hybrid failure injection |
| `can-gan-loop/SKILL.md` | 220 | GAN loop skill |
| `can-data-guide/SKILL.md` | 89 | Data guide skill |

---

## 7. Challenges & Solutions

### Challenge 1: Data Utilization
**Problem:** 131GB decoded data but only 500 samples per CAN ID used
**Solution:** Process full dataset through pipeline, use SCANIA patterns for realistic injection

### Challenge 2: No Real Failure Data
**Problem:** All CAN data is 100% normal driving
**Solution:** Download SCANIA APS (real failures), extract patterns, inject realistically

### Challenge 3: Models Detect Injection Method
**Problem:** AUROC 0.97-1.00 on synthetic data, but detecting injection not failures
**Solution:** Use realistic SCANIA patterns, multi-signal correlated injection

### Challenge 4: GAN Loop Not Improving
**Problem:** Identical AUROC across iterations (0.80, 0.80, 0.80)
**Solution:** Wire feedback loop, dual-objective loss, temperature-varied noise

### Challenge 5: Simple Injection Too Realistic
**Problem:** Single-signal mutations (drop-to-zero) are too easy to detect
**Solution:** Multi-signal correlated failures, gradual onset/decay

---

## 8. What's Next

### Immediate (This Week)
1. ✅ SCANIA pattern extraction (done)
2. ✅ Conditional TimeGAN (done)
3. ✅ Hybrid failure injection (done)
4. **Test full pipeline** — use the control-plane runtime MCP tools
5. **Run comprehensive experiments** — compare all approaches

### Short-term (Next 2 Weeks)
1. **Correlation-based injection** — use can_profile correlation matrix
2. **Gradual onset/decay** — smooth transitions instead of hard windows
3. **Full dataset training** — process 131GB with realistic failures
4. **Presentation preparation** — catalog all results

### Long-term (Next Month)
1. **Real failure data** — get vehicle service records
2. **Cross-dataset validation** — test on different vehicles
3. **Production deployment** — edge inference on live CAN bus

---

## 9. Key Metrics Summary

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **AUROC (simple injection)** | 0.50-0.60 | 0.70+ | ⚠️ Needs improvement |
| **AUROC (SCANIA patterns)** | 0.70-0.80 | 0.80+ | ✅ On track |
| **Dataset size** | 20,500 samples | 1M+ samples | ⚠️ Need to process 131GB |
| **Failure diversity** | 8 modes | 8 + learned | ✅ Hybrid approach ready |
| **Model comparison** | 3 architectures | All compared | ✅ LightGBM/LSTM/TCN |

---

## 10. Files for Presentation

| File | Content |
|------|---------|
| `can-gan-loop-report.md` | Experiment results |
| `can-failure-prediction.md` | Domain spec |
| `rando-vision.md` | High-level vision |
| `can-data-guide/SKILL.md` | Data utilization guide |
| This file | Complete work catalog |

---

## 11. Demo Script

### Live Demo Steps

1. **Show data inventory**
   - 131GB decoded CAN frames
   - 20,500 training samples
   - SCANIA APS with real failures

2. **Run simple injection experiment**
   - 500 samples, 8 failure modes
   - Train LightGBM/LSTM/TCN
   - Show AUROC ~0.50-0.60

3. **Run SCANIA pattern injection**
   - Same 500 samples, realistic patterns
   - Train same models
   - Show AUROC ~0.70-0.80 (+0.15 improvement)

4. **Compare architectures**
   - LightGBM: Fast, interpretable
   - LSTM: Best on realistic patterns
   - TCN: Best for real-time

5. **Show recursive improvement**
   - TimeGAN continues training
   - TCN improves +0.12 across iterations

---

**Document version:** 1.0
**Last updated:** 2026-07-23
