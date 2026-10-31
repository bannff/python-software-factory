# Learning Event Taxonomy

## Goal

Define the minimal runtime taxonomy for learning-loop orchestration in the factory without introducing a new first-class `LearningRun` write model.

## Context

The factory already has the right architectural primitives for a real enough learning loop:

- a shared event envelope and event model in the Events brick
- dotted event types with wildcard-capable subscriptions
- run-oriented result shapes in the Evals brick
- existing workflow completion hooks on `graph.completed`

What is missing is a canonical contract for learning-related events and a durable projection shape for the ML tab.

This document extends the existing runtime taxonomy. It does not introduce a new orchestration subsystem.

## Guidance

- Use the existing Events brick `Envelope` and `Event` models as the base contract.
- Treat `run_id` and `workflow_run_id` as the primary correlation spine for learning flows.
- Keep graph as lineage and evidence, not the source of truth for learning state.
- Use durable events and projections for UI state; do not infer completion from graph shape alone.
- Keep event names in dotted form and scoped to durable state transitions.
- Prefer execution profiles over a heavyweight learned-policy abstraction.

## Details

### Base contract to extend

All learning-loop events inherit the existing runtime shape from the Events brick:

- envelope context: `tenant_id`, `principal_id`, `session_id`, `request_id`, `agent_id`, `tool_name`, `timestamp`
- event metadata: `id`, `timestamp`, `source`, `type`, `payload`
- denormalized correlation: `trace_id`, `session_id`, `principal_id`

### Canonical learning correlation fields

Every event that participates in the learning loop should include these payload fields:

- `run_id`: stable identifier for the evaluated or executed run
- `workflow_run_id`: stable identifier for the workflow instance when different from `run_id`
- `graph_id`: graph or workflow definition identifier
- `session_id`: actor or agent session identifier
- `principal_id`: user or agent principal
- `profile_id`: named execution profile identifier
- `profile_version`: immutable version or hash of the execution profile

Recommended when applicable:

- `target_app`
- `workflow_type`
- `vuln_class`
- `game_id`
- `experiment_id`

### Shared payload taxonomy

Learning-loop payloads should reuse a small set of common groups.

#### Subject

Identifies what the run was acting on.

- `target_app`
- `workflow_type`
- `vuln_class`
- `game_id`
- `experiment_id`

#### Outcome

Carries the result of a state transition.

- `status`
- `score`
- `reward_value`
- `reward_unit`
- `verdict`
- `converged`

#### Evidence

Provides drill-down handles for the UI.

- `event_id`
- `transaction_id`
- `memory_id`
- `metric_id`
- `eval_run_id`
- `graph_node_ids`

#### Timing

Provides durable runtime semantics.

- `started_at`
- `completed_at`
- `duration_ms`

### Canonical event types

Start with event types that represent durable, independently useful state transitions.

#### `graph.completed`

Producer:

- `agent` or workflow execution path

Required payload additions:

- canonical correlation fields
- `status`
- `duration_ms`
- `node_count`

Meaning:

- a workflow run finished and downstream subscribers may derive reward, memory, and metrics work from it

#### `reward.computed`

Producer:

- reward or eval computation handler

Required payload additions:

- canonical correlation fields
- `score`
- `reward_value`
- `reward_unit`
- `verdict`
- `idempotency_key`

Meaning:

- reward logic finished and produced a durable result that can feed ledger, memory, and metrics steps

#### `wallet.rewarded`

Producer:

- blockchain brick

Required payload additions:

- canonical correlation fields
- `reward_value`
- `transaction_id`
- `wallet_id`
- `idempotency_key`

Meaning:

- reward side effect has been committed to the ledger

#### `memory.learning_stored`

Producer:

- memory brick or learning persistence handler

Required payload additions:

- canonical correlation fields
- `memory_id`
- `summary_type`
- `idempotency_key`

Meaning:

- the system stored a distilled learning artifact tied to the run

#### `convergence.checked`

Producer:

- metrics or machine learning brick

Required payload additions:

- canonical correlation fields
- `metric_id`
- `converged`
- `baseline_window`
- `comparison_window`

Optional payload additions:

- `regression_signal` — propagated from `MetricsRuntime.detect_drift` when a named baseline exists for the metric. Typical values: `"block"`, `"warn"`, `"ok"`. Lets downstream policy routers act on the gating decision without re-querying metrics.
- `baseline_tag` — tag of the baseline that produced `regression_signal`.

