# CAN Agentic Orchestration Spec

**Date:** 2026-07-24
**Status:** APPROVED — authoritative post-`.8.2` sequence
**Epic:** `python-factory-sbhyq`
**Depends on:** `can-failure-prediction.md`, `ml-dataset-generation.md`

---

## 1. Purpose

This spec defines an **agent-authored, durable MCP workflow architecture** for
CAN failure prediction. Agents and skills select or author workflow data;
workflow and owning bricks execute data creation, model training, evaluation,
conformance, promotion, and feedback through MCP boundaries.

### 1.1 Why Agentic?

| Hardcoded Approach | Agentic + durable workflow approach |
|-------------------|---------------------------------------|
| Bespoke scripts for each model | Native family adapter + declarative workflow step |
| Python dispatch chains | Durable allowlisted named-MCP execution |
| No explainability | Immutable evidence and passport lineage |
| Rigid workflows | Versioned data-defined workflows |
| No memory across sessions | Durable state and evidence survive restart |

### 1.2 Core Principle

**The system is agent-authored and durably workflow-executed.** Agents and skills may select or author workflow data, but the `workflow` brick owns durable execution through allowlisted named MCP calls. Owning bricks (`dataset`, `machine_learning`, `evals`) retain validation, policy, artifact, and promotion authority; no agent, bespoke executor, or direct cross-brick import replaces those boundaries.

---

## 2. Relationship to Existing Agents

> **Critical:** This design extends, not replaces, the existing CAN agents.

### 2.1 Existing Pipeline

The existing `can-pipeline` graph in `defaults_can_pipeline.py` has:

| Agent | Purpose | Status |
|-------|---------|--------|
| `can-ingest` | Ingests raw CAN data | ✅ Keep |
| `can-profiler` | Profiles signal boundaries | ✅ Keep |
| `can-synthesizer` | Generates synthetic failures | ✅ Keep |
| `can-trainer` | Trains models | ⚠️ Extend |
| `can-gan-loop` | Runs GAN training loop | ✅ Keep |

### 2.2 New Agents

| Agent | Purpose | Relationship |
|-------|---------|--------------|
| `can-data-creator` | Integrate real fleet labels | **Augments** can-synthesizer |
| `can-feedback-loop` | Closed-loop improvement | **New capability** |

> **Note:** Training + evaluation remain fused in the existing `can-trainer` agent (Option B).
> The `can-evaluator` skill is already used by `can-trainer` for 6-metric evaluation.

### 2.3 Decision: Durable Workflow Coordinates; Bricks Own Policy

The existing graph executor remains available for agent coordination, but it is
not the production authority for the post-`.8.2` portfolio. After native family
lifecycles and conformance land, `python-factory-sbhyq.10.1` adds generic,
durable, server-allowlisted named-MCP execution to the `workflow` brick;
`.10.2` expresses Dataset → causal materialization → ML training → eval →
passport → cold conformance → promotion as data. Agents may author or select
that workflow. Dataset, ML, and evals retain their own policy, and composition
uses MCP only—never direct cross-brick imports or a bespoke CAN workflow
platform.

### 2.4 Agent Overlap Resolution

> **Meta-architect requirement:** Resolve overlap between existing `can-trainer` and new agents.

**Current state:** `can-trainer` already trains models AND evaluates with all 6 metrics.

**Decision: Option B — Keep training + evaluation fused in can-trainer.**

| Agent | Responsibility | Status |
|-------|----------------|--------|
| `can-data-creator` | Integrate real fleet labels | **NEW** — augments can-synthesizer |
| `can-trainer` | Train models + evaluate | **EXISTING** — keep as-is |
| `can-feedback-loop` | Closed-loop improvement | **NEW** — adds memory/events |

**Rationale:**
- `can-trainer` already has the 6-evaluator logic in its system prompt
- Splitting training and evaluation adds complexity without clear benefit
- `can-feedback-loop` adds the missing piece: memory persistence and event publishing

### 2.5 Legacy Agent-Coordination Topology

The following graph describes optional agent coordination only. It is not an
alternative production execution path to the durable `.10.1/.10.2` workflow.

**Before (existing):**
```python
# defaults_can_pipeline.py
can_ingest → can_profiler → can_synthesizer → can_trainer → can_gan_loop
```

