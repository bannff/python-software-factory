---
name: can-recipe-author
description: Compose CAN-specific dataset recipes for synthetic data generation and model training.
---
# CAN Recipe Author

You are composing dataset generation recipes for CAN bus telemetry. A
CAN recipe chains five data stages: **ingest → profile → synthesize →
window → augment**. Each stage consumes a typed artifact from the
previous stage and emits a new typed artifact with a content-addressed
digest. The ML training step (`ml_train_timeseries`) is a separate
post-pipeline invocation, not a dataset stage.

## Recipe Structure

A CAN recipe is a YAML document with `stages:` (an ordered list) and
`outputs:` (the canonical artifact bundle). Each stage declares:

- `name` — stage id (`can-ingest`, `can-profile`, `can-synthesize`,
  `can-window`, `can-augment`)
- `adapter` — dotted path to the runtime adapter
  (`factory.dataset.runtime.adapters.can_ingest` etc.)
- `inputs` — list of `{uri, digest}` references
- `params` — stage-specific overrides (e.g., `failure_modes`,
  `synthesis_count`, `model_type`)

The five canonical stages:
1. `can-ingest` — MF4 → raw frame log + observed CAN IDs
2. `can-profile` — raw log + DBC → constraint schema (boundaries, periods)
3. `can-synthesize` — constraint schema → synthetic CAN frames with
   injected failure modes (dropout, drift, stuck-value, spike)
4. `can-window` — synthetic frames → rolling time-series windows
   (Polars-based; see `factory.dataset.runtime.adapters.can_window`)
5. `can-augment` — windowed frames → augmented training set
   (jitter, scale, time-warp; see
   `factory.dataset.runtime.adapters.can_augment`)

The full 5-stage pipeline is registered as
`recipe://local/can-pipeline-aug@1` and resolved by
`factory.dataset.runtime.recipe._CAN_RECIPE_URIS`. A 4-stage
`can-pipeline@1` (omitting augment) is also available for
ablation runs.

## MCP Tools

### Submit a CAN generation job

```
dataset_submit_generation(request={
  "recipe_uri": "recipe://local/can-pipeline-aug@1",
  "recipe_digest": "<sha256>",
  "input_artifacts": [
    {"uri": "file://<path>.mf4", "digest": "<sha256>"},
    {"uri": "file://<path>.dbc", "digest": "<sha256>"}
  ],
  "context_snapshot": {"uri": "snapshot://local/can-default@1",
                       "digest": "<sha256>"},
  "tool_schema_snapshot": {"uri": "schema://local/empty@1",
                           "digest": "<sha256>", "allowed_tools": []},
  "requested_views": ["default", "sft"],
  "idempotency_key": "can-pipeline-aug-<trace_id>"
})
```

Use `recipe://local/can-pipeline-aug@1` for the full 5-stage pipeline
(ingest → profile → synthesize → window → augment). Use
`recipe://local/can-pipeline@1` for the 4-stage variant that omits
augment (ablation runs).

Use `requested_views: ["default", "sft"]` so the train stage has a
supervised-fine-tuning view ready for `ml_train_timeseries`.

### Train a time-series model

After `dataset_get_artifact` returns, pull the `X_uri` and `y_uri` from
the resolved manifest, then submit training:

```
ml_train_timeseries(
  model_type="tcn",  # or lightgbm | lstm | patchtst
  X_uri="<manifest.X_uri>",
  y_uri="<manifest.y_uri>",
  experiment_name="can-failure-prediction",
  config={"epochs": 30, "batch_size": 64, "window_size": 64}
)
```

Returns `{job_id, model_type, status, experiment_id, run_id, metrics,
model_path}`.

### Run computational evaluators on predictions

```
evals_evaluate_computational(
  evaluator_name="can_auroc",  # can_auprc, can_brier, can_lead_time,
                               # can_false_alarm, can_episode_recall
  y_true=<ground_truth>, y_pred=<hard_preds>, scores=<soft_scores>
)
```

`can_auroc` is the headline metric; `can_lead_time` measures how early
the model detects failures before they manifest; `can_false_alarm`
penalizes spurious alerts.

## Chained Workflow

1. **Author** the recipe YAML (5 data stages, 2 input artifacts: MF4 + DBC)
2. **Submit** to `dataset_submit_generation` with `requested_views`
3. **Poll** `dataset_get_job` until `completed`
4. **Resolve** the manifest and extract `X_uri`, `y_uri`
5. **Train** via `ml_train_timeseries` with the resolved URIs
6. **Score** via `evals_evaluate_computational(can_auroc)`

## Key Rules

- The recipe URI is content-addressed: the same recipe content always
  hashes to the same `recipe_uri`. Never mutate a recipe without
  bumping its `@<n>` version suffix.
- `failure_modes` in the synthesize stage must be a subset of
  `{dropout, drift, stuck_value, spike}` — other modes are not yet
  supported by the failure_injection adapter.
- `model_type` is enum-locked; unknown values return
  `{"error": "Unknown model_type: ..."}`. Pick one of
  `lightgbm | lstm | tcn | patchtst`.
- Recipes must not embed raw LLM config blobs — route LLM calls
  through `llm_gateway`.
