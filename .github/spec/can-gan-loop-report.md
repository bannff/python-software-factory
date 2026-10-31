# CAN GAN Loop — Experiment Report

**Date:** 2026-07-21
**Status:** Active experimentation
**Epic:** python-factory-dth

---

## 1. Model Options

| Model | Type | Pros | Cons | Best For |
|-------|------|------|------|----------|
| **LightGBM** | Gradient-boosted trees | Fast training (<1s), interpretable feature importance, works on small data, low memory | Can't learn temporal sequences, misses cross-signal correlations | Baseline, production deployment |
| **LSTM** | Recurrent neural network | Learns temporal dependencies, handles variable-length sequences, captures time-series patterns | Needs more data per class, slower training, prone to overfitting on small datasets | Complex temporal patterns |
| **TCN** | Temporal convolutional | Parallelizable, ultra-low latency (<1ms inference), stable training, good for fixed windows | Fixed receptive field, may miss long-range dependencies | Real-time inference |
| **TimeGAN** | Adversarial generative | Learns temporal dynamics, generates realistic sequences, captures cross-signal correlations | Unstable training, needs substantial data, mode collapse risk | Synthetic data generation |
| **GaussianCopula** | Statistical generative | Simple, stable, fast, works on small data | Ignores temporal patterns, samples independently per signal | Quick baseline (not for CAN) |

**Verdict:** LightGBM for production baseline. LSTM for complex patterns. TCN for real-time. TimeGAN for synthetic data generation.

---

## 2. Training Methods

| Method | Pros | Cons | Use Case |
|--------|------|------|----------|
| **Per-CAN-ID training** | Specialized models, avoids cross-signal noise, interpretable | 82+ models to maintain, no cross-ID generalization | Current approach |
| **Multi-CAN-ID unified** | Single model, cross-signal learning, simpler deployment | Mixed signals confuse model, lower accuracy on individual IDs | Future exploration |
| **Synthetic injection** | No real fault data needed, bootstraps training, legitimate weak-supervision technique | Models detect injection method, not real failures, AUROC inflated | Current labels |
| **TimeGAN synthesis** | Learns temporal patterns, realistic sequences, improves with iterations | Unstable, data-hungry, needs tuning | Synthetic data generation |
| **Transfer learning** | Leverages pre-trained patterns, less data needed | Domain mismatch, may not transfer across vehicles | Future exploration |

**Verdict:** Per-CAN-ID + TimeGAN synthesis for current. Multi-ID unified for future scale.

---

## 3. Experiments Run

### Experiment Matrix — All Approaches (FINAL RESULTS)

| Approach | LightGBM | LSTM | TCN | Average | Best | Notes |
|----------|----------|------|-----|---------|------|-------|
| **Baseline** | 0.500 | 0.500 | 0.500 | 0.500 | — | Original data, no injection |
| **Correlation-based** | **1.000** | 0.431 | 0.407 | 0.613 | LightGBM | Good for trees, hard for neural nets |
| **Realistic SCANIA** | **1.000** | 0.500 | **1.000** | **0.833** | LightGBM/TCN | **WINNER** — best balance |
| **TimeGAN (Recursive)** | **1.000** | **1.000** | **1.000** | 1.000 | All | ⚠️ Possibly overfitting |
| **Hybrid (70/30)** | 0.562 | 0.497 | 0.500 | 0.520 | LightGBM | Dilutes signal quality |

### Key Findings

1. **Realistic SCANIA wins** — AUROC 0.83 average, both LightGBM and TCN achieve 1.0
2. **TimeGAN perfect scores** — but likely overfitting to synthetic artifacts
3. **Correlation-based** — easy for trees (AUROC 1.0) but hard for neural nets (0.40-0.43)
4. **Hybrid underperforms** — mixing 70% trivial rules with 30% learned dilutes the signal
5. **Baseline is hard** — original CAN data has nearly identical normal/failure distributions

### Recommendation

**Use Realistic SCANIA patterns** — best balance of challenge and learnability across architectures. Supplement with TimeGAN for complex temporal patterns if needed.

---

## 4. Evaluations Performed

| Evaluator | What It Measures | Threshold | Status |
|-----------|------------------|-----------|--------|
| **can_auroc** | Discrimination (ROC curve) | ≥0.80 | ✅ Implemented, wired |
| **can_auprc** | Precision-recall balance | ≥0.75 | ✅ Implemented, wired |
| **can_brier** | Calibration (probability accuracy) | ≤0.15 | ✅ Implemented, wired |
| **can_lead_time** | How far before failure model detects | ≥5s | ✅ Implemented, not auto-invoked |
| **can_false_alarm** | False positive rate | ≤0.10 | ✅ Implemented, not auto-invoked |
| **can_episode_recall** | Episode-level detection rate | ≥0.80 | ✅ Implemented, not auto-invoked |

**Evaluation pipeline:**
- `evals_evaluate_computational` — runs individual evaluator
- `evals_record_run` — persists to evals brick for dashboard
- `evals_get_run_regression` — compares iterations

**Gap:** 3 evaluators (lead_time, false_alarm, episode_recall) implemented but not auto-invoked by training loop. Only AUROC/AUPRC/Brier are automatic.

---

## 5. Dataset and Size