Meaning:

- the system evaluated whether recent runs show stability, drift, or improvement

### Optional event types

Only add these when they are independently visible and operationally meaningful.

#### `profile.selected`

Use when profile selection is dynamic, user-visible, or experiment-relevant. If a profile is implied by static workflow config, store the profile fields on the run and skip the extra event.

#### `game.completed`

Use when games are first-class environments whose terminal state should feed learning flows independently of graph workflow completion.

### Ownership by brick

- `agent` or `workflow`: emit `graph.completed`
- `games` or `evals`: compute reward inputs and emit `reward.computed`
- `blockchain`: apply ledger mutation and emit `wallet.rewarded`
- `memory`: persist distilled learning and emit `memory.learning_stored`
- `metrics` or `machine_learning`: evaluate trend or convergence and emit `convergence.checked`

The `games` brick should not remain the owner of the entire post-run loop. It may define environment semantics and reward inputs, but durable side effects should stay with the bricks that own them.

### Idempotency rules

Event-only choreography is not safe without explicit deduplication.

Every side-effect event should carry `idempotency_key`.

Recommended key forms:

- `reward.computed`: `reward:{workflow_run_id}:{profile_version}`
- `wallet.rewarded`: `wallet:{workflow_run_id}:{profile_version}:{reward_value}`
- `memory.learning_stored`: `memory:{workflow_run_id}:{summary_type}`

Subscribers must treat repeated events with the same key as no-ops.

### ML tab projection contract

The ML tab should be backed by a durable, rebuildable projection keyed by `run_id` and `workflow_run_id`.

Suggested projection shape:

```json
{
  "run_id": "uuid",
  "workflow_run_id": "uuid",
  "graph_id": "rt-scan-idor",
  "profile_id": "balanced",
  "profile_version": "2026-05-04.1",
  "principal_id": "kiro-agent",
  "session_id": "session-123",
  "target_app": "WebGoat",
  "workflow_type": "dast",
  "vuln_class": "IDOR",
  "status": "completed",
  "score": 0.82,
  "reward_value": 12,
  "reward_unit": "tokens",
  "converged": false,
  "duration_ms": 4200,
  "reward_event_id": "evt-1",
  "wallet_event_id": "evt-2",
  "memory_event_id": "evt-3",
  "convergence_event_id": "evt-4",
  "transaction_id": "tx-123",
  "memory_id": "mem-123",
  "metric_id": "reward-stability",
  "updated_at": "2026-05-04T20:10:00Z"
}
```

This projection is a read model, not a new domain entity. It exists to keep the ML tab honest and queryable.

### Truth hierarchy

Use this order of truth:

1. durable event log
2. ledger and memory side-effect records
3. ML projection rows derived from durable events
4. graph lineage and evidence views

The UI should always be able to drill down from a projection row to raw evidence.

## Examples

### Example: reward computation event

```json
{
  "source": "games.rewards",
  "type": "reward.computed",
  "payload": {
    "run_id": "run-123",
    "workflow_run_id": "wf-123",
    "graph_id": "rt-scan-idor",
    "session_id": "sess-1",
    "principal_id": "kiro-agent",
    "profile_id": "balanced",
    "profile_version": "2026-05-04.1",
    "target_app": "WebGoat",
    "workflow_type": "dast",
    "vuln_class": "IDOR",
    "status": "completed",
    "score": 0.82,
    "reward_value": 12,
    "reward_unit": "tokens",
    "verdict": "improved",
    "duration_ms": 4200,
    "idempotency_key": "reward:wf-123:2026-05-04.1"
  }
}
```

### Example: subscription choreography

- `graph.completed` triggers reward computation
- `reward.computed` triggers ledger mutation
- `wallet.rewarded` triggers learning persistence
- `memory.learning_stored` triggers convergence evaluation

A policy router subscribing to `convergence.checked` can read `regression_signal` directly from the payload to decide whether to block, warn, or pass — no separate `metrics_detect_drift` round trip required.

## Links / Next Steps

- Add a small schema module or documented validator for the required learning-loop payload fields.
- Move reward, ledger, memory, and convergence side effects behind brick-owned handlers where they are still bundled together.
- Add subscription YAMLs for the canonical event transitions.
- Build the ML tab from the projection contract above rather than from graph inference or fine-tuning-job lists.