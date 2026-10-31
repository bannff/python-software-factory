# Rando — What It Is, What It Could Be

## What Rando Is

Rando is a system to predict vehicle failures by training models on CAN bus
telemetry. It's not a text/LLM pipeline — CAN data is high-frequency binary
time-series, so Rando runs a parallel "signal pipeline" inside the same
the control-plane runtime substrate: ingest raw MF4/CSV captures, decode them into
physical signals via DBC files, synthesize a larger training corpus,
inject labeled failure modes, train classifiers, and evaluate them.

Today it's a linear pipeline, not a closed loop: ingest → profile →
synthesize → window → augment → train. Real data (22.7M raw CAN frames
across Toyota MF4 captures, Kia/Hyundai public datasets, and S3 OBD-II
data) feeds through this, and the best model (LightGBM) hits AUROC
0.97-1.00 detecting the failure patterns we inject ourselves — which is
the most important caveat on everything below: **no real fault data has
validated this yet.** Every failure label in the system is synthetic.

The five decisions below are the ones that shape what Rando is right now.
Each one had real alternatives; here's what we picked and why.

---

## Decision 1: How to decode CAN frames into meaning

Rando decodes raw CAN frames into physical signals (RPM, temp, etc.) using
DBC files, rather than working on raw bytes or querying ECUs directly.

**Options considered:**

- **Raw bytes** — feed the model CAN ID + payload bytes directly, no
  decoding at all.
  - *Pro:* no DBC dependency, zero information loss from decoding.
  - *Con:* no semantic meaning — the model has to learn from scratch that
    byte 3 of ID 0x25 means "coolant temp." Loses the interpretability and
    lead-time reasoning that comes from knowing what a signal *is*.
- **DBC decode** — match captures against known DBC files (Toyota,
  Hyundai/Kia via opendbc), decode to physical signal values.
  - *Pro:* semantic meaning, standard approach in automotive PHM
    literature, gives us interpretable features and physically-plausible
    boundaries per signal.
  - *Con:* requires a DBC match; some signals won't decode cleanly and
    fall back to raw bytes.
- **UDS (diagnostic queries)** — pull values on-demand from ECUs the way a
  scan tool does.
  - *Pro:* exact, manufacturer-standard diagnostic values.
  - *Con:* this is a request/response protocol for point-in-time
    diagnostics, not continuous telemetry — wrong shape for streaming
    prediction, and it requires active bus communication we don't want.

**What we picked and why:** DBC decode. It's the field-standard approach
for signal-level PHM (as opposed to CAN intrusion detection, which
sometimes works raw-byte because DBCs are deliberately withheld — that's a
different problem than ours). We fall back to raw bytes only for IDs we
can't match, so we don't lose data entirely when a DBC doesn't cover
something.

---

## Decision 2: How to make more training data than we actually have

We only have ~67 real capture files (~48MB). Rando multiplies that into a
larger corpus using SDV (GaussianCopula/CTGAN) today, with TimeGAN built
as a documented next step.

**Options considered:**

- **SDV (GaussianCopula, CTGAN)** — statistical/light-GAN tabular
  synthesis, fits a per-CAN-ID distribution and samples from it.
  - *Pro:* simple, stable to train even on modest data, good documentation
    and ecosystem support.
  - *Con:* weaker at modeling sequential/temporal dynamics than a model
    built specifically for time-series.
- **TimeGAN** — a GAN with an LSTM generator and discriminator trained
  adversarially on sequences.
  - *Pro:* can, in principle, capture temporal dynamics and cross-signal
    correlation structure that SDV smooths over.
  - *Con:* GANs are well-documented as unstable to train (mode collapse,
    discriminator overpowering generator), and that instability gets
    worse, not better, with less data. Our data volume is small for this.
