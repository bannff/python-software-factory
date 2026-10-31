---
name: can-feedback-loop
description: Closed-loop improvement for CAN failure prediction via evaluation feedback.
---
# CAN Feedback Loop

You close the loop on the CAN failure-prediction pipeline. After every training iteration you decide whether to **retrain backward** (fix data — labels, splits, feature engineering) or **progress forward** (tune architecture, add a model family, harden for edge cases). Every decision is persisted in memory and published as an event so downstream agents (TimeGAN loop, dashboard, auto-improvement subscription) can react.

## Purpose

The other CAN agents produce models and metrics; you turn those metrics into a *direction*. Without you the pipeline is one-shot. With you it is a closed loop that converges on the production rubric:

1. Read the latest run regression and the six metric scores
2. Compare against thresholds: AUROC ≥0.80, AUPRC ≥0.75, Brier ≤0.15, lead-time ≥5s, false-alarm ≤0.10, episode-recall ≥0.80
3. Classify the iteration as `backward` or `forward` with a reason
4. Persist the decision in memory (tag `can-feedback`)
5. Publish `can.retrain.decision` and, when the model improves, `can.model.promoted` via `events_publish`
6. Update the model ranking via `ml_compare_timeseries`

## Workflow

### Step 1: Pull the latest run regression

```
evals_get_run_regression(run_id="<latest_run_id>")
```

Returns `{regressed, regression_state, pass_rate_delta, avg_score_delta, previous_run_id}`. If `regressed` is true, treat the regression itself as the primary signal.

### Step 2: Read the six metric scores

One `evals_evaluate_computational` call per evaluator (deterministic, no LLM): `can_auroc`, `can_auprc`, `can_brier`, `can_lead_time`, `can_false_alarm`, `can_episode_recall`. Aggregate into `metrics`.

### Step 3: Decide direction

Apply the rubric tree in **Decision Logic**:

```
decision = {
  "direction": "backward" | "forward",
  "reason": "<one-sentence explanation>",
  "metrics": {<six scores>},
  "target_improvement": "<what needs to improve next>",
  "decided_at": "<iso-8601 UTC>"
}
```

### Step 4: Persist in memory (memory is source of truth)

```
memory_store(
  user_id='can-feedback-loop',
  content=f"DECISION: run_id={run_id}\nDIRECTION: {decision['direction']}\n"
          f"REASON: {decision['reason']}\nMETRICS: {decision['metrics']}",
  category='fact',
  metadata={"tags": ["can-feedback"], "run_id": run_id,
            "model_id": model_id, "direction": decision['direction']}
)
```

Tag `can-feedback` so the TimeGAN loop and dashboard can retrieve the full decision history via `memory_retrieve`.

### Step 5: Publish `can.retrain.decision`

```
events_publish(
  event_type="can.retrain.decision",
  payload={"direction": decision["direction"], "reason": decision["reason"],
           "metrics": decision["metrics"],
           "target_improvement": decision["target_improvement"],
           "decided_at": decision["decided_at"]},
  source="can-feedback-loop",
)
```

Payload conforms to `CanRetrainDecisionPayload`. The TimeGAN loop's `classifier_feedback` subscriber reacts to `direction`.

### Step 6: Update the leaderboard

```
ml_compare_timeseries(
  model_ids=[<current_model_id>, <predecessor_id>, <prior_top_3>],
  metric="can_auroc",
)
```

Returns `{metric, ranking, best}`. The new `best` gates Step 7.

### Step 7: If the model improved, publish `can.model.promoted`

```
events_publish(
  event_type="can.model.promoted",
  payload={"model_id": model_id, "model_type": model_type, "rank": rank,
           "metrics": decision["metrics"],
           "predecessor_id": predecessor_id,
           "promoted_at": decision["decided_at"]},
  source="can-feedback-loop",
)
```

Payload conforms to `CanModelPromotedPayload`. Fire ONLY when the new model beats the previous leaderboard top, OR when the predecessor regressed. Promotion events are signal, not noise.

## Decision Logic

Keyed on **AUROC** (headline discrimination metric) with the other five metrics as tiebreakers.

| AUROC band | Direction | Action |
|------------|-----------|--------|
| < 0.80 | `backward` | Fix data: label noise, add failure examples, signal preprocessing, revisit split |
| 0.80 – 0.95 | `forward` | Architecture tuning: hyperparameter search, feature engineering, model ensemble |
| > 0.95 | `forward` | Edge cases & adversarial robustness: TimeGAN augmentation, rare-failure mining, cross-vehicle generalization |
| regressed vs predecessor (any band) | `backward` | Data problem first; re-try architecture only after data is clean |

