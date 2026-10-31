---
name: can-timegan
description: Train, monitor, and sample TimeGAN generative models for synthetic CAN bus signal windows.
---

# CAN TimeGAN

You are training, monitoring, and evaluating TimeGAN generative models
for CAN bus failure prediction. TimeGAN learns the joint distribution
of CAN signal windows without labels, so it is a useful complement to
supervised classifiers (LSTM/TCN/LightGBM): synthesize extra windows
to balance rare failure classes, or compare real vs. synthetic
distributions to detect distribution shift.

## MCP Tools

### Train a TimeGAN model

```
ml_train_timeseries(
  model_type="timegan",
  X_uri="<file://X_3d.npy>",
  y_uri="<file://y.npy>",  # unused for unsupervised generation
  experiment_name="can-timegan",
  config={
    "window_size": 100,
    "batch_size": 32,
    "epochs": 50,
    "extra": {
      "latent_dim": 32,
      "hidden_dim": 64,
      "n_layers": 2,
      "epochs_reconstruction": 50,
      "epochs_adversarial": 50
    }
  }
)
```

Returns `{job_id, model_type, status, metrics, model_path}`. The
adapter trains in two phases:
1. **Generator phase** (`epochs_reconstruction`): G is updated to
   produce synthetic windows that D misclassifies as real.
2. **Discriminator phase** (`epochs_adversarial`): D is updated on
   real-vs-fake windows. D gradients are blocked from reaching G
   via `torch.no_grad()` on the fake branch.

### Sample synthetic windows

```
ml_sample_timeseries(
  model_id="<job_id>",
  n_samples=1000,
  seed=42
)
```

Returns `{samples_uri: "file://...", n_samples, seed}`. The `.npy`
file has shape `(n_samples, window_size, n_features)` matching the
training windows. `seed` is required for reproducibility — TimeGAN
sampling is stochastic.

### Evaluate synthetic quality

Compare per-feature statistics between real and synthetic windows:

```python
import numpy as np
real_X = np.load(real_uri)        # (n_real, T, F)
synth_X = np.load(samples_uri)    # (n_synth, T, F)
for f in range(real_X.shape[-1]):
    print(
        f"feature_{f}: "
        f"real mean={real_X[..., f].mean():.4f}, std={real_X[..., f].std():.4f} | "
        f"synth mean={synth_X[..., f].mean():.4f}, std={synth_X[..., f].std():.4f}"
    )
```

A well-trained TimeGAN should hit:
- Per-feature means within ~10–20% of the real means
- Per-feature standard deviations within ~25% of the real std

## Monitoring Training

The TimeGAN adapter logs these metrics after training:

| Metric | Healthy range | Diagnosis |
| --- | --- | --- |
| `g_loss_final` | 0.5–1.5 | <0.3 = mode collapse; >2.0 = D dominates |
| `d_loss_final` | 0.5–1.5 | <0.3 = D lost; >2.0 = G lost |
| `synthetic_mean` | within 20% of `real_mean` | >50% gap = G collapsed |
| `synthetic_std` | within 25% of `real_std` | <50% of real = uniform output |

**Early stopping heuristics** — call the run *borderline* if any of
these fire:
- `d_loss_final < 0.3` — generator dominates; reduce `epochs_adversarial`
- `g_loss_final > 2.0` — discriminator dominates; increase `epochs_reconstruction`
- `|synthetic_mean - real_mean| / |real_mean| > 0.5` — generator collapsed
- `synthetic_std < 0.5 * real_std` — mode collapse (output too uniform)

**Recovery actions:**
- Mode collapse → halve `epochs_adversarial` or double `hidden_dim`
- D dominates → halve `learning_rate` or double `epochs_reconstruction`
- G dominates → double `epochs_adversarial` or halve `hidden_dim`

## Chained Workflow

1. **Train** — `ml_train_timeseries(model_type="timegan", X_uri, ...)`
2. **Sample** — `ml_sample_timeseries(model_id, n_samples, seed)`
3. **Validate** — Compare per-feature statistics between real and synthetic
4. **Use** — Inject synthetic windows into a training set, or
   compare real vs. synthetic divergence to detect distribution shift
5. **Record** — Store model id + quality metrics in memory with
   `user_id='can-timegan'` so the can-evaluator can review

## Recipe

`recipe://local/can-pipeline-timegan@1` chains `can_ingest →
can_profile → can_window → can_augment`. It omits `can_synthesize`
because TimeGAN learns from real data, not synthesized data —
synthesizing extra frames first would dilute the real distribution
the generator is trying to learn.

## Key Rules

- **TimeGAN is unsupervised** — `y_uri` is ignored. Pass a placeholder
  or any existing y_uri; the adapter never reads it.
- Always set `seed` for reproducibility. Default is 42.
- `window_size=100` for high-frequency CAN IDs (e.g., 0x320, 0x420);
  `window_size=32` for low-frequency IDs (e.g., 0x610, 0x611).
- `hidden_dim` should be 2–4× the `latent_dim`; `latent_dim >= 16` to
  capture enough signal structure.
- The adapter does not mutate OpenMP environment variables at import time.
  On Darwin arm64, install through the workspace's uv contract so LightGBM
  is built without introducing a Homebrew OpenMP runtime.
- Do **not** call `timegan.sample()` with `n_samples > 100_000` on a
  CPU-only worker; the synthetic generation is a single forward pass
  through the LSTM stack and scales linearly in `n_samples`.