| Dataset | Location | Size | Records | Format | Real Failures? |
|---------|----------|------|---------|--------|----------------|
| Raw MF4 captures | `$DATA_ROOT/mf4_files/` | 7.5 GB | ~100 files | MF4 | ❌ Normal driving |
| Decoded CAN frames | `$DATA_ROOT/decoded_data/` | **131 GB** | **100M+** | JSONL | ❌ 100% normal |
| Per-CAN-ID windows | `$DATA_ROOT/per_can_id/` | 360 MB | 82 IDs × 500 windows | NPY | ❌ Synthetic injection |
| Training data | `$DATA_ROOT/training_data/` | 263 MB | 59 files | NPY + JSONL | ❌ Synthetic injection |
| DBC files | `$DATA_ROOT/dbc_files/` | 552 KB | 9 files | DBC | N/A |

**Critical Finding: NO REAL FAILURE DATA EXISTS**

All CAN data is 100% normal operation. The AUROC 0.97-1.00 numbers are based on **synthetic failure injection**, not real-world failures. The models detect "did I insert a drop-to-zero mutation" — not "will this vehicle actually fail."

**Why datasets can't be combined:**

| Dataset | Feature Schema | Label Schema | Data Type |
|---------|----------------|--------------|-----------|
| CAN decoded | 23 vehicle-specific signals | `is_failure` (0/1) | Time-series |
| Combined 5M | Different signal names | No labels | Time-series |
| SCANIA APS | 170 tabular features | `class` (pos/neg) | Tabular snapshot |
| Car-Hacking | Unknown (corrupted) | Unknown | Unknown |

**To get real failure data:**
1. Download SCANIA APS (real workshop repair records, different feature space)
2. Get real DTC-linked fault data from vehicles (same feature space, but hard to source)
3. Use EngineAD (real multivariate sensor telemetry with expert-annotated labels)

**Data pipeline:**
```
MF4 (7.5GB) → DBC decode → JSONL (131GB) → Windowing → NPY (360MB) → Training
```

**External drive:** All data lives on `/Volumes/Crucial X9/can_data/`. Portable to any laptop via `DATA_ROOT` env var.

---

## 6. Next Steps to Scale

### Current Limitation: Per-CAN-ID Models

| Problem | Impact | Solution |
|---------|--------|----------|
| 82 CAN IDs = 82 models | Maintenance burden, storage overhead | Multi-ID unified model |
| No cross-ID generalization | Can't detect patterns spanning multiple signals | Transfer learning |
| Manual CAN ID selection | Requires domain expertise | Auto-discovery via profiling |

### Scaling Architecture

**Option A: One Model Per Client (Current)**
```
Client A → CAN ID 0x25 model → Predictions
Client A → CAN ID 0x2C1 model → Predictions
...
Client A → CAN ID 0xXXX model → Predictions (82 models)
```
- Pros: Specialized, interpretable, isolated
- Cons: 82× storage, no cross-signal learning, manual maintenance

**Option B: Unified Multi-ID Model**
```
Client A → All CAN IDs → Single model → Predictions
```
- Pros: One model, cross-signal learning, simpler deployment
- Cons: May lose specificity, needs more training data, harder to debug

**Option C: Hierarchical (Recommended)**
```
Client A → Profile CAN IDs → Cluster similar IDs → Train cluster models → Predictions
```
- Pros: Balances specificity and generalization, auto-discovery, scalable
- Cons: More complex pipeline, needs clustering logic

### Scaling Plan

| Phase | Goal | Work |
|-------|------|------|
| **Phase 1** (now) | Validate approach | Per-CAN-ID TimeGAN + 3 classifiers, 8 experiments |
| **Phase 2** | Multi-ID training | Train unified model on all 82 CAN IDs, compare vs per-ID |
| **Phase 3** | Auto-profiling | Auto-discover CAN IDs from MF4, cluster similar signals |
| **Phase 4** | Fleet deployment | One model per vehicle type, transfer learning across fleet |
| **Phase 5** | Real-time inference | Sub-ms prediction on live CAN bus, edge deployment |

### Real-Time Requirements

| Requirement | Target | Current |
|-------------|--------|---------|
| Inference latency | <5ms per window | TCN: <1ms ✅ |
| Throughput | 1000+ predictions/sec | LightGBM: ~10K/sec ✅ |
| Memory | <100MB per model | All models <50MB ✅ |
| Model size | <10MB for edge | All models <5MB ✅ |

### Production Recommendations

1. **Start with LightGBM** — fastest to deploy, interpretable, good enough accuracy
2. **Add TCN for real-time** — when latency matters more than accuracy
3. **Use LSTM for complex patterns** — when temporal relationships are critical
4. **TimeGAN for data augmentation** — generate training data for new CAN IDs
5. **Per-vehicle profiling** — each vehicle gets its own model cluster
6. **Transfer learning** — pre-train on fleet data, fine-tune per client

### Deployment Architecture

```
Vehicle CAN Bus → MF4 Capture → Ingest Pipeline → Windowing → Model Ensemble → Alerts
                                      ↓
                              TimeGAN Generator
                                      ↓
                              Synthetic Data Store
                                      ↓
                              Model Retraining (weekly)
```

---

## Files

- Report: `.github/spec/can-gan-loop-report.md` (this file)
- Skill: `components/agent/src/factory/agent/skills/can-gan-loop/SKILL.md`
- Agent: `components/agent/src/factory/agent/registry/defaults_can_agents.py`
- Steering: `.agents/steering/can-failure-prediction.md`
- Results: `/Volumes/Crucial X9/can_data/gan_loop_results/`

---

**Next:** Run iterations 9-10 to complete the demo dataset, then generate charts.