- **Diffusion models (TabDDPM, Diffusion-TS, CSDI)** — iteratively denoise
  random noise into realistic data.
  - *Pro:* current published literature shows these beating GANs on
    long-sequence fidelity and training stability; this is where the field
    has moved.
  - *Con:* also documented as data-hungry, and slower at inference (many
    denoising steps). Not implemented in Rando at all — this is a future
    option, not something we've built.

**What we picked and why:** SDV first, TimeGAN as the stated next step.
SDV is real and running today. TimeGAN is real code too — genuinely
adversarial, unit-tested — but it's not wired into the production pipeline
and, given our data volume, is probably the wrong next investment (see the
open question below). Diffusion isn't in the codebase at all; noting it
here because it's where the field is headed, not because we've built it.

**Open question worth deciding explicitly:** is TimeGAN still worth
maturing at our data scale, or should that effort go toward validating
labels against real faults first (Decision 4)? Current lean: the label
problem is the bigger lever — a better generator for signal realism
doesn't fix a model that's only ever seen synthetic failures.

---

## Decision 3: Which model architectures to train and compare

Rando trains multiple classifier architectures and compares them, rather
than betting on one up front.

**Options considered:**

- **LightGBM + tsfresh features** — gradient-boosted trees on extracted
  time-series features.
  - *Pro:* fast to train (seconds), interpretable feature importance,
    works well on modest per-class sample sizes.
  - *Con:* less capacity for complex sequential dependencies than a model
    built for sequences.
- **LSTM / Bi-LSTM** — recurrent network on windowed sequences.
  - *Pro:* built for exactly this kind of sequential dependency.
  - *Con:* needs more data per class than tree models to actually realize
    that advantage.
- **TCN (Temporal Convolutional Network)** — 1D convolutions across
  windows.
  - *Pro:* ultra-low latency, parallelizable, a good fit if inference
    speed matters more than squeezing out extra accuracy.
  - *Con:* same data-hunger issue as LSTM at our current scale.
- **PatchTST / Transformer** — patched time-series transformer.
  - *Pro:* highest ceiling for complex, long-range patterns.
  - *Con:* highest data/compute requirement of the four. Deferred, not
    implemented yet.

**What we picked and why:** train all three implemented architectures
(LightGBM, LSTM, TCN) and let the eval harness pick a winner per CAN ID
rather than assuming one architecture wins everywhere. Right now
LightGBM wins clearly (AUROC 0.97-1.00 vs. 0.73-0.77 for LSTM/TCN), which
tracks with the literature — gradient-boosted trees are expected to beat
deep sequence models until there's meaningfully more labeled data per
class. This isn't a verdict on architecture, it's a symptom of data volume,
and worth re-testing once the corpus (real or synthetic) grows.

---

## Decision 4: How to get failure labels without real fault data

We don't have annotated real-world failures, so Rando injects synthetic
failure modes into real background data.

**Options considered:**

- **Wait for / source real fault data** before training anything.
  - *Pro:* the only way to get labels with zero construct-validity risk.
  - *Con:* real, timestamped, DTC-linked fault data for a specific vehicle
    is genuinely hard to get — this could stall the whole project
    indefinitely if treated as a hard blocker.
- **Synthetic failure injection** (what we do today) — hand-coded
  deterministic mutations (signal drift, drop-to-zero, sensor
  degradation, ECU timeout, signal freeze, spike noise, correlation
  break, out-of-sequence) applied to real background windows, labeled
  `is_failure=1`.
  - *Pro:* lets us start training and building the pipeline immediately,
    without waiting on data we may never get. This is a real, named
    technique in weak-supervision literature ("the anomaly assumption"),
    not a made-up shortcut.
  - *Con:* the field explicitly documents the risk we're now seeing
    reflected in our own numbers — a model can learn to detect *the
    injection method* rather than *the real failure signature*, and some
    of our current AUROC 1.000 results (with F1 flagged 0/1) look exactly
    like that failure mode: a task that's easy because the injected
    pattern is too distinguishable from normal noise, not because the
    model has learned something transferable.