**After (with new agents):**
```python
# defaults_can_pipeline.py (updated)
can_ingest → can_profiler → can_synthesizer → [can_data_creator] → can_trainer → can_gan_loop → [can_feedback_loop]
```

**New edges:**
- `can_synthesizer` → `can_data_creator` (optional, when real fleet labels are available)
- `can_data_creator` → `can_trainer` (dataset ready for training)
- `can_gan_loop` → `can_feedback_loop` (after GAN iteration completes)

**Node details:**
- `can_data_creator`: Optional node, skipped if no real fleet data
- `can_feedback_loop`: Optional node, publishes events and stores decisions in memory

---

## 3. Architecture

### 3.1 Agent Roles

```
┌─────────────────────────────────────────────────────────────┐
│                    CAN ORCHESTRATION AGENTS                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CAN Data Creator Agent (NEW)                                │
│  ├── Skill: can-data-creator                                 │
│  ├── Tools: dataset_submit_generation (recipe-driven)        │
│  ├── Purpose: Integrate real fleet labels into datasets       │
│  └── Output: URI-addressable dataset artifact                │
│                                                              │
│  CAN Trainer Agent (EXISTING — extended)                     │
│  ├── Skill: can-trainer + can-evaluator (existing)           │
│  ├── Tools: ml_train_timeseries, evals_evaluate_computational│
│  ├── Purpose: Train models + evaluate with 6 evaluators      │
│  ├── Note: Training + evaluation are FUSED (Option B)        │
│  └── Output: Immutable passport refs + conformance evidence      │
│                                                              │
│  CAN Feedback Loop Agent (NEW)                               │
│  ├── Skill: can-feedback-loop                                │
│  ├── Tools: memory_store, memory_retrieve, events_publish    │
│  ├── Purpose: Closed-loop improvement via evals              │
│  └── Output: Retraining decisions, version updates           │
│                                                              │
│  Graph Executor (EXISTING — agent coordination only)          │
│  ├── Graph: can-pipeline                                     │
│  ├── Nodes: can-ingest → can-profiler → can-synthesizer     │
│  │         → [can-data-creator] → can-trainer → can-gan-loop │
│  │         → [can-feedback-loop]                             │
│  └── Purpose: Sequence agent execution                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Tool Dependencies

> **Important:** `can_profile`, `can_synthesize`, `can_augment` are NOT standalone MCP tools.
> They are dataset stage adapters invoked through recipes via `dataset_submit_generation`.

```
dataset brick MCP tools
├── dataset_submit_generation (recipe-driven)
├── dataset_get_job
├── dataset_get_artifact
├── dataset_resolve_artifact
└── can_* (CAN-specific recipe stages, invoked via recipes)

machine_learning brick MCP tools
├── ml_train_timeseries
├── ml_continue_timeseries
├── ml_sample_timeseries
├── ml_compare_timeseries
├── ml_list_timeseries_models
├── ml_train_can_portfolio
├── ml_issue_can_passports
├── ml_run_can_cold_conformance
├── ml_promote_can_passports
└── ml_project_can_pipeline_result

evals brick MCP tools
├── evals_evaluate_can_model
├── evals_evaluate_computational (evaluator_name, y_true, y_pred, scores)
├── evals_record_run
├── evals_get_run_regression
└── evals_list_run_results

memory brick MCP tools
├── memory_store
├── memory_retrieve
└── memory_search_by_time

