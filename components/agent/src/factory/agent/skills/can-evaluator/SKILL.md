---
name: can-evaluator
description: Evaluate CAN failure prediction models, compare architectures, recommend best model.
---
# CAN Evaluator

You are evaluating time-series models for CAN bus failure prediction.
The goal is to recommend the best model per the CAN evaluation rubric:
high `can_auroc` and `can_lead_time`, low `can_false_alarm` and
`can_brier`, plus high `can_episode_recall` for sustained faults.

## MCP Tools

### Bundled metrics (auto-wired into training)

`train_top_can_ids` (machine_learning brick) now best-effort calls
`evals_evaluate_can_model(y_true, y_pred, y_score=None)` after each
per-CAN-ID LightGBM fit and merges the result into `job.metrics`.
Always returns accuracy/precision/recall/f1; adds auroc/auprc/brier
when `y_score` is given and both classes are present in the holdout.
This is separate from — and does not replace — the six standalone
computational evaluators below, which you still call directly for
the full rubric (lead time, false alarm, episode recall).

```
evals_evaluate_can_model(
  y_true=[0, 0, 1, 1, 0, 1, ...],
  y_pred=[0, 0, 1, 1, 0, 1, ...],
  y_score=[0.05, 0.12, 0.91, 0.83, 0.21, 0.77, ...]
)
```

### Run a computational evaluator

```
evals_evaluate_computational(
  evaluator_name="can_auroc",
  y_true=[0, 0, 1, 1, 0, 1, ...],
  y_pred=[0, 0, 1, 1, 0, 1, ...],
  scores=[0.05, 0.12, 0.91, 0.83, 0.21, 0.77, ...]
)
```

Supported evaluators (all deterministic, no LLM call):
- `can_auroc` — area under ROC; headline discrimination metric
- `can_auprc` — area under precision-recall; better for imbalanced
  failure classes
- `can_brier` — Brier score; calibration of soft scores
- `can_lead_time` — mean seconds of advance warning before a
  failure event (higher is better)
- `can_false_alarm` — false-alarm rate per hour of normal driving
  (lower is better)
- `can_episode_recall` — fraction of fault episodes detected within
  their lifetime

Returns `{"evaluator": "<name>", "score": <float>}`.

### Compare models on a single metric

```
ml_compare_timeseries(
  model_ids=["can-tcn-2026-07-15-001", "can-lstm-2026-07-15-002",
             "can-patchtst-2026-07-15-003"],
  metric="can_auroc"
)
```

Returns `{metric, ranking: [{model_id, score}, ...], best: model_id}`.
Use this when you have a holdout set and want a single-metric leader
board.

### List trained models

```
ml_list_timeseries_models()
```

Returns `{"models": [{id, model_type, experiment_id, run_id, metrics,
created_at}, ...], "count": N}`. Filter by `experiment_name` in
client-side memory or via the run id.

## Evaluation Rubric

A model is **promotable** when ALL of the following hold on the
holdout set:
1. `can_auroc >= 0.90`
2. `can_lead_time >= 5.0` (seconds)
3. `can_false_alarm <= 0.10` (per hour)
4. `can_episode_recall >= 0.80`
5. `can_brier <= 0.15` (well-calibrated soft scores)

A model is **borderline** if 3-4 of the 5 thresholds are met.
Otherwise it is **rejected** — recommend a different architecture or
more training data.

When comparing architectures (`lightgbm` vs `lstm` vs `tcn` vs
`patchtst`), run the same holdout through each and use the rubric
above. `tcn` and `patchtst` typically lead on `can_auroc` and
`can_lead_time`; `lightgbm` is fastest to train and most
interpretable.

## Chained Workflow

1. **List** trained models → `ml_list_timeseries_models`
2. **Score** each model on the holdout set → `evals_evaluate_computational`
   (one call per evaluator per model)
3. **Aggregate** the six metric scores per model
4. **Compare** via `ml_compare_timeseries` for the headline metric
5. **Recommend** the model that passes the rubric; record the
   decision in memory

## Key Rules

- All six evaluators are deterministic; do not wrap them in an LLM
  call — that adds cost without changing the score.
- Always evaluate on a holdout set the train stage has NOT seen.
  Ingest-split-synthesize-train means: hold out 20% of the
  synthetic frames and all REAL frames the synthesizer didn't see.
- Lead time and false-alarm rate are deployment-critical; do not
  optimize only for `can_auroc`.
- When recommending a model, record the model id, the six metric
  scores, and the decision reason in
  `memory_store(user_id='can-evaluator', category='fact',
  metadata={"tags": ["can-eval"]})`.
