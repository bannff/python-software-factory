---
name: can-gan-loop
description: Closed-loop adversarial CAN synthesis — multi-model comparison with recursive TimeGAN improvement
---
# CAN GAN Loop

You orchestrate a closed-loop adversarial CAN synthesis system. Each iteration:
1. **Trains/continues TimeGAN** on real CAN data to learn temporal patterns
2. **Generates synthetic data** with TimeGAN (not GaussianCopula) using temperature-varied latent noise
3. **Trains all three architectures** (LightGBM, LSTM, TCN) on the synthetic data
4. **Compares models** via 6 evaluators
5. **Records everything** in the control-plane runtime evals brick for dashboard visualization
6. **Feeds the averaged AUROC back to TimeGAN** so the next iteration's generator loss actually redirects the model

## Design Goals

1. **TimeGAN-first** — use TimeGAN for synthesis (learns temporal patterns), NOT GaussianCopula
2. **Multi-model comparison** — train LightGBM + LSTM + TCN each iteration, compare via 6 evaluators
3. **Recursive improvement** — TimeGAN must actually improve each iteration; the
   feedback loop is what makes it recursive, not just re-running with a new seed
4. **Demo-ready** — record enough data points for charts showing model comparison and iterative improvement
5. **Portable** — all data on external drive (`/Volumes/Crucial X9/can_data/`), plug into any laptop and run

## Recursive Improvements (the dual-objective loss)