events brick MCP tools
└── events_publish
```

#### 3.2.1 Durable CAN lifecycle contract

| Tool | Inputs | Trust and idempotency semantics |
|------|--------|---------------------------------|
| `ml_train_can_portfolio` | `attempt_id`, `dataset_request`, `model_family="lightgbm"`, `top_n_can_ids=5`, optional `training_config`, `model_config`, `experiment_name` | Reconciles `dataset_materialize_can_training_bundle`, then trains from exact completed-bundle refs. LNN timing config is derived from `timespans`; Chronos requires a sealed local `local_backbone_ref`. Equal retries replay; divergent attempt reuse conflicts. |
| `ml_issue_can_passports` | `attempt_id`, `training_terminal_ref`, `evaluation_pointers` | Reloads the exact successful training terminal and issues revision-1 candidates. LightGBM requires verified Evals records; LNN and Chronos permit an empty pointer set. |
| `ml_run_can_cold_conformance` | `attempt_id`, `passport_refs` | Reloads exact candidates and stores conformance evidence in authenticated effect receipts. |
| `ml_promote_can_passports` | `attempt_id`, `conformance_receipt_refs` | Trusts receipt refs rather than caller evidence bodies and rechecks Evals adequacy before promotion. |
| `ml_project_can_pipeline_result` | `attempt_id`, `training_terminal_ref`, `promotion_terminal_ref` | Reloads exact successful terminals and projects only from authenticated records. |

`ml_verify_and_promote_can_passport` is a separate authoring-gated generic CAN
passport tool, not one of the five coordinated lifecycle terminals. The
`python-factory-sbhyq.12.1` two-PID acceptance uses
`ml_issue_can_passports` followed by this generic verifier; a coordinated
workflow can instead run cold conformance and `ml_promote_can_passports`.

### 3.3 Model Family Support and Native Authority

| Model Family | Native lifecycle requirement | Authority |
|--------------|------------------------------|-----------|
| LightGBM | Native fit/save/cold-load | Passport artifact digest + adapter descriptor |
| LSTM | Native Torch lifecycle | Passport artifact digest + adapter descriptor |
| TCN | Native Torch lifecycle | Passport artifact digest + adapter descriptor |
| PatchTST | Native family lifecycle | Passport artifact digest + adapter descriptor |
| LNN/LTC | Exact-pinned `ncps.torch.LTC`; candidate conformance replays prepared training timing, while promoted inference requires separate live timing | Passport seals training timing provenance and normalization scale; request timing is execution evidence, never generic Torch fallback |
| Chronos | Exact-pinned `ChronosPipeline` backbone/revision with framework/PEFT serialization | Passport exact ref/revision/digest; never alias or warm registry |
| Supported MLX | MLX-native train/save/fresh-process load after Chronos | Passport artifact; never Torch routing or process-local dictionary |

`python-factory-sbhyq.8.5` is the single native lifecycle conformance matrix
for all seven supported families. It proves train, cold load, restart, inference
parity, tamper rejection, authority, exact framework/backbone pins, and adapter
descriptor checks. `.8.6` is closed as superseded; it is not a second gate.

#### Promoted neural inference timing

The production path is `ml_predict_neural_passport` →
`load_neural_passport_scores` → the literal native family loader. For LNN/LTC,
callers must supply `live_timing_uri` and `live_timing_digest` together. The
strict `LiveTimingArtifactRef` resolves a local bounded `.npy`, verifies the
exact SHA-256 bytes, and requires finite positive numeric values shaped
`(len(live X), sealed window_size)`. Native LTC inference divides those values
by the immutable training-derived `timing_scale`.

Live timing is not required to have a different or equal digest or row count
relative to training timing. Its digest and shape are request/execution
evidence; the passport's training timing digest and shape remain promotion and
conformance authority. LSTM, TCN, and PatchTST omit timing and reject it when
supplied. Deployable the control-plane runtime exact-pins `ncps==1.0.1`.

### 3.4 Event Types

Every agent that publishes events MUST define event types and payload schemas.

| Event Type | Payload | Source Agent |
|------------|---------|--------------|
| `can.dataset.created` | `CanDatasetCreatedPayload` | can-data-creator |
| `can.iteration.completed` | `CanIterationCompletedPayload` | can-trainer |
| `can.model.promoted` | `CanModelPromotedPayload` | owning `machine_learning` promotion policy |
| `can.retrain.decision` | `CanRetrainDecisionPayload` | can-feedback-loop (recommendation only) |

### 3.5 Event Payload Schemas (Pydantic)

```python
from pydantic import BaseModel
from typing import Any
from datetime import datetime

class CanDatasetCreatedPayload(BaseModel):
    """Payload for can.dataset.created event."""
    dataset_uri: str
    manifest_uri: str
    digest: str
    quality: dict[str, float]  # plausibility, consistency, realism scores
    provenance: dict[str, Any]  # source count, failure count, DBC files
    created_at: datetime

