# Rando — Approach Review & Decision Options

Status check on the CAN failure-prediction system, grounded in (a) what's
actually implemented today (verified by reading code, not specs), and (b)
current field practice for CAN-bus PHM, synthetic time-series generation,
weak-supervision labeling, rare-event evaluation, and closed-loop retraining.

This is not a new spec. It's the "why did I decide this, and is it still the
right call" document, per decision point, so you can drop it into your write-up.

## Tracked gaps (Beads)

Every gap in this doc has a corresponding bead so status stays live and
travels with commits (the `.beads/` Dolt DB + JSONL backups are committed
like any other repo state — no separate spec-alteration step is needed
beyond this cross-reference).

| Bead | Priority | Section | Title |
|---|---|---|---|
| `python-factory-sbhyq` | P1 | — | EPIC: Rando — close construct-validity and closed-loop gaps |
| `python-factory-sbhyq.1` | P0 | §4 | Validate CAN failure labels against real fault data |
| `python-factory-sbhyq.4` | P1 | §5 | Wire evals CAN evaluator harness into `can_keystone` training loop |
| `python-factory-sbhyq.3` | P1 | §7 | Wire live inference feedback loop with confirmation gate |
| `python-factory-sbhyq.2` | P2 | §2, §6 | Deprioritize TimeGAN maturation; park or condition-on-failure-mode |
| `python-factory-sbhyq.11` | P0 | §4, §8 | Restore deterministic Dataset failure-injection contracts before portfolio work |
| `python-factory-bzm3s` | P2 | §16 | Broader physics-constrained correlated multi-signal failure realism (distinct from `.11`) |
| `python-factory-jln5n` | P3 | §16, §17 | ✅ Closed — conditional TimeGAN + dual-objective loss shipped upstream |
| `python-factory-sbhyq.5` | P2 | §17 | Scope SCANIA-derived injection construct-validity (truck features reshaped into CAN signal space) |

Check current status any time with `bd children python-factory-sbhyq` or
`bd show <id>`.

> **2026-07-23 addendum:** a follow-up Kiro session reviewed this doc plus
> current field literature and reached a sharper, more actionable version of
> §2/§4/§6's conclusions. See §16 before picking up `sbhyq.1`, `sbhyq.2`, or
> the failure-injection realism work.
>
> **2026-07-24 addendum:** upstream shipped a conditional TimeGAN and
> SCANIA-pattern-informed hybrid injection that directly act on §16's two
> beads — see §17 for a from-code review of what landed, plus one new
> construct-validity note it introduces (`sbhyq.5`). §18 adds some
> longer-horizon model/direction thoughts, offered for discussion, not as a
> decision.

## 0. TL;DR

The immediate gate is now Dataset correctness, not another model comparison:
`python-factory-sbhyq.11` must restore deterministic seeded injection before any
post-`.8.2` portfolio lifecycle work proceeds. For `ecu_timeout`, every decoded
signal is zero throughout each injected event window; for `signal_freeze`, only
the selected signals hold one stable prior value throughout the window. Event
rate/count/boundaries and provenance are deterministic, while non-target modes
remain unchanged. This is a regression fix, distinct from
`python-factory-bzm3s`, the broader physics-constrained correlated multi-signal
realism enhancement.

The full portfolio roadmap and hard dependency order are in §8 and mirrored in
[CAN Agentic Orchestration](./can-agentic-orchestration.md) and
[ML Dataset Generation](./ml-dataset-generation.md).

The pipeline is real engineering, not vaporware — SDV synthesis, LightGBM/LSTM/TCN
training with correct temporal-split methodology, 6 real computational
evaluators, a registered graph taxonomy, and genuinely promising LightGBM
numbers (AUROC 0.97–1.00 per CAN ID on Toyota + Kia/Hyundai data). But three
things need your attention before you trust the numbers or call this
"closed-loop":

1. **Every failure label is synthetic (self-injected).** The AUROC numbers
   measure "can the model detect the exact anomaly patterns I hand-coded,"
   not "can it predict real vehicle faults." This is the single biggest
   validity gap in the project right now.
2. **There is no closed loop.** The steering doc's stated goal — a
   TimeGAN-vs-evaluator adversarial cycle — doesn't exist in code. It's a
   linear pipeline: ingest → synthesize → train → (manual) evaluate. TimeGAN
   is implemented and unit-tested at toy scale but not wired into
   `can_keystone.py`, and none of the 6 evaluators are called by the training
   pipeline (LightGBM logs its own metrics instead).
3. **TimeGAN is probably the wrong upgrade path given your data volume.**
   67 files / 48MB is a low-data regime. Current field consensus (2024-2026)
   has moved past GANs toward diffusion models for time-series synthesis, but
   both families are data-hungry — likely overkill/underpowered here. SDV's
   GaussianCopula approach you're already using is closer to the right tool.

None of this means "start over." It means: label real gaps honestly in the
write-up, and treat current AUROC numbers as "detects injected synthetic
patterns" rather than "predicts vehicle failure."

---

## 1. Decode strategy: DBC-based signal decoding

**What you decided:** Match MF4 captures against opendbc candidates, decode to
physical signals, fall back to raw bytes for unmatched IDs.

**Field check:** This is standard and still correct. DBC-decoded, signal-level
modeling is the dominant approach in automotive PHM / prognostics literature.
Raw-frame/byte-level representation learning (skip the DBC entirely) is an
emerging trend, but only in CAN *intrusion detection*, where the DBC is
deliberately unavailable (that's an adversarial-security framing, not a
predictive-maintenance one). For your use case — predicting failures on
signals you can physically interpret (RPM, coolant temp, etc.) — DBC decoding
is the right call and gives you interpretability and lead-time reasoning that
byte-level models don't.

**Verdict: keep.** No change needed.

---

## 2. Synthetic data generation: SDV → TimeGAN progression

**What you decided:** Start with SDV (GaussianCopula/CTGAN), graduate to
TimeGAN if temporal fidelity is insufficient.