The TimeGAN generator loss is **not** a plain BCE anymore. The
`timegan_loss` module replaces the scalar BCE multiplier (which
couldn't change the gradient direction) with a **dual objective**:

1. **Adversarial BCE (weakened as AUROC rises)**
   - The standard ``G fools D`` loss, but its weight is a linear
     taper: 1.0 at AUROC ≤ 0.5, 0.2 at AUROC = 1.0.
   - Rationale: at high AUROC, the discriminator is already
     powerful; further adversarial push causes G/D overshoot.
2. **Diversity loss** — penalises low per-feature standard deviation
   across the generated batch. Without this, the generator collapses
   to a single mode and classifier AUROC plateaus near chance.
   - ``div_loss = 1 / (1 + 10 · std)``; ~1.0 for collapsed output,
     ~0.02 for a healthy diverse batch.
3. **One-sided label smoothing on D when AUROC > 0.75**
   - Real label target drops from 1.0 to 0.9. Standard GAN trick to
     stop the discriminator from saturating and starving G.

The `continue_train` API accepts `classifier_feedback={"auroc": x}`
which feeds the AUROC scalar into both the adversarial weight taper
and the label-smoothing threshold.

## Data Inventory — CRITICAL: Use What You Have

| Dataset | Location | Size | Records | Use |
|---------|----------|------|---------|-----|
| **Decoded CAN frames** | `$DATA_ROOT/decoded_data/` | **131 GB** | **100M+** | **PRIMARY TRAINING SOURCE** |
| Per-CAN-ID windows | `$DATA_ROOT/per_can_id/` | 360 MB | 20,500 samples | ⚠️ Only 0.02% of available data |
| Training data | `$DATA_ROOT/training_data/` | 263 MB | 59 files | Small subset |
| DBC files | `$DATA_ROOT/dbc_files/` | 552 KB | 9 files | Signal decoding |

**DO NOT USE `per_can_id/` for training** — it only has 500 samples per CAN ID. You're sitting on 131GB of decoded data!

**Correct approach:** Process the 131GB `decoded_data/` through the full pipeline:
```
decoded_data/*.jsonl (131GB, 100M+ records)
  → can_ingest (parse JSONL)
  → can_profile (compute boundaries)
  → can_synthesize (multiply with multiplier=10-50)
  → can_window (create 100-frame windows)
  → can_augment (jitter/scale)
  → Training-ready NPY arrays
```

**Why multiply isn't needed if you use the full dataset:**
- 100M+ records × 15% failure rate = 15M+ failure examples
- That's more than enough for TimeGAN to learn temporal patterns
- The bottleneck was always data utilization, not data volume

**If you DO want to multiply** (for faster iteration or smaller experiments):
- Use `dataset_submit_generation` with `recipe://local/can-synthesize@1`
- Config: `{"multiplier": 10, "failure_rate": 0.15}`
- This creates 10x more synthetic data from the decoded frames

## Do NOT Combine Datasets

Different datasets have incompatible schemas:
- Your CAN data: 23 vehicle-specific signals
- SCANIA APS: 170 anonymized sensors
- **Cannot merge directly** — different feature spaces

**But you CAN use real patterns:** The `generate_realistic_failures.py` script extracts failure patterns from SCANIA APS and injects them into CAN data. This produces AUROC 0.70-0.80 vs 0.50-0.60 for simple injection.

## Loop Protocol

### Initialization
1. Check for existing state (iteration number, best scores per model)
2. If no state exists, start from iteration 0
3. Load real CAN data from `$DATA_ROOT/per_can_id/` or `$DATA_ROOT/training_data/`
4. Initialise a single `TimeGANAdapter` instance — its on-disk registry
   preserves the parent→child checkpoint chain across iterations

### Each Iteration

**Step 1: Train (iter 1) or continue-train (iter 2+) TimeGAN**
- **Iteration 1:** call `ml_train_timeseries` with `model_type="timegan"`
  and `parent_model_id=None` to cold-start. This is the *only* iteration
  that should ever cold-start a new generator.
- **Iteration 2+:** call `ml_continue_timeseries` with
  - `model_id = <previous iteration's timegan_model_id>` (NOT a
    new `train` call with a different seed — that's what iter5-8 did
    wrong, and it never actually loaded the previous checkpoint)
  - `X_uri` = real CAN windowed data
  - `classifier_feedback = {"auroc": avg_auroc_prev_iter}` — the
    single scalar that activates the dual-objective loss
- Config: `epochs_reconstruction=50-60`, `epochs_adversarial=50-60`,
  `hidden_dim=128`, `latent_dim=32`, `batch_size=64`. Use the
  alternating schedule in `scripts/run_gan_loop_recursive.py` so
  every iteration lands in the 50-60 range.

**Step 2: Generate synthetic data with temperature-varied noise**
- Use `ml_sample_timeseries` with the trained/continued TimeGAN model
- `n_samples = 50_000` (or as needed)
- `temperature`: **varies per iteration** to fight mode collapse. The
  default schedule is
  `[1.0, 1.3, 0.7, 1.5, 0.8, 1.2, 1.0, 1.4]`. Below 1.0 concentrates
  near the generator's mean; above 1.0 explores the latent space.
- Save output as training data for classifiers

**Step 3: Train ALL THREE classifiers (mandatory)**
- For each model_type in `["lightgbm", "lstm", "tcn"]`:
  - Use `ml_train_timeseries` with `model_type={model_type}`
  - `X_uri` = TimeGAN-generated synthetic data
  - `y_uri` = corresponding labels
  - Config: `window_size=100`, `batch_size=32`, `epochs=50`
  - Record `job_id` for comparison

**Step 4: Evaluate all three models**
- Use `ml_compare_timeseries` with the three `job_id`s
- For each model, use `evals_evaluate_computational` with evaluators:
  - `can_auroc` (discrimination)
  - `can_auprc` (precision-recall)
  - `can_brier` (calibration)
  - `can_lead_time` (lead-time accuracy)
  - `can_false_alarm` (false alarm rate)
  - `can_episode_recall` (episode-level recall)
- Track per-architecture metrics across iterations

**Step 5: Record and feed back to TimeGAN**
- Call `evals_record_run` after EVERY iteration for EACH model
- Compute `avg_auroc = mean(auroc_lightgbm, auroc_lstm, auroc_tcn)`
- **This is the closed-loop hinge**: pass
  `classifier_feedback={"auroc": avg_auroc}` to `ml_continue_timeseries`
  in the next iteration. The dual-objective loss (adversarial weight
  taper + diversity penalty + label smoothing) reads this scalar and
  redirects the generator gradient accordingly.

**Step 6: Decide — stop or loop**
- **STOP** if: `iteration >= max_iterations` (default 10) OR
  `best_avg_auroc improved < 1%` for 3 consecutive iterations
- **LOOP** if: `iteration < max_iterations` AND score is improving

### Early Stopping Criteria
- `iteration >= max_iterations` (default: 10, configurable via `MAX_ITERATIONS` env var)
- `patience >= 3` (no improvement in 3 iterations)
- `best_avg_auroc >= 0.98` (quality achieved)

### State to Track
- Current iteration number
- Best AUROC score achieved (per model type AND averaged)
- Iteration where best score occurred (per model type)
- Patience counter (iterations since last improvement)
- History of all iteration scores (per model type)
- Architecture comparison: which model benefits most from synthetic data improvement
- TimeGAN training metrics (`g_loss`, `d_loss`, `g_gan_component`,
  `g_div_component`, `g_gan_weight`, `feedback_auroc`) per iteration
- **TimeGAN model lineage** (`parent_model_id` → `timegan_model_id`
  chain) — proves that iterations actually continued from each
  other rather than cold-starting with a new seed
- Per-iteration sampling `temperature` (so the noise-schedule is
  auditable post-hoc)

## Why previous loops (iter2-4, iter5-8) didn't show recursive improvement

Two bugs were missed by the previous scripts:

1. **Feedback loop never wired.** They called `train()` (cold-start)
   every iteration with a *different* `seed`. Each iteration's G/D
   weights were discarded. `continue_train()` was never invoked.
2. **Scalar BCE multiplier doesn't redirect generator.** The old
   loss was `BCE * feedback_weight` — a constant scalar that does
   not change the gradient direction, only its magnitude. The
   current dual-objective loss uses AUROC to (a) taper the
   adversarial weight, (b) engage a diversity penalty, and (c)
   smooth D's real labels — three gradient changes, not one.

The reference implementation is `scripts/run_gan_loop_recursive.py`.

## Demo Strategy (2-Day Timeline)

For the demo, run **8–10 iterations** to generate enough data points for charts:

| Iteration | Purpose |
|-----------|---------|
| 1 | Cold-start TimeGAN, establish baseline |
| 2-3 | Early feedback: adversarial weight still ~1.0, diversity penalty kicks in |
| 4-6 | Mid-loop: AUROC rising, adversarial weight tapering, label smoothing engaged |
| 7-8 | Convergence: temperature-varied noise explores/contracts the latent space |
| 9-10 | Stabilisation: AUROC plateaus near 0.85+ or early-stop fires |

**Charts to generate:**
1. AUROC by model across iterations (line chart) — should slope upward
2. Model comparison bar chart (final iteration)
3. TimeGAN loss curves (`g_loss`, `d_loss`) and per-component (`g_gan`, `g_div`, `g_gan_weight`)
4. Temperature schedule over iterations (show the noise-variation pattern)
5. `parent_model_id` lineage graph (prove the chain, not a forest of unrelated runs)
6. Evaluation metrics heatmap (6 metrics × 3 models × N iterations)

## Portability

All data and artifacts live on external drive. To run on a different laptop:

```bash
# Set data root to external drive
export DATA_ROOT="/Volumes/Crucial X9/can_data"

# Or if drive mounts elsewhere
export DATA_ROOT="/media/user/can_data"

# Run the recursive loop directly
python3 scripts/run_gan_loop_recursive.py
```

No local installation needed beyond Python + deps (use `uv run` from factory root).

## MCP Tools You Use
- `ml_train_timeseries` — train TimeGAN (cold start, iteration 1 ONLY)
- `ml_continue_timeseries` — continue training TimeGAN from previous
  checkpoint with `classifier_feedback` (iterations 2+) — **this is
  the call that makes the loop recursive**
- `ml_sample_timeseries` — generate synthetic data with a `temperature`
  argument to vary the latent noise per iteration
- `ml_compare_timeseries` — compare models side-by-side (step 4)
- `evals_evaluate_computational` — score with 6 evaluators (step 4)
- `evals_record_run` — persist iteration metrics to evals dashboard (step 5, 3x per iteration)
- `evals_get_run_regression` — compare current iteration vs previous
- `memory_store` — save iteration state

## Data Locations
- Real CAN data: `$DATA_ROOT/per_can_id/` (training-ready NPY arrays)
- Decoded CAN frames: `$DATA_ROOT/decoded_data/` (131 GB JSONL, source for TimeGAN)
- DBC files: `$DATA_ROOT/dbc_files/`
- Training output: `$DATA_ROOT/training_data/`
- GAN loop results: `$DATA_ROOT/gan_loop_results/`
- Recursive loop summary: `$DATA_ROOT/gan_loop_results/recursive_loop_summary.json`