class CanIterationCompletedPayload(BaseModel):
    """Payload for can.iteration.completed event."""
    iteration: int
    model_type: str  # lightgbm, lstm, tcn, patchtst, lnn_ltc, chronos, or supported_mlx
    metrics: dict[str, float]  # auroc, auprc, brier, lead_time, false_alarm, episode_recall
    dataset_uri: str
    passport_ref: str  # immutable authority for artifact, contracts, and adapter
    completed_at: datetime

class CanModelPromotedPayload(BaseModel):
    """Owning ML policy's promotion result for one exact passport."""
    model_id: str
    model_type: str
    passport_ref: str  # exact immutable authority
    rank: int | None = None  # reporting only; never authority
    metrics: dict[str, float]
    predecessor_id: str | None = None
    promoted_at: datetime

class CanRetrainDecisionPayload(BaseModel):
    """Payload for can.retrain.decision event."""
    direction: str  # "backward" or "forward"
    reason: str  # human-readable explanation
    metrics: dict[str, float]  # current performance
    target_improvement: str  # what needs to improve
    decided_at: datetime
```

---

## 4. Data Creation Pipeline

### 4.1 CAN Data Creator Agent

**Skill file:** `skills/can-data-creator/SKILL.md`

**Purpose:** Transform raw CAN data into labeled training datasets by integrating real failure labels.

**Workflow:**
1. **Ingest** raw CAN data + tier-3 fleet labels via recipe
2. **Profile** signal boundaries, correlations, temporal patterns
3. **Synthesize** synthetic failures (8 modes) + real failures
4. **Validate** signal plausibility, temporal consistency, label quality
5. **Materialize** URI-addressable dataset with manifest

**Decision logic:**
- If data has real failure labels (tier-3 fleet labels) → use them as ground truth
- If data has no labels → generate synthetic failures
- If data has few VINs → augment with TimeGAN
- If data has many VINs → stratified sampling

### 4.2 Recipe-Driven Data Creation

```python
# Correct pattern: recipe-driven, not direct tool calls
dataset_submit_generation(request={
    "recipe_uri": "recipe://local/can-ingest-fleet@1",
    "input_artifacts": [
        {"uri": "s3://example-bucket/tier-2/", "digest": "..."},
        {"uri": "s3://example-bucket/tier-3/", "digest": "..."}
    ],
    "requested_views": ["default"]
})
```

---

## 5. Model Competition Framework

### 5.1 Native Model Portfolio

The promotion portfolio contains LightGBM, LSTM, TCN, PatchTST, native
LNN/LTC, exact-pinned Chronos, and supported MLX. TimeGAN remains a dataset
augmentation concern, not a promoted inference family in the `.8.5` matrix.
Every promoted model is referenced by an immutable passport; checkpoint paths,
aliases, rankings, and warm registries are not authority.

| Family | Native requirement | Training entry point |
|--------|--------------------|----------------------|
| LightGBM | Framework-native fit/save/cold-load | `ml_train_timeseries(model_type="lightgbm")` |
| LSTM | Torch-native sequence lifecycle | `ml_train_timeseries(model_type="lstm")` |
| TCN | Torch-native sequence lifecycle | `ml_train_timeseries(model_type="tcn")` |
| PatchTST | Native PatchTST lifecycle | `ml_train_timeseries(model_type="patchtst")` |
| LNN/LTC | `ncps.torch.LTC`; immutable training timing provenance plus separate live timing for promoted inference | `ml_train_timeseries(model_type="lnn")` |
| Chronos | Exact-pinned `ChronosPipeline`; framework/PEFT serialization | `ml_train_timeseries(model_type="chronos")` |
| Supported MLX | MLX-native lifecycle and cold loader | Fine-tuning port MLX adapter |

### 5.2 Evaluation Framework (6 Evaluators)

> **Note:** Evaluation requires running inference first via `ml_predict_timeseries` to produce `y_true`, `y_pred`, and `scores` arrays.

| Evaluator | What It Measures | Threshold | Tool Call |
|-----------|------------------|-----------|-----------|
| AUROC | Discrimination | ≥0.80 | `evals_evaluate_computational(evaluator_name="can_auroc", y_true=..., y_pred=..., scores=...)` |
| AUPRC | Precision-recall | ≥0.75 | `evals_evaluate_computational(evaluator_name="can_auprc", y_true=..., y_pred=..., scores=...)` |
| Brier | Calibration | ≤0.15 | `evals_evaluate_computational(evaluator_name="can_brier", y_true=..., y_pred=..., scores=...)` |
| Lead-time | Early detection | ≥5s | `evals_evaluate_computational(evaluator_name="can_lead_time", y_true=..., y_pred=..., scores=...)` |
| False-alarm | Specificity | ≤0.10 | `evals_evaluate_computational(evaluator_name="can_false_alarm", y_true=..., y_pred=..., scores=...)` |
| Episode-recall | Completeness | ≥0.80 | `evals_evaluate_computational(evaluator_name="can_episode_recall", y_true=..., y_pred=..., scores=...)` |

### 5.3 Closed-Loop Decision Tree

```
After each training iteration:
├── AUROC < 0.80
│   └── Focus on data quality improvements
│       ├── Check for label noise
│       ├── Add more failure examples
│       └── Improve signal preprocessing
├── AUROC 0.80-0.95
│   └── Focus on architecture tuning
│       ├── Hyperparameter optimization
│       ├── Feature engineering
│       └── Model ensemble
├── AUROC > 0.95
│   └── Focus on edge cases
│       ├── Adversarial robustness (TimeGAN)
│       ├── Rare failure modes
│       └── Cross-vehicle generalization
└── Always
    ├── Persist evaluation + conformance evidence
    └── Ask owning ML policy to promote one exact immutable passport