- **Model-driven failure generation** (e.g. a conditional GAN, generator
  conditioned on a failure-mode label) instead of hand-coded rules.
  - *Pro:* this is the "GAN vision" version of failure generation —
    generator and discriminator co-improving on realistic-looking
    *failures*, not just realistic-looking normal signals. Directly
    answers "why is this hand-coded and not learned."
  - *Con:* nothing like this exists in the codebase today. Our TimeGAN
    only trains on unlabeled normal signal windows — there's no
    label-conditioned generator anywhere, so this would be new work, not
    a wiring fix.

**What we picked and why:** synthetic injection, because it unblocked
everything else. But this is the decision I'd push back on hardest if
someone asked "does this actually predict failures" — right now, honestly,
it predicts *our own injected patterns*. The fix isn't to abandon synthetic
injection (it's still a legitimate way to bootstrap), it's to (a) validate
against any real fault data we can get our hands on, even a small amount,
and (b) lean harder into multi-signal correlated injection over
single-signal modes, since real faults usually manifest as a coordinated
shift across multiple signals, not one signal going to zero in isolation.

---

## Decision 5: How to evaluate model quality

Rando built a 6-metric computational eval harness (AUROC, AUPRC, Brier
score, lead-time accuracy, false alarm rate, episode-level recall) inside
the `evals` brick, purpose-built for rare-event failure prediction rather
than reusing the brick's existing LLM-as-judge evaluators.

**Options considered:**

- **Ad-hoc scripts** — one-off Python for whatever metric is needed that
  day.
  - *Pro:* fast to write.
  - *Con:* no persistence, no comparability across runs, no reproducibility.
- **MLflow only** — log metrics manually to the tracking server.
  - *Pro:* gives persistence and a UI.
  - *Con:* no built-in evaluators — still have to write the metric math
    yourself, MLflow just stores the result.
- **`evals` brick with custom computational evaluators** (what we built) —
  register CAN-specific pure-math evaluators alongside the brick's
  existing LLM-as-judge ones.
  - *Pro:* one harness, comparable across models and runs, reuses existing
    experiment persistence.
  - *Con:* needed real engineering — the brick's existing evaluators are
    text-in/text-out LLM judges, not array-in/score-out math, so this
    required a genuinely new evaluator *type*, not just new evaluator
    *instances*.

**What we picked and why:** build it inside `evals`, correctly, as a new
computational evaluator type. This part of the build is solid — the 6
metrics are implemented with correct math and pass their own tests. The
gap isn't the harness itself, it's that **the training loop doesn't call
it yet.** `can_keystone.py` still computes its own inline metrics instead
of routing through the harness we built for exactly this purpose. That's
wiring debt, not a design mistake — the fix is cheap (the games brick
already has the exact cross-brick calling pattern to copy).

---

## Where this leaves us

Real, working, and worth being proud of: DBC-based signal decoding, SDV
synthesis, three trained model architectures with a legitimate baseline
progression, a correctly-designed computational eval harness, and a real
adversarially-trained TimeGAN (even if unused).

The honest gap, stated plainly for anyone reading this: **the numbers we
have today measure "can the model detect the patterns we hand-coded,"
not "can it predict a real vehicle failure."** That's not a reason to
distrust the engineering — it's the next thing to go solve, and it's more
important than any model-architecture or generator upgrade until it's
addressed.

## Tracked next steps

See `python-factory-sbhyq` (epic) and its children for the concrete,
prioritized fixes derived from this document:

- `python-factory-sbhyq.1` (P0) — validate labels against real fault data
- `python-factory-sbhyq.4` (P1) — wire the eval harness into training
- `python-factory-sbhyq.3` (P1) — wire live inference into a feedback loop,
  with a confirmation gate
- `python-factory-sbhyq.2` (P2) — decide TimeGAN's fate: park it, or build
  it properly as a label-conditioned generator

Full technical detail behind each decision: `.github/spec/can-failure-prediction-review.md`.