**What's actually running:** SDV per-CAN-ID synthesis is real and working
(`can_synthesize.py` / `can_synthesize_helpers.py`), with constraint clamping
and optional Gaussian smoothing. TimeGAN is real code — an LSTM
generator/discriminator trained adversarially — but it's a simplified GAN
(no embedder/recovery/supervisor networks from the original Yoon et al. 2019
paper), tested only on a tiny synthetic (32,16,2) fixture, and not called
anywhere in `can_keystone.py`.

**Field check:** This is the decision most worth reconsidering.

- Diffusion models (TabDDPM, Diffusion-TS, CSDI) have overtaken GANs as the
  state of the art for tabular/time-series synthesis in the recent literature.
- But *both* GANs and diffusion models are documented to need substantially
  more training data than you have. CTGAN itself is known to underperform in
  low-sample regimes — and TimeGAN, being recurrent + adversarial, is harder
  to train stably than CTGAN, not easier.
- 67 files / 48MB of real data is a genuinely small corpus for any deep
  generative model. Training instability (mode collapse, discriminator
  overpowering generator) is a well-known TimeGAN failure mode even with
  much larger corpora.

**Options:**

| Option | Fit for your data volume | Effort | Recommendation |
|---|---|---|---|
| Stay on SDV (GaussianCopula/CTGAN) | Good — designed for smaller tabular corpora | Already done | **Keep as primary path** |
| Push TimeGAN into production | Poor — likely data-starved, unstable | High (needs real training data + tuning) | Don't prioritize; keep as documented experiment only |
| Lightweight VAE (temporal) | Better fit than GAN for small data, more stable to train | Medium | Worth a spike if signal-correlation fidelity matters more than SDV gives you |
| Skip generative upgrade, invest in more real data | Best long-term signal, no synthetic construct-validity risk | Depends on data access | Actually consider this first — see §4 |

**Verdict:** Don't spend more effort maturing TimeGAN right now. The marginal
value of "better fidelity between synthetic signals" is dwarfed by the fact
that all your labels are synthetic anyway (§4). Fix the label problem before
investing in a better generator for the inputs.

---

## 3. Model architecture: LightGBM / LSTM / TCN / (PatchTST deferred)

**What you decided:** Train all three, compare via eval harness, LightGBM as
baseline.

**What's actually running:** All three train for real, with correct
methodology — temporal train/val split (no look-ahead), per-feature scaling
fit on train-only and reapplied at inference. Reported numbers: LightGBM
AUROC 0.97–1.00 per CAN ID; LSTM/TCN AUROC 0.73–0.77 (documented as
underperforming on small per-CAN-ID samples, which tracks — recurrent/conv
nets need more data per class than gradient-boosted trees on flattened
windows).

**Field check:** This progression (tree baseline → sequence models → 
transformer ceiling) matches current PHM/RUL literature (C-MAPSS-style
benchmarking is the closest methodological parallel). LightGBM winning at
your current data scale is expected and not a red flag — it's consistent with
published results showing gradient-boosted trees outperforming deep
sequence models until you have substantially more labeled examples per class.

**Verdict: keep the progression, but don't read the current LightGBM-vs-LSTM
gap as final.** It's more informative about data volume than about
architecture superiority. Revisit LSTM/TCN once you have a larger, more
real-label-anchored dataset.

---

## 4. Labeling: synthetic failure injection (no real failure timestamps)

**What you decided:** Inject 8 synthetic failure modes (signal drift,
drop-to-zero, out-of-sequence, sensor degradation, ECU timeout, signal
freeze, spike noise, correlation break) into real background data, since you
don't have annotated real failures.

**This is the part I'd push back on hardest, and it's worth being direct
about in your write-up.**

Synthetic failure injection ("the anomaly assumption") is a real, named
technique in weak-supervision / self-supervised anomaly detection literature
— it's not a made-up shortcut. But the field explicitly documents its
central risk: models trained this way tend to learn to detect the *injection
method*, not the underlying real-world failure signature. A recent survey
(142 studies) frames the injected-vs-real generalization gap as an open
research question, not a solved problem.

Your current AUROC 0.97–1.00 numbers are consistent with this risk: a model
detecting "did I insert a drop-to-zero mutation here" is a much easier task
than "will this vehicle actually fail," and near-perfect separability on some
CAN IDs (some showing AUROC 1.000, with F1 flagged as 0 or 1 in your own
results table) is a classic signature of a task that's too easy because the
injected pattern is too distinguishable from normal noise.

**What the field does about this (options, not just a warning):**

1. **Multi-signal correlated injection, not single-signal.** If a failure
   mode manifests as a coordinated shift across multiple correlated signals
   (which real faults usually do), injecting it that way makes the synthetic
   task closer to the real one. Your `correlation_break` mode does something
   in this direction already — worth leaning into as the "most realistic"
   injection mode and treating single-signal modes (drop-to-zero, freeze) as
   weaker positive controls, not primary training signal.
2. **Sanity-check against any real fault examples you can get**, even a
   handful. Public datasets like NASA C-MAPSS or PHM-conference challenge
   data don't map 1:1 to your vehicle, but if you can source even a few
   confirmed real-world DTC-linked episodes (even from a public dataset with
   labeled faults), validating that your model transfers to them at all is
   the single highest-value experiment you could run next.
3. **Treat synthetic-injection training as pretraining/weak supervision, not
   ground truth.** i.e., report metrics on synthetic data as "sanity check
   that the model can learn *a* pattern," and be explicit in your write-up
   that this isn't validated against real failures yet.
4. **Add an unsupervised/reconstruction-based anomaly detector as a
   complement**, not a replacement. Because it doesn't need injected labels
   at all, comparing its flagged anomalies against your supervised model's
   predictions is a way to cross-validate without needing real fault data.

**Verdict:** Not a wrong approach to have started with — it's a legitimate
weak-supervision technique — but the numbers you have now shouldn't be
presented as "the model predicts failures." They should be presented as "the
model detects the class of anomaly patterns we can currently define,"
with real-failure validation as the next gate before you'd trust this in
production framing.

---

## 5. Evaluation harness: AUROC / AUPRC / Brier / lead-time / false-alarm / episode-recall