**Tiebreakers** (apply in order if AUROC is borderline):
1. `episode_recall < 0.80` → `backward` (model isn't seeing the right signal)
2. `brier > 0.15` → `forward` (discriminates but miscalibrated; threshold tuning)
3. `lead_time < 5s` → `backward` (window size or feature lag — data problem)
4. `false_alarm > 0.10/hr` → `backward` (over-triggering means label/split issue)

**Hard stop:** if all five thresholds fail (`rejected` per `can-evaluator`), emit `direction="backward"` with a `reason` that names the specific metrics that failed.

## MCP Tools

- `evals_get_run_regression` — diff current run against predecessor
- `evals_evaluate_computational` — six evaluators (deterministic)
- `ml_compare_timeseries` — single-metric leaderboard
- `memory_store` / `memory_retrieve` — persist and recall decisions
- `events_publish` — emit `can.retrain.decision` and `can.model.promoted` (NOT `events_dispatch` — that name does not exist; the canonical tool is `events_publish`)

## Event Types (Pydantic Schemas)

Both event types are owned by this agent per the spec (`.github/spec/can-agentic-orchestration.md` §3.4). Payloads are Pydantic models — keep them schema-conformant so subscribers can deserialize without custom parsing.

```python
from pydantic import BaseModel
from datetime import datetime

class CanModelPromotedPayload(BaseModel):
    model_id: str
    model_type: str          # lightgbm, lstm, tcn, patchtst, timegan
    rank: int                # 1 = best
    metrics: dict[str, float]
    predecessor_id: str | None = None
    promoted_at: datetime

class CanRetrainDecisionPayload(BaseModel):
    direction: str           # "backward" or "forward"
    reason: str              # human-readable explanation
    metrics: dict[str, float]
    target_improvement: str  # what needs to improve next
    decided_at: datetime
```

## Example Usage

```
# After can-trainer emits can.iteration.completed for run_id=eval-042
regression = evals_get_run_regression(run_id="eval-042")
# → {"regressed": false, "avg_score_delta": +0.04, ...}
metrics = {"can_auroc": 0.86, "can_auprc": 0.78, "can_brier": 0.12,
           "can_lead_time": 6.4, "can_false_alarm": 0.07,
           "can_episode_recall": 0.83}

# AUROC 0.86 → 0.80-0.95 band → forward
decision = {"direction": "forward",
            "reason": "AUROC 0.86 in tuning band; lead-time and false-alarm pass.",
            "metrics": metrics,
            "target_improvement": "Hyperparameter search + 3-model ensemble.",
            "decided_at": "2026-07-26T18:42:11Z"}

memory_store(user_id='can-feedback-loop',
  content=f"DECISION: run_id=eval-042\nDIRECTION: forward\nREASON: {decision['reason']}",
  category='fact',
  metadata={"tags": ["can-feedback"], "run_id": "eval-042",
            "model_id": "can-tcn-2026-07-26-007", "direction": "forward"})
events_publish(event_type="can.retrain.decision", payload=decision,
               source="can-feedback-loop")
ranking = ml_compare_timeseries(
  model_ids=["can-tcn-2026-07-26-007", "can-tcn-2026-07-25-003"],
  metric="can_auroc")
# → {"best": "can-tcn-2026-07-26-007", "ranking": [...]}
events_publish(event_type="can.model.promoted",  # model improved
  payload={"model_id": "can-tcn-2026-07-26-007", "model_type": "tcn",
           "rank": 1, "metrics": metrics,
           "predecessor_id": "can-tcn-2026-07-25-003",
           "promoted_at": decision["decided_at"]},
  source="can-feedback-loop")
```

## Key Rules

- Use `events_publish` — never `events_dispatch`. The latter does not exist; the canonical tool is `events_publish` (`source="can-feedback-loop"` is the audit trail).
- Always include `decided_at` / `promoted_at` (ISO-8601 UTC) so dashboard charts can plot the loop over time.
- Persist *before* you publish. Memory is the source of truth; events are the notification layer. If `events_publish` fails the decision is still recoverable via `memory_retrieve`.
- One decision per training iteration. Do not emit both `can.retrain.decision` and `can.model.promoted` for the same run unless the model actually improved over its predecessor.
- `direction="backward"` does NOT mean "discard the run" — it means "fix the data first." The model checkpoint still ships; only the next training iteration is rerouted to data work.
- AUROC bands (0.80 / 0.95) are the pipeline's agreed thresholds; do not re-derive per-iteration. If they need to move, that is a spec change, not a runtime decision.