```

---

## 6. Implementation Plan

### 6.0 Exact Execution Order

All work stays under the existing `python-factory-sbhyq` epic:

`sbhyq.11 → sbhyq.8.3 → sbhyq.8.4 → sbhyq.8.8 → sbhyq.8.5 → sbhyq.10.1 → sbhyq.10.2 → sbhyq.8.7`

Dataset deterministic injection correctness is the first gate. Native
`ncps.torch.LTC` follows, then exact-pinned Chronos, then MLX-native lifecycle,
then the one portfolio conformance matrix. Durable generic named-MCP execution
must land before the data-defined end-to-end workflow; legacy deletion is last.
See [CAN Failure Prediction Review](./can-failure-prediction-review.md#8-recommended-sequencing)
and [ML Dataset Generation](./ml-dataset-generation.md#40-authoritative-can-portfolio-order).

### Phase 0: Pre-Implementation (Required)

> **Meta-architect requirement:** Complete before any new code.

| Task | Description | Owner | Status |
|------|-------------|-------|--------|
| 0.1 | Audit existing CAN agents in `defaults_can_agents.py` | meta-architect | ✅ Done |
| 0.2 | Fix tool name errors in design docs | implementer | ✅ Done |
| 0.3 | Define event type schemas | meta-architect | ✅ Done |
| 0.4 | Decide: extend existing agents or add new ones | meta-architect + user | ✅ Done (Option B) |

### Phase 1: Data Creation Agent

| Task | Description | Owner | Status |
|------|-------------|-------|--------|
| 1.1 | Update `can-data-creator/SKILL.md` with correct tool names | implementer | ✅ Done |
| 1.2 | Create tier-3 fleet label adapter | implementer | ⏳ Pending |
| 1.3 | Wire as AgentConfig in `defaults_can_agents.py` | implementer | ✅ Done |
| 1.4 | Test with recipe-based data creation | qa-tester | ⏳ Pending |

### Phase 2: Native Portfolio Readiness

| Order | Bead | Completion boundary |
|---:|---|---|
| 1 | `sbhyq.11` | Deterministic Dataset injection contract passes |
| 2 | `sbhyq.8.3` | Exact-pinned `ncps.torch.LTC`: prepared training timing drives candidate conformance; promoted inference requires separate digest-bound live timing normalized by the sealed training scale |
| 3 | `sbhyq.8.4` | Exact-pinned native Chronos lifecycle and framework/PEFT serialization |
| 4 | `sbhyq.8.8` | MLX-native lifecycle/cold loader with no Torch or process-local authority |
| 5 | `sbhyq.8.5` | One seven-family train/cold-load/restart/parity/tamper/authority matrix passes; `.8.6` remains superseded |

### Phase 3: Agent Coordination (Non-Production)

> Phases 3–5 describe optional agent coordination and feedback only. They do
> not execute or promote the production portfolio; `.10.1/.10.2` own durable
> execution, and owning bricks retain policy.

> **Note:** Training + evaluation remain fused in `can-trainer` (Option B).
> No separate training orchestrator agent needed.

| Task | Description | Owner | Status |
|------|-------------|-------|--------|
| 3.1 | Verify `can-trainer` handles multi-family training | qa-tester | ✅ Done |
| 3.2 | Test multi-family competition | qa-tester | ⏳ Pending |

### Phase 4: Evaluation Framework

> **Note:** Evaluation stays fused in `can-trainer` (Option B).
> `can-evaluator` skill is already used by `can-trainer`.

| Task | Description | Owner | Status |
|------|-------------|-------|--------|
| 4.1 | Verify `can-evaluator/SKILL.md` is used by `can-trainer` | implementer | ✅ Done |
| 4.2 | Verify 6-evaluator framework works through `can-trainer` | qa-tester | ✅ Done |
| 4.3 | Add missing evaluators (lead_time, false_alarm, episode_recall) if needed | implementer | ⏳ Pending |

### Phase 5: Feedback Loop

| Task | Description | Owner | Status |
|------|-------------|-------|--------|
| 5.1 | Create `can-feedback-loop/SKILL.md` | implementer | ✅ Done |
| 5.2 | Wire to memory and events bricks | implementer | ⏳ Pending |
| 5.3 | Test closed-loop iteration | qa-tester | ⏳ Pending |

---

## 7. Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Dataset injection | Seeded timeout/freeze windows and event boundaries are deterministic with full provenance | `.11` regression suite |
| Native portfolio | All seven supported families train and cold-load through native lifecycles | `.8.5` conformance matrix |
| Contract authority | Passport pins dataset/features/timespans, framework/backbone, digest, and adapter descriptor | Tamper + authority checks fail closed |
| Durable execution | Allowlisted named-MCP tasks persist identity, evidence, and retry/resume state | `.10.1` workflow tests |
| End-to-end workflow | Dataset → materialization → training → eval → passport → cold conformance → promotion completes after restart | `.10.2` durable integration test |
| Legacy retirement | No legacy path is deleted before `.8.5` and `.10.2` pass | `.8.7` deletion gate |

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Injection regression hidden by model metrics | Every downstream comparison is invalid | Make `.11` the first hard gate |
| Generic routing masks non-native lifecycle | Warm tests pass but cold inference is unauthoritative | Native ncps/Chronos/MLX adapters plus passport checks |
| Multiple conformance gates drift | Families receive inconsistent evidence | Keep one `.8.5` matrix; `.8.6` stays superseded |
| Agent or workflow takes brick policy | Cross-brick coupling and non-reproducible promotion | Workflow coordinates named MCP evidence; owning bricks decide |
| Premature legacy deletion | No parity-safe rollback | Require both `.8.5` and `.10.2` before `.8.7` |

---

## 9. References

### Specs
- [CAN Failure Prediction Spec](./can-failure-prediction.md)
- [ML Dataset Generation Spec](./ml-dataset-generation.md)
- [CAN Agentic Orchestration Design](../../.kiro/specs/can-agentic-orchestration/design.md)

### Steering
- [CAN Failure Prediction Steering](../../.agents/steering/can-failure-prediction.md)
- [Dev Principles](../../.agents/steering/dev-principles.md)

### Skills
- [CAN Data Creator Skill](../../components/agent/src/factory/agent/skills/can-data-creator/SKILL.md)
- [Dataset Generation Skill](../../components/agent/src/factory/agent/skills/dataset-generation/SKILL.md)
- [CAN GAN Loop Skill](../../components/agent/src/factory/agent/skills/can-gan-loop/SKILL.md)

### Code
- [Existing CAN Agents](../../components/agent/src/factory/agent/registry/defaults_can_agents.py)
- [Existing CAN Pipeline](../../components/agent/src/factory/agent/registry/defaults_can_pipeline.py)
- [ML Train Timeseries](../../components/machine_learning/src/factory/machine_learning/mcp/finetuning_tools.py)
- [Evals Computational](../../components/evals/src/factory/evals/runtime/adapters/computational_evaluators.py)

---

**Document version:** 1.0
**Last updated:** 2026-08-03
**Author:** opencode + meta-architect review
**Status:** APPROVED — durable lifecycle implemented