**What you decided:** 6 computational evaluators, real math, registered in
`evals`.

**What's actually running:** All 6 are implemented correctly (Mann-Whitney U
for AUROC, threshold-sweep trapezoidal AUPRC, etc.) and have passing tests.
But — and this is a real gap, not a nuance — **nothing in `can_keystone.py`
actually calls them.** LightGBM logs its own sklearn-style metrics instead.
The eval harness you built is disconnected from the training loop it was
built for.

**Field check on the metric set itself:** it's well-chosen. AUROC+AUPRC dual
reporting matches current practice (there's active 2024 debate pushing back
on "PR-AUC is always better under imbalance" as folklore, so reporting both
rather than picking one is the right call). Two things commonly missing that
you don't have yet:

- **Calibration drift monitoring over time** — Brier score at training time
  tells you nothing about whether the model stays calibrated as conditions
  drift in deployment. This matters more than the static Brier score once you
  have live inference running.
- **Cost-sensitive/economic thresholding** — a fixed probability cutoff
  ignores that a missed failure and a false alarm have very different real
  costs. Worth defining an explicit cost matrix once you're past the
  synthetic-label validation stage.

**Verdict:** Wire the 6 evaluators into `can_keystone.py` — this is cheap
(they already exist and pass tests) and gives you a consistent comparison
across LightGBM/LSTM/TCN instead of relying on LightGBM's own internal
metrics. Add calibration-drift and cost-sensitive thresholding once live
inference exists.

---

## 6. The GAN setup goal specifically

Since you asked directly: **is a GAN (TimeGAN) justified here?**

Short answer: not yet, and possibly not at all for this data volume.

- TimeGAN is real, implemented, and passes unit tests — that part of the
  build is solid engineering.
- But it's not in the production path, and the field's current trajectory
  (diffusion models overtaking GANs for time-series synthesis) plus the
  well-documented low-data instability of adversarial training both argue
  against investing further here right now.
- Your actual bottleneck isn't "synthetic signal fidelity" — SDV is already
  producing usable synthetic signals. Your actual bottleneck is "synthetic
  labels aren't validated against real failures" (§4). A better generator
  doesn't fix that.

If you want a generative-modeling investment to pay off, the highest-leverage
place isn't a better GAN for signal synthesis — it's a small, well-validated
generative or statistical model for the *labels themselves* (i.e., a more
principled weak-supervision/label-model layer), or simply more real data.

**Verdict:** deprioritize TimeGAN maturation. Keep it as a documented,
tested experiment. Don't block anything on it.

---

## 7. Closed-loop / recursively-learning feedback

**What the spec says:** "Build a closed-loop adversarial system... graded by
evaluation metrics, until models achieve production-quality."

**What's actually wired:** Nothing. `CanInferenceBridge` (`can_inference.py`)
is a complete, working batch-inference class — but it has zero code
connections to `games`, `evals_persist_score`, or `memory_store`. Nothing
feeds live inference results, false alarms, or newly labeled episodes back
into retraining. The `can_failure` graph taxonomy is registered and has one
real consumer (the optional `can_taxonomize` stage), but that stage isn't
part of the default keystone pipeline either.

**Field check on what a real closed loop looks like:** current best practice
for PHM systems is drift-triggered retraining (monitor distributional drift
— PSI/KS/JS-divergence — against your training distribution, tools like
Evidently AI / whylogs), not calendar-based retraining and not a naive
"retrain on everything the model flags." A 2024 finding worth taking
seriously: feeding self-generated (model-flagged) labels back into training
*without* a human/rule-based confirmation gate causes silent performance
degradation over successive retrain cycles — the model can drift into
confirming its own biases.

**Options given what you already have in the control-plane runtime:**

| Component | Already exists | What it'd take to close the loop |
|---|---|---|
| `events` brick learning contracts / rewards | Yes, domain-agnostic | Tag CAN inference outcomes with `domain_class="can_failure"` and route through existing reward plumbing |
| `games` brick RL cascade | Yes, domain-agnostic substrate | Wire `can_inference` outputs as a new domain's game events |
| `memory` brick episode storage | Yes, spec already defines the convention (`tags=["can-episode"]`) | Actually call `memory_store` from `can_inference.py` — currently zero calls |
| `evals_persist_score` | Yes | Call it from `can_keystone.py` after each training run using the 6 computational evaluators (§5) |
| Confirmation gate before retrain | **Does not exist anywhere** | This is the one net-new thing to build — a simple rule ("only retrain on episodes where a human or a DTC log confirmed the label") before wiring anything else |

**Verdict:** You have the plumbing (events/games/memory are domain-agnostic
by design per the platform doctrine), you're just not calling it from the
CAN pipeline. Closing the loop is mostly wiring, not new infrastructure —
*except* the confirmation gate, which needs to be designed deliberately so
you don't build a system that quietly reinforces its own synthetic-label
biases (which, per §4, is a real risk given where labels come from today).

---

## 8. Recommended sequencing

The post-`.8.2` model portfolio is one gated roadmap under the existing
`python-factory-sbhyq` epic; do not create another umbrella epic.

| Order | Bead | Gate |
|---:|---|---|
| 1 | `python-factory-sbhyq.11` | Restore deterministic Dataset injection: seeded `ecu_timeout` zeros all decoded signals for the full event window; seeded `signal_freeze` holds selected signals at one stable prior value for the full window; event rate/count/boundaries are repeatable; provenance and non-target modes are preserved. |
| 2 | `python-factory-sbhyq.8.3` | Implement exact-pinned `ncps.torch.LTC`: candidate conformance replays exact prepared training timing; promoted inference requires a separate digest-bound live timing artifact normalized by the training-derived scale; non-LNN families reject supplied timing. |
| 3 | `python-factory-sbhyq.8.4` | Implement the native `ChronosPipeline` lifecycle with exact pinned backbone/revision and framework/PEFT serialization. |
| 4 | `python-factory-sbhyq.8.8` | Add MLX-native training, serialization, lifecycle, and cold loading after Chronos; no Torch routing or process-local dictionary authority. |
| 5 | `python-factory-sbhyq.8.5` | Run one portfolio-wide native train/cold-load/restart/parity/tamper/authority matrix across LightGBM, LSTM, TCN, PatchTST, LNN/LTC, Chronos, and supported MLX, including exact framework/backbone pins and adapter descriptor checks. `.8.6` is closed as superseded into this gate. |
| 6 | `python-factory-sbhyq.10.1` | Add generic durable, server-allowlisted named-MCP execution with persisted identity, outputs/evidence, retry/resume, and loud unknown-task failure. |
| 7 | `python-factory-sbhyq.10.2` | Define Dataset → causal materialization → ML training → eval → passport → cold conformance → promotion as workflow data. The workflow coordinates evidence; owning bricks retain policy. |
| 8 | `python-factory-sbhyq.8.7` | Delete legacy paths only after every supported family has `.8.5` parity and the `.10.2` durable workflow completes. |

**Exact dependency chain:** `.11 → .8.3 → .8.4 → .8.8 → .8.5 → .10.1 → .10.2 → .8.7`.

This order makes Dataset truth the first gate and legacy deletion the last. It
also keeps `.11` narrowly scoped to deterministic regression correctness;
`python-factory-bzm3s` remains the independent, broader enhancement for
physics-constrained correlated multi-signal realism. The same chain is mirrored
in [CAN Agentic Orchestration](./can-agentic-orchestration.md) and
[ML Dataset Generation](./ml-dataset-generation.md).

---

## 9. Earlier implementation requirements (retained context)

The requirements below preserve the earlier `.1`/`.3` validity and feedback
work. They are no longer the current execution sequence; the authoritative
post-`.8.2` dependency chain is §8.

### 9.1 `python-factory-sbhyq.1` — Validate CAN labels against real fault data (§4)

**Status: blocked on data access, not blocked on design.** This bead cannot
be closed by wiring existing code — it requires an external data source
decision the agent should confirm with the user before starting, then a real
experiment.

1. **Source or construct real labeled fault episodes.** Web research
   (2026-07-20) confirms real options exist — but note the split below
   between "validates the modeling approach" and "validates this exact
   vehicle's signals," since no public dataset does both for
   Toyota/Kia/Hyundai passenger cars.

   **Important scoping correction:** the pipeline's data sources are NOT
   uniformly manufacturer-specific. Per `.agents/steering/can-failure-prediction.md`,
   ~100K of the ~22.7M records ("S3 OBD-II", 2 VINs) are already
   pre-decoded **generic OBD-II PIDs** (EngineRPM, VehicleSpeed,
   EngineCoolantTemp, ThrottlePosition, MAF, FuelTrims, DTC codes) —
   these 17 signals are standardized by **SAE J1979 / ISO 15031-5**
   across every OBD-II-compliant vehicle (US 1996+, EU 2001+), Toyota
   and Kia/Hyundai included. The Toyota MF4 captures (92M records, Toyota
   Legacy DBC) and the Kia/Hyundai Car-Hacking/OTIDS data (20M+ records,
   `opendbc` Hyundai DBC) are NOT standardized — those are proprietary
   manufacturer CAN signal layouts and do not transfer across makes.
   If a team member says "we're using generic PIDs so this shouldn't be
   CAN-specific," that claim is accurate ONLY for the OBD-II slice of
   the pipeline, not the DBC-decoded majority. Scope any validation
   claim to the specific signal source it covers.

   Candidates, by what they actually validate:

   **(a) Validates the general modeling approach (any real failure
   label, not vehicle-specific) — available now, no manufacturer match
   needed:**
   - **SCANIA Component X** — real repair-record-labeled operational
     data from 33,000+ real heavy-duty trucks. Public, CC-BY 4.0, via
     Swedish National Data Service, DOI
     [10.5878/jvb5-d390](https://doi.org/10.5878/jvb5-d390). Labels
     come from actual workshop invoices (component replaced/repaired =
     failed), not injected patterns. See [Kharazian et al., Sci Data 12,
     493 (2025)](https://www.nature.com/articles/s41597-025-04802-6).
   - **APS Failure at Scania Trucks** — older, real, real-failure-labeled
     (Air Pressure System component failures), 60K+16K rows, CC-BY 4.0,
     one `pip install ucimlrepo` away via
     [UCI dataset 421](https://archive.ics.uci.edu/dataset/421/aps+failure+at+scania+trucks).
   - Caveat for both: anonymized histogram/counter features, not named
     signals — useful to test "does retraining this pipeline on real
     repair-linked labels still separate healthy/failed," not to test
     Toyota/Kia signal decoding specifically.

   **(b) Validates the generic-PID slice specifically (closer to
   directly comparable, still not make-specific):**
   - **EngineAD** ([Roth et al., McGill/Preteckt, 2026](https://arxiv.org/html/2603.25955v1)) —
     real multivariate sensor telemetry from a **fleet of 25 commercial
     vehicles over 6 months**, with **expert-annotated labels
     distinguishing normal operation from incipient engine faults** —
     explicitly NOT synthetic/injected. Hosted at
     [McGill iSMART Lab](https://ismart.ece.mcgill.ca/datasets/). This is
     the closest public match to "real OBD/engine-telemetry failure
     labels" found so far. Confirm exact signal list / access terms
     before committing — dataset page should be checked directly by
     whoever picks this up, as access mechanics weren't independently
     verified beyond the lab listing page.
   - `eron93br/carOBD` (GitHub) — OBD-II PID captures from a real Toyota
     Etios (27 PIDs) — real vehicle, real generic PIDs, but appears to be
     normal-operation logging with no confirmed failure/fault labels as
     described; verify before relying on it for label validation.

   **(c) Directly matches your make/model with real DTC-linked failures
   — not found in this pass:**
   - No public dataset was found with real Toyota/Kia/Hyundai
     manufacturer-specific CAN signals AND confirmed real failure/DTC
     labels. OEMs keep this proprietary; SCANIA's public release is
     explicitly called out in their own paper as an exception to
     standard industry practice. If this exact match is required, it
     has to come from data you or the team already has access to (real
     service records / DTC logs tied to specific vehicles) — there is
     no public substitute found.

   **Recommended sequencing:** start with (a) SCANIA — it's the fastest
   path to answering "does the synthetic-injection technique generalize
   to ANY real failure label," which is the single biggest open question
   in this review, and requires no new data acquisition. Follow with (b)
   EngineAD if the generic-PID slice needs its own validation. Only pursue
   (c) if the team has or can obtain real Toyota/Kia/Hyundai service
   records — do not substitute more synthetic data if this isn't available;
   state the gap explicitly instead.
2. **Validate current LightGBM/LSTM/TCN performance against those real
   episodes.** Run the existing trained models (or retrain via
   `can_run_full_pipeline` / `can_keystone.py`) against the real-labeled
   set and report AUROC/AUPRC/Brier via the now-wired evals harness
   (`evals_evaluate_can_model`, landed under `sbhyq.4`). This is the
   single experiment that determines whether §4's construct-validity
   concern is theoretical or actually biting. Compare directly against
   the existing synthetic-injection numbers (AUROC 0.97–1.00) — a large
   drop on real data confirms the gap; comparable performance would be
   genuinely good news worth reporting as such.

   **✅ DONE for the SCANIA slice (2026-07-21, verified by direct
   re-execution).** Trained + scored the same `TimeSeriesTrainingPort` /
   `evals_evaluate_can_model` path against the real UCI "APS Failure at
   Scania Trucks" dataset (60,000 train / 16,000 test rows, real
   workshop repair records as labels, 59:1 imbalance):

   | Metric | Real-data (SCANIA APS) | Synthetic claim |
   |--------|-------------------------|------------------|
   | AUROC | 0.9828 | 0.97–1.00 |
   | AUPRC | 0.9001 | not reported |
   | F1 | 0.8085 | 0.000–1.000 (per-CAN-ID) |
   | UCI cost @ 0.5 threshold | 26,040 | n/a |
   | 2016 leaderboard reference | 9,920 / 10,900 / 11,480 | n/a |

   **Verdict**: real-label AUROC lands inside the claimed synthetic
   range — the modeling approach generalizes to genuine failures, not
   just the injected artifact. Caveat: the cost metric (which weights
   missed failures 50x over false alarms) is ~2.4x worse than the 2016
   leaderboard at a naive 0.5 threshold, so AUROC alone overstates
   deployment readiness — threshold calibration is a separate gap.

   **This answers Question A only** (does the approach generalize to
   ANY real failure label) — it does NOT answer Question B (does it
   hold on Toyota/Kia's actual manufacturer-specific CAN signals), since
   SCANIA is heavy trucks with anonymized histogram features, not
   passenger-car CAN data. Question B remains open per option (c) above
   — no public substitute found; needs real Toyota/Kia/Hyundai service
   records from the team.

   Artifacts: `projects/the control-plane project/data/real_failure_validation/`
   (downloaded dataset, safety-verified — HTTPS from `archive.ics.uci.edu`,
   valid TLS cert, archive contents inspected before extraction, all
   files confirmed plain-text CSV via `file`, SHA256 checksums recorded).
   Script: `projects/the control-plane project/validate_real_failure_labels.py`.
   Enabling adapter change (additive, backward-compatible
   `scale_pos_weight`/`class_weight` support via
   `TimeSeriesTrainingConfig.extra`):
   `components/machine_learning/src/factory/machine_learning/runtime/adapters/sklearn_timeseries.py`.
   Leakage-purity verified independently (not just self-reported by the
   implementing agent): train-only median imputation, official UCI
   test split never touched before final scoring, exact row counts
   (60000/16000) and exact documented class balance (375 pos/15625 neg
   in test) reproduced, existing adapter tests green including a new
   regression test proving the default path is byte-identical when
   `extra` is empty.

   **Open provenance note**: the existing per-CAN-ID AUROC 0.97–1.00
   tables in `.agents/steering/can-failure-prediction.md` ("Training
   Results" section) could not be independently re-verified from this
   workspace — no raw training-run artifacts (result JSON, MLflow
   records) for CAN-specific runs exist in `projects/the control-plane project/runs/`
   or `experiments/`, and no MF4/Kia raw data files exist on this
   machine. Those numbers are real per-run results (there IS a
   per-CAN-ID breakdown table, not a single made-up figure), but the
   underlying logs live on whichever machine actually processed the
   Toyota MF4 / Kia CSV data — likely the "other computer" referenced
   in this epic's work split. Re-verification should happen there.
3. **Lean into multi-signal correlated injection going forward.** Once
   real-data validation results exist, treat `correlation_break` (in
   `failure_injection.py`) as the primary training-signal injection mode
   for any further synthetic augmentation, and reclassify single-signal
   modes (`drop_to_zero`, `signal_freeze`, etc.) as weaker positive
   controls rather than primary training signal. This is a config/usage
   change in how the existing 8 injection modes are weighted, not new
   injection code.
4. **Relabel all existing reporting.** Everywhere current AUROC/AUPRC
   numbers are surfaced (dashboards, `Rando.md`, any write-up), change the
   framing from "failure prediction accuracy" to "detection of injected
   synthetic patterns" until step 2's real-data validation is complete
   and reported alongside. This is a documentation-only change but should
   land in the same PR/commit as step 2's results, not deferred.

### 9.2 `python-factory-sbhyq.3` — Live inference feedback loop with confirmation gate (§7)

**Status: mostly wiring (steps 1–2), one net-new component (step 3).**
Steps 1–2 follow the exact `get_service("tool_invoker")` pattern already
used in `games/runtime/workflow_rl.py` and just landed for `sbhyq.4` — no
new infrastructure, only new call sites. Step 3 needs an explicit design
decision from the user before any code is written, because it determines
what data is allowed to re-enter training.

1. **Wire `can_inference.py` → `memory_store`.** `CanInferenceBridge` in
   `components/machine_learning/.../runtime/can_inference.py` currently has
   zero calls into `memory`, `games`, or `evals_persist_score` (confirmed by
   grep). Add a best-effort call to `memory_store` after each inference run,
   using the episode-tagging convention already specified in `Rando.md`
   §10.5 (`tags=["can-episode", ...]`) — mirror the try/except-log-swallow
   pattern from `games/runtime/workflow_rl.py` / the `sbhyq.4` fix. This
   alone gets most of the way to a feedback loop without touching
   `games`/RL.
2. **Wire inference outputs into the events brick's learning-contract /
   rewards plumbing.** Tag CAN inference outcomes with
   `domain_class="can_failure"` and route through the existing
   domain-agnostic reward plumbing (`learning_compute_reward` /
   `events` subscriptions), same `get_service("tool_invoker")` idiom.
3. **Design and build the confirmation gate — the one genuinely new
   component.** Do NOT wire this into `games`/RL retraining until this
   exists. Requires an explicit decision on what "confirmed" means for a
   real vehicle before implementation starts. Candidate definitions to
   choose from (or combine):
   - DTC (Diagnostic Trouble Code) log match — the inference-flagged
     episode is corroborated by an actual DTC entry in vehicle logs.
   - Human review — a person explicitly marks a flagged episode as a
     true positive before it's eligible for retraining.
   - A hybrid: DTC match auto-confirms, anything without a DTC match
     requires human sign-off.
   Without this gate, self-generated (model-flagged) labels feeding back
   into training risk silently degrading the model over successive
   retrain cycles (documented 2024 finding, cited in §7) — the model can
   drift into confirming its own biases. This decision should be made
   explicitly (and recorded, e.g. via meta-architect consult) before
   step 4.
4. **Add calibration-drift monitoring and cost-sensitive thresholding.**
   Once live inference + the confirmation gate exist: (a) monitor
   calibration drift over time (the static training-time Brier score
   doesn't tell you whether the model stays calibrated as conditions
   drift in deployment — consider PSI/KS/JS-divergence style monitoring,
   e.g. Evidently AI / whylogs patterns); (b) replace the fixed
   probability cutoff with a cost-sensitive/economic threshold that
   accounts for the fact that a missed failure and a false alarm have
   different real costs — this needs an explicit cost matrix, which is
   itself a decision for the user/domain owner, not something to default
   silently.

---

## Sources consulted (web research, 2024-2026)

Research was gathered by a sub-agent search across current literature on:
DBC-decoded vs. raw-frame CAN modeling in automotive PHM vs. intrusion
detection; TimeGAN/DoppelGANger/RCGAN vs. TabDDPM/Diffusion-TS/CSDI for
time-series synthesis and their data-volume requirements; the "anomaly
assumption" synthetic-injection literature and its documented
generalization-gap risk (142-study survey); the 2024 AUROC-vs-AUPRC
folklore-challenging paper (*Patterns*, Cell Press); and drift-triggered
retraining practice (Evidently AI / whylogs-style monitoring) plus the 2024
finding on self-generated-label feedback loops degrading silently without a
confirmation gate. Citations for each specific claim should be re-pulled
inline if this doc is published externally — this version prioritizes the
technical substance for your internal decision record.

---

## 16. 2026-07-23 follow-up: TimeGAN diagnosis and injection-realism next steps

**Context:** a later Kiro session was asked directly "how do I inject
realistic failures into raw driving data, and why isn't my TimeGAN loop
working?" This section is that session's findings, layered on top of
sections 2/4/6 above rather than replacing them. Tracked as
`python-factory-bzm3s` (injection realism) and `python-factory-jln5n`
(generator fate decision) under this epic.

### 16.1 Why the TimeGAN loop specifically isn't working — a structural diagnosis, not a tuning problem

Re-reading `timegan.py` end to end confirms something sections 2 and 6
above imply but don't say explicitly: **`TimeGANAdapter` is unsupervised.**
It trains `Generator`/`Discriminator` on unlabeled *normal* signal windows
only. `ml_sample_timeseries`'s own docstring says `y_uri` is ignored for
`timegan`. There is no failure-mode-conditioned generator anywhere in this
codebase.

This means the current TimeGAN, as built, **cannot generate realistic
failures no matter how it's tuned** — it was never given failure examples or
a failure-mode label to condition on. The instability documented in
`.github/spec/can-gan-loop-report.md` (AUROC swinging 0.43–0.86 across
seeds 42/100/200/300/400, with iterations 2–4 producing byte-identical
results at the same seed) is consistent with two compounding problems, not
one:

1. It's solving the wrong problem (normal-signal diversity, not failure
   realism) — this alone caps its usefulness for the stated goal regardless
   of stability.
2. It's also unstable/data-starved on ~48MB of real captures, exactly as
   §2's field-check predicted.

**Practical implication:** stop iterating on the current TimeGAN loop
expecting it to eventually produce better *failures*. It structurally
can't — the fix isn't more seeds or more epochs, it's a different
architecture (conditional generator) or a different approach entirely (see
16.3).

### 16.2 Current field literature (checked 2026-07-23) reinforces §2's diffusion-over-GAN call, specifically for *fault* synthesis in low-data regimes

Two 2025-2026 papers on synthetic fault-time-series generation, found via
web search, are directly on-point for this exact problem (few-shot fault
generation, not just "more synthetic normal data"):

- **FaultDiffusion** ([arXiv 2511.15174](https://arxiv.org/html/2511.15174))
  — a few-shot fault time-series generation framework using diffusion
  models with a "positive-negative difference adapter" that leverages a
  pretrained *normal*-data distribution to model the discrepancy into the
  *fault* domain, plus a diversity loss specifically to prevent mode
  collapse on rare fault classes. This is architecturally close to "take
  your existing normal-data TimeGAN pretraining and add a fault-domain
  adapter" — worth reading before building a conditional GAN from scratch.
- **Diff-MTS** ([arXiv 2407.11501](https://arxiv.org/pdf/2407.11501.pdf))
  — reports diffusion-based multivariate time-series generation
  "substantially better in diversity, fidelity, and utility" than GAN-based
  methods on C-MAPSS and FEMTO (both PHM/RUL benchmarks, the same
  problem family as Rando).
- Related supporting context: [emergentmind's summary of the few-shot fault
  generation literature](https://www.emergentmind.com/topics/few-shot-fault-time-series-generation-framework)
  explicitly names GAN/VAE variants as "empirically deficient" in the
  few-shot regime because they either memorize the few anomalies (mode
  collapse) or revert to unrealistic smoothed signals.

This doesn't overturn §2/§6's verdict — it sharpens it. §2 said "diffusion
is where the field is headed, generically." This is the fault-specific
confirmation: the field has a named answer for *your exact* few-shot
fault-generation problem, and that answer is diffusion-with-conditioning,
not a better-tuned GAN.

### 16.3 Two independent, decoupled next steps (don't block one on the other)

**Step A — Physics-constrained correlated injection (rule-based, cheap,
buildable now).** `python-factory-bzm3s`. This does NOT depend on §9.1's
data-access-blocked real-label validation and does NOT depend on any
generative-model decision. It's a direct extension of the existing
`failure_injection.py` + `can_profile.py` code:

- Use `can_profile`'s existing correlation matrix to inject coordinated
  shifts across clusters of correlated signals (e.g. coolant_temp +
  fan_rpm + engine_load moving together), not single-signal mutation.
- Constrain injected magnitude/rate-of-change to `can_profile`'s own
  measured physical bounds per signal, so injected trajectories can't
  exceed a physically plausible slew rate.
- Replace instant on/off failure-window labels with ramped onset/decay.
- Reweight defaults toward correlated modes per §4/§9.1 step 3 (already
  recommended above; this operationalizes it into a bead with concrete
  acceptance criteria).

This is the highest-leverage, lowest-risk next action for "make injected
failures look more real" — it's an afternoon-to-few-days job, not a new
model.

**Step B — Decide the generator's fate explicitly.** `python-factory-jln5n`.
Three options, and the recommendation is to pick one rather than keep
iterating ambiguously:

1. Park TimeGAN as documented/tested-but-unused code (cheapest, matches
   §6's original verdict). Do Step A and §9.1 (real-label validation)
   first; only revisit generative modeling if rule-based injection still
   demonstrably looks synthetic after Step A lands.
2. Build a failure-mode-conditioned generator — either a conditional GAN
   or, per 16.2, a few-shot diffusion adapter in the FaultDiffusion style
   — so the adversarial/generative loop actually targets failure realism
   instead of normal-signal diversity. This is net-new work, not a wiring
   fix to the existing TimeGAN.
3. Stop running further GAN-loop demo iterations (the steering doc's
   "Session Resume" plan to run iterations 9–10 for chart data) — the
   metric instability being charted is structural (16.1), not something
   more iterations will resolve into a clean trend line.

### 16.4 What this section does not change

- §4's core recommendation (validate against real fault labels) is still
  the top-priority gate — `sbhyq.1` Question B (Toyota/Kia-specific
  validation) is still open and still blocked on data access, unchanged
  by this section.
- §5/§7's wiring recommendations (evals harness, memory/events feedback
  loop, confirmation gate) are unaffected — this section is scoped
  specifically to the injection-realism and generator questions.

---

## 17. 2026-07-24 follow-up: upstream shipped conditional TimeGAN + SCANIA-pattern injection — status update and a new construct-validity note

**Context:** between the 2026-07-23 session (§16) and this one, the repo
picked up 7 commits from elsewhere (`931cddfe`, `0e7e3245`, `d0574406`,
`82df58cb`, `a80e7b68`, `bb0fcabe`, `6d314ecc`) that directly act on §16's
two open beads. This section is a from-code review of what actually landed
(not a restatement of commit messages), plus one new gap it introduces.
Tracked as `python-factory-sbhyq.5`.

### 17.1 `python-factory-jln5n` (TimeGAN fate) — effectively resolved, option 2 taken

§16.3 gave three options for TimeGAN's fate. Option 2 — build a
failure-mode-conditioned generator — is what shipped:

- `ConditionalTimeGANAdapter` (`timegan_conditional.py`) adds a one-hot
  `failure_mode` vector, broadcast per-timestep and concatenated into both
  the `ConditionalGenerator` and `ConditionalDiscriminator` LSTM inputs
  (`timegan_conditional_models.py`). This directly fixes §16.1's core
  diagnosis: the old `TimeGANAdapter` was unsupervised and structurally
  could not generate failures. The new adapter can, by construction.
- `timegan_loss.py`'s `DualObjectiveConfig` independently fixes the
  instability documented in `can-gan-loop-report.md` (AUROC swinging
  0.43–0.86 across seeds): it tapers the adversarial loss weight down as
  classifier AUROC rises (stops G/D fighting once the signal is good
  enough), adds an explicit diversity-loss term against mode collapse, and
  applies one-sided label smoothing on D once AUROC crosses 0.75. This is
  correct, well-reasoned GAN engineering — each piece maps to a named,
  documented GAN failure mode, not ad hoc tuning.
- `scripts/run_gan_loop_recursive.py`'s docstring self-diagnoses *why* the
  earlier iteration scripts (iter2-8 in the original report) never showed
  recursive improvement: they cold-started a new seed every iteration and
  never passed `classifier_feedback`, so the feedback loop was wired but
  inert. This is the same root cause independently reached in §16.1.

**Bead status:** `jln5n` closed. This is a legitimate resolution, not a
partial one — the generator now targets the right problem (failure
realism, not normal-signal diversity) and the training instability has a
principled fix rather than more seed-hunting.

### 17.2 Injection strategy — `rule` / `learned` / `hybrid`

`failure_injection.py` was refactored into a strategy-dispatch design:
`"rule"` (the original 8 modes, now in `_rule_failure_helpers.py`),
`"learned"` (samples from a `LearnedSampler`, i.e. a trained
`ConditionalTimeGANAdapter`), and `"hybrid"` (30% rule / 70% learned per
event). `can_synthesize.py` wires a `scania_data_uri`/`scania_model_id`
config path that trains or loads a SCANIA-pattern-conditioned generator
and auto-promotes `"rule"` to `"hybrid"` when a SCANIA source is supplied.

Reported result (`can-gan-loop-report.md` §3 "Realistic Failure
Experiments"): AUROC 0.70–0.80 with SCANIA-pattern injection vs 0.50–0.60
for simple injection. This is a real, interesting empirical finding —
worth noting explicitly, since it cuts against §4's framing in one sense:
0.70–0.80 is *lower* than the original hand-injection AUROC of 0.97–1.00,
which is itself informative — it suggests the original numbers actually
were inflated by too-easy injected patterns (§4's hypothesis), and a
harder, more realistic anomaly distribution knocks AUROC down toward a
more believable range.

### 17.3 New gap: what "SCANIA-derived" actually means once you trace the code

This is the one thing worth flagging before this gets reported as "we
fixed the realism problem." `ScaniaPatternExtractor`
(`scania_pattern_extractor.py`) works from SCANIA APS's 170 anonymized
tabular histogram/counter features (see §9.1's original caveat: this is
snapshot data, not a real time series). To make it usable by a
sequence-model generator, the extractor:

1. Builds an **invented** 50-frame linear-interpolation trajectory from
   the healthy-baseline mean to each failure row's values (`build_trajectory`
   in `_scania_helpers.py`) — the temporal shape here is a modeling choice,
   not an observed dynamic.
2. Z-score normalizes across all 170 features jointly.

Then, at blend time, `_can_synthesize_hybrid_utils.py`'s `match_signals()`
and `resample_time()` mechanically reshape this 170-feature, 50-frame
tensor to whatever shape the target CAN ID's actual signal set needs:
excess target signals beyond SCANIA's 170 are **padded with Gaussian noise
matched to the window's own std** (not padded with SCANIA content), and
time-axis mismatches are linearly resampled.

**What this means concretely:** the injected "realistic SCANIA failure" for
a CAN ID with, say, 6 decoded signals is: pick 6 of SCANIA's 170 anonymized
truck-sensor features (by column order, no semantic matching — there's no
mapping from "coolant_temp" to a specific SCANIA histogram feature),
apply the invented drift trajectory, resample to the target frame count.
For CAN IDs with more than 170 signals in aggregate across a session, the
overflow is literally noise, not truck data. This is a real, meaningfully
different distribution from hand-coded `drop_to_zero` (there's now a real
failure-adjacent statistical structure underneath it), but it is **not**
"real Toyota/Kia CAN failure signatures," and the AUROC 0.70–0.80 numbers
should not be read as validating construct-validity against real CAN
failures. They're better interpreted as "detects a harder synthetic
anomaly distribution than naive injection" — a real improvement, but a
different claim than §4/§9.1's real-label validation gate, which remains
unresolved.

**Ask (tracked as `python-factory-sbhyq.5`):** relabel the 0.70–0.80
numbers in reporting to reflect this scope precisely, and make an explicit
decision on whether noise-padding uncovered CAN signals is the intended
long-term design or a placeholder needing a real fix (e.g. restricting
SCANIA-pattern injection to CAN IDs with a documented physical analog to a
SCANIA feature, rather than blending into arbitrary signal counts).

### 17.4 What this doesn't change

- `sbhyq.1` (real Toyota/Kia-specific label validation, Question B) is
  still open, still blocked on data access, and this section's finding
  makes it *more* important, not less — SCANIA-pattern injection is a
  better synthetic proxy, but it's still a proxy.
- `python-factory-bzm3s` (rule-based correlated multi-signal injection) is
  untouched by any of this and remains open — it's a complementary,
  decoupled improvement to the `"rule"` strategy specifically, orthogonal
  to the `"learned"`/`"hybrid"` work described here.

---

## 18. Bigger-picture thoughts on model/direction (not a decision — for discussion)

Stepping back from the specific gaps: a few observations on where this
project's modeling strategy could head, offered as thinking-out-loud
rather than a recommendation to act on immediately.

**On "best possible model."** There probably isn't a single best model
here — the right framing is a portfolio, and the repo is already
structured that way (LightGBM baseline, LSTM/TCN sequence models,
generative augmentation). If forced to bet on where the ceiling is:
LightGBM on well-engineered windowed features will likely keep winning on
*this* data volume regardless of what generative model produces the
training data, simply because tree ensembles are the least data-hungry
architecture in the comparison set (§3's field-check already covers this).
The generative-model choice (SDV vs conditional-TimeGAN vs future
diffusion) mostly affects how good LightGBM's *training data* is, not
whether LightGBM itself should be replaced. That reframes "what's the best
model" into "what's the best data" — which is exactly the direction §17.2's
SCANIA experiment and the "Critical Honest Assessment" data-utilization
finding (131GB sitting unused) are both already pointing at, from two
different angles (label realism vs. data volume).

**On direction, three candidate next bets, not mutually exclusive:**

1. **Scale data utilization before scaling model sophistication.** The
   131GB-unused finding is arguably a bigger lever than any generator
   upgrade — 100M+ real (if unlabeled) records is a lot of normal-driving
   signal that could sharpen the SDV/conditional-TimeGAN's sense of what
   "normal" looks like per CAN ID, independent of the failure-labeling
   question entirely. Cheap, no new architecture needed.
2. **Keep pushing on real-label acquisition, harder than SCANIA.** SCANIA
   answered "does this approach generalize to any real failure label" —
   worth treating that as done, and putting more effort into finding
   *any* real DTC-linked or service-record-linked passenger-vehicle data,
   even a handful of episodes, since that's the one gap no amount of
   better synthesis can substitute for.
3. **If pursuing more generative sophistication, diffusion is still the
   next rung, not a bigger GAN** — §16.2's papers (FaultDiffusion, Diff-MTS)
   remain the relevant reference point. The conditional TimeGAN shipped
   this round is a legitimate step (conditioning was the missing piece),
   but if it plateaus, the field's answer for few-shot fault synthesis is
   diffusion-with-conditioning, not a third GAN variant.

None of this is a call to stop current work — just flagging where the
highest-leverage next investments plausibly are, for whoever picks this up
next to weigh against their own priorities and time constraints.
