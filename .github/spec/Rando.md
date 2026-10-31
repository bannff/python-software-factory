# CAN Failure Prediction — Implementation Spec

This spec defines the implementation plan for *Rando* — a system to predict car failures by analyzing CAN bus telemetry data. It depends on the following foundation specs:

- [ML Dataset Generation Spec](./ml-dataset-generation.md) — dataset brick, recipe system, artifact lifecycle
- [CAN Failure Prediction and Agentic Dataset Spec](./can-failure-prediction.md) — domain data contract, taxonomy, labeling
- [CAN Frame Analysis and Variation Synthesis Spec](./can-frame-analysis-variation-synthesis.md) — offline analysis, protocol-valid variation synthesis

## 1. Background

Rando is an agent-driven pipeline that:

1. Parses raw MF4 CAN log files into structured frame data
2. Decodes frames into physical signals using DBC files
3. Profiles signal boundaries, correlations, and temporal dynamics
4. Generates synthetic CAN data that captures real-world edge cases
5. Trains time-series models to predict failures from CAN telemetry
6. Runs inference live on a CAN bus for real-time failure prediction

The core insight: CAN data is high-frequency binary time-series, not conversational text. The existing dataset pipeline (AgentInstruct → S2M → APIGen → ReviewInstruct) is built for LLM training. CAN data needs a parallel **Signal Pipeline** with math-based stages.

### 1.1 Source Data

67 MF4 files (MDF 4.11 format), ~48MB total, captured from a vehicle CAN bus. Plus 10 gzipped MF4 files and an `opendbc` folder containing candidate DBC files for decoding.

Initial analysis of the first MF4 file shows:
- 9,936 CAN frames over 77 seconds
- 55 unique CAN IDs
- Mostly raw/undecoded bytes (no physical signal values)
- Payload lengths 1-8 bytes, 8-byte frames dominate (5,554)
- Regular periodic traffic on IDs 0x20, 0xB4, 0x25, 0xB0, 0xB2
- Sparse payloads: 50-82% zero bytes in most frames
- Median frame gap: 0.25ms, min: 0.05ms

### 1.2 What Rando Is NOT

- Not an LLM. The prediction model is a dedicated time-series classifier.
- Not a text pipeline. No tokenization, no conversational data.
- Not real-time bus actuation. Read-only monitoring and prediction.
- Not a standalone project. Lives inside the control-plane runtime using existing bricks.

## 2. Architecture Decisions

### 2.1 Decode Strategy

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Raw bytes** | Use CAN ID + payload bytes directly | No DBC needed, zero decode loss | No semantic meaning, model must learn byte patterns from scratch | Reject — loses physical context |
| **DBC decode** | Match MF4 against candidate DBC files, decode to physical signals | Semantic meaning (RPM, temp, speed), proven boundaries, standard approach | Requires DBC match, some signals may not decode cleanly | **Recommended** — you have opendbc candidates |
| **UDS decode** | Use Unified Diagnostic Services for on-demand ECU queries | Exact diagnostic values, manufacturer-standard | Diagnostic-only (not continuous telemetry), requires active ECU communication, high overhead | Reject — wrong use case for continuous monitoring |

**Decision: DBC decode.** Match your 67 MF4 files against the opendbc candidate library. Score candidates by CAN ID overlap, DLC match, frequency match, and signal plausibility. Fallback to raw bytes for unmatched IDs.

### 2.2 Data Format

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Raw frames** | Keep as individual CAN events with timestamps | Zero information loss, preserves exact timing | Hard to window, variable-length, no signal alignment | Keep as intermediate format |
| **Polars DataFrame (rasterized)** | Resample all signals to a consistent time grid (e.g., 10ms) | Aligned for windowing, fast parallel ops, memory-efficient | Interpolation introduces minor smoothing, fixed resolution | **Recommended** for training |
| **Parquet** | Columnar storage for processed data | Compressed, efficient I/O, ecosystem support | Not a processing format, storage only | Use for artifact output |

**Decision: Dual format.** Raw frames for ingest and profiling. Polars rasterized DataFrame (10ms grid) for training. Parquet for artifact storage.

### 2.3 Synthetic Data Generation

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **SDV (Synthetic Data Vault)** | Python framework with Copulas, CTGAN, TVAE | Simple API, tabular-focused, stable training, good documentation | Limited temporal modeling, may miss sequential dynamics | **Start here** — simplest path to synthetic data |
| **TimeGAN** | GAN with recurrent network for sequential data | Learns temporal dynamics, generates realistic sequences | Complex to tune, training instability, requires substantial data | Graduate to if SDV quality insufficient |
| **TabDDPM** | Diffusion model for tabular data | More stable than GANs, captures multi-modal distributions, state-of-the-art | Newer, less ecosystem support, heavier compute | Evaluate after SDV baseline |
| **Gretel.ai** | Commercial/open-source time-series synthesis | Purpose-built for high-frequency data, enterprise-grade | Paid cloud option, vendor dependency | Consider for production scale |
| **Chronos / TimesFM** | Pre-trained time-series foundation models | Zero-shot forecasting, fine-tunable | Built for forecasting not synthesis, may not generate training data | Evaluate for edge-case generation |

**Decision: SDV first, then TimeGAN.** SDV gets you from raw data to synthetic corpus fastest. TimeGAN if temporal fidelity (signal correlations, phase shifts) matters for failure prediction quality.

### 2.4 Model Architecture

| Option | Description | Latency | Training Cost | Best For | Verdict |
|---|---|---|---|---|---|
| **LightGBM + tsfresh** | Gradient-boosted trees on extracted time-series features | Ultra-low (<1ms) | Low (seconds) | Fast baseline, feature importance, tabular simplicity | **Baseline** — train first |
| **LSTM / Bi-LSTM** | Recurrent network on windowed sequences | Low (1-5ms) | Medium (minutes) | Sequential dependencies, variable time gaps | **Compare** — strong time-series performer |
| **TCN (Temporal Convolutional Network)** | 1D convolutions across time windows | Ultra-low (<1ms) | Low-Medium | Ultra-low latency deployment, parallelizable | **Compare** — if latency is critical |
| **PatchTST / Transformer** | Downsized transformer on time-series patches | Medium (5-10ms) | High (minutes-hours) | Complex non-linear patterns, long-range dependencies | **Compare** — if accuracy matters most |

**Decision: Train all four.** Use the `evals` brick to compare. LightGBM is the baseline (fast, interpretable). LSTM and TCN are the practical middle ground. PatchTST is the accuracy ceiling.

### 2.5 Evaluation Approach

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Custom evaluation scripts** | One-off Python scripts | Quick to write | No comparison framework, no persistence, hard to reproduce | Reject |
| **MLflow manual** | Log metrics to MLflow tracking server | Persistence, UI, comparison | Manual orchestration, no built-in evaluators | Partial — use for experiment tracking |
| **`evals` brick** | Factory eval harness with multi-evaluator support | Built-in comparison, Strands Evals SDK, LLM-as-judge for label QA, experiment serialization | May need custom evaluators for time-series metrics | **Recommended** — extend with CAN-specific evaluators |

**Decision: `evals` brick with custom evaluators.** Register CAN-specific evaluators (AUROC, AUPRC, Brier score, lead-time accuracy, false alarm rate, episode-level recall). Use the brick's comparison and experiment persistence.

### 2.6 New Brick vs Existing Infrastructure

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **New `can_analytics` brick** | Dedicated brick for CAN-specific logic | Clean separation, CAN-specific MCP surface | 200+ LOC budget pressure, new brick maintenance, may duplicate existing capabilities | Reject — over-engineering |
| **Recipe stages in `dataset` brick** | CAN-specific logic as `DatasetStagePort` adapters | Fits existing architecture, leverages async job system, checkpoint/resume | Domain logic lives inside dataset brick | **Recommended** — this is what the recipe system is for |
| **Skills + sub-agents** | CAN analyst persona with domain skills | Reusable, composable, agent-driven, no new brick surface | Requires agent orchestration | **Recommended** — the control-plane runtime drives the pipeline |

**Decision: No new brick.** CAN-specific logic lives as recipe stages inside the `dataset` brick (Noise Injector, Temporal Windowing, Failure Labeler). the control-plane runtime orchestrates via skills and sub-agents. The `machine_learning` brick handles training.

## 3. Data Pipeline Architecture

### 3.1 Signal Pipeline (Parallel to LLM Pipeline)

```
[Raw MF4 Files]
       │
       ▼ (asammdf + DBC decode)
┌──────────────────────────────────────────────┐
│  Signal Pipeline (Time-Series Branch)        │
├──────────────────────────────────────────────┤
│ 1. Ingest & Decode                           │
│    -> MF4 parse, DBC match, signal extraction│
├──────────────────────────────────────────────┤
│ 2. Profile & Edge Map                        │
│    -> Static boundaries, temporal dynamics,  │
│       frequency/periodicity analysis         │
├──────────────────────────────────────────────┤
│ 3. Noise & Edge Injector                     │
│    -> Synthetic variations, dropouts,        │
│       bit-flips, offsets, drift              │
├──────────────────────────────────────────────┤
│ 4. Temporal Windowing                        │
│    -> Rolling lookback windows, overlap,     │
│       sequence construction                  │
├──────────────────────────────────────────────┤
│ 5. Failure Labeler                           │
│    -> Inject ground-truth failure targets,   │
│       anomaly timestamps, DTC markers        │
├──────────────────────────────────────────────┤
│ 6. Quality & Split                           │
│    -> Leakage checks, chronological splits,  │
│       vehicle-separated validation           │
└──────────────────────────────────────────────┘
       │
       ▼
[Training Dataset Artifact (dataset URI)]
       │
       ▼
┌──────────────────────────────────────────────┐
│  Model Training (machine_learning brick)     │
├──────────────────────────────────────────────┤
│  - LightGBM baseline                         │
│  - LSTM / Bi-LSTM                            │
│  - TCN                                       │
│  - PatchTST                                  │
└──────────────────────────────────────────────┘
       │
       ▼
[Trained Model Artifact]
       │
       ▼
┌──────────────────────────────────────────────┐
│  Live Inference Bridge                       │
├──────────────────────────────────────────────┤
│  - Real-time frame ingestion                 │
│  - Rolling context buffer                    │
│  - Sub-millisecond prediction                │
│  - Alert threshold → LLM context bridge      │
└──────────────────────────────────────────────┘
```

### 3.2 Mapping to Existing Bricks

| Pipeline Stage | Brick | Adapter/Tool |
|---|---|---|
| MF4 ingest | `dataset` | New `DatasetStagePort` adapter |
| DBC decode | `dataset` | New `DatasetStagePort` adapter (uses `opendbc`/`cantools`) |
| Profiling | `dataset` | New `DatasetStagePort` adapter (outputs JSON constraint schema) |
| Noise injection | `dataset` | New `DatasetStagePort` adapter (math-based variation) |
| Windowing | `dataset` | New `DatasetStagePort` adapter (Polars rolling windows) |
| Labeling | `dataset` + `agent` | Agent-driven label proposal, dataset-stage materialization |
| Quality checks | `dataset` | Existing quality gates + CAN-specific checks |
| Training | `machine_learning` | Existing experiment tracking + fine-tuning |
| Evaluation | `evals` | Custom CAN evaluators registered via MCP |
| Orchestration | `agent` | CAN analyst skill + sub-agent dispatch |

## 4. Implementation Epics

### Epic 1: MF4 Ingest & DBC Decode
**Goal:** Parse 67 MF4 files, match against opendbc candidates, decode CAN signals.

**Work:**
- Build MF4 parser stage adapter using `asammdf`
- Score opendbc candidates (CAN ID overlap, DLC match, frequency match, signal plausibility)
- Handle gzipped MF4 files
- Output: rasterized Polars DataFrame per capture (10ms grid)
- Fallback: raw bytes for unmatched CAN IDs

**Acceptance criteria:**
- All 67 MF4 files parsed successfully
- DBC match confidence score for each candidate
- Decoded signal summary (unique signals, value ranges, coverage)
- At least one candidate matched with >80% CAN ID coverage

**Dependencies:** `asammdf`, `polars`, `cantools` or `opendbc`

### Epic 2: Signal Profiling & Edge Mapping
**Goal:** Build a profiling agent that maps the boundaries of the decoded signal space.

**Work:**
- Static boundary analysis (min/max/variance/clipping per signal)
- Temporal correlation detection (signal pairs that move together)
- Delta threshold computation (max rate-of-change per signal per timestep)
- Frequency/periodicity analysis per CAN ID
- Sparsity and zero-byte analysis
- Output: JSON constraint schema consumed by downstream generators

**Acceptance criteria:**
- Constraint schema generated for all decoded signals
- Correlation matrix showing signal relationships
- Frequency table showing periodic vs sporadic CAN IDs
- Delta thresholds with physical plausibility check

**Dependencies:** Epic 1 (decoded signals)

### Epic 3: Synthetic Data Generation
**Goal:** Multiply real data into a large training corpus with injected failure modes.

**Work:**
- Noise & edge injector (dropouts, bit-flips, offsets, drift, signal degradation)
- Temporal windowing (rolling 5-second lookbacks, configurable overlap)
- Failure label injection (anomalous patterns at synthetic failure timestamps)
- Synthetic failure modes: signal drift, sudden drop-to-zero, out-of-sequence injection, checksum errors, ECU timeout
- Materialize as dataset artifact via `dataset` brick

**Acceptance criteria:**
- Synthetic dataset ≥10x the size of real data
- At least 5 distinct failure modes injected
- Each synthetic record has ground-truth labels
- Temporal correlations preserved in synthetic data
- Dataset artifact materialized with manifest, provenance, and quality results

**Dependencies:** Epic 1 (raw frames), Epic 2 (constraint schema)

### Epic 4: Model Training & Comparison
**Goal:** Train multiple architectures, compare with eval harness.

**Work:**
- LightGBM baseline on tsfresh-extracted features ✅
- LSTM/Bi-LSTM on windowed sequences ✅ (PyTorch, temporal split, gradient clipping, normalization)
- TCN on windowed sequences ✅ (PyTorch, causal-style convolutions)
- PatchTST / Temporal Transformer on windowed sequences — deferred (low priority)
- Register CAN-specific evaluators in `evals` brick: AUROC, AUPRC, Brier score, lead-time accuracy, false alarm rate, episode-level recall ✅
- Run comparison experiments via `evals` brick ✅
- Log all experiments to MLflow via `machine_learning` brick ✅

**Acceptance criteria:**
- LightGBM, LSTM, TCN trained and comparable ✅
- Eval harness reports AUROC, AUPRC, Brier score for each ✅
- Lead-time accuracy measured (how far before failure the model detects it) ✅
- False alarm rate measured ✅
- Best model selected based on composite score ✅
- All experiments tracked in MLflow with reproducible configs ✅
- Security: pickle RCE fixed, allow_pickle=False, config bounds validated ✅

**Dependencies:** Epic 3 (training dataset), `evals` brick, `machine_learning` brick

### Epic 5: Live Inference Pipeline
**Goal:** Bridge the trained model to real CAN bus data for real-time prediction.

**Work:**
- Real-time MF4 stream ingestion (or replay from saved captures)
- Rolling context buffer (last N seconds of decoded signals)
- Prediction engine (sub-millisecond inference on windowed input)
- Alert threshold system (anomaly score → alert levels)
- LLM context bridge (alert state fed to the control-plane runtime for conversational queries)
- Visualization (real-time signal plots, prediction overlays)

**Acceptance criteria:**
- Inference latency <5ms per prediction window
- Alert generated within 1 second of anomalous pattern
- LLM can query current prediction state via MCP
- Visualization shows real-time signals and prediction confidence

**Dependencies:** Epic 4 (trained model), `machine_learning` brick (inference)

### Epic 6: Agentic Dataset Skills
**Goal:** Teach the control-plane runtime to orchestrate the full CAN pipeline via MCP.

**Work:**
- CAN analyst skill (`skills/can-analyst/SKILL.md`) — MF4 analysis, DBC matching, signal profiling
- Recipe authoring skill — compose CAN-specific dataset recipes
- Model evaluation skill — run eval harness, compare results, recommend model
- Wire skills into the control-plane runtime agent registry
- Update `compx-platform` skill with CAN-specific tools

**Acceptance criteria:**
- the control-plane runtime can submit CAN dataset jobs via chat
- the control-plane runtime can profile signal data and report findings
- the control-plane runtime can run model comparisons and recommend best architecture
- All skills discoverable via `agent_list_skills()`

**Dependencies:** Epic 1-5 (full pipeline working)

### Epic 7: Pipeline Wiring & Integration
**Goal:** Wire all CAN adapters into the dataset brick's executor and agent system so the control-plane runtime can drive the pipeline end-to-end via chat.

**Work:**
- Register CAN stage adapters (`can_ingest`, `can_profile`, `can_synthesize`) in the dataset brick's local executor stage registry
- Add `recipe://local/can-ingest@1`, `recipe://local/can-profile@1`, `recipe://local/can-synthesize@1` to the recipe resolver
- Register `CAN_AGENTS` and `CAN_PIPELINE_GRAPH` in the agent system's `defaults.py`
- Verify `agent_list_skills()` returns `can-analyst`, `can-recipe-author`, `can-evaluator`
- End-to-end test: the control-plane runtime chat agent receives "analyze my CAN captures", dispatches the pipeline, returns results

**Acceptance criteria:**
- `dataset_submit_generation` with a CAN recipe URI resolves to the correct stage adapters
- `agent_list_skills()` includes all 3 CAN skills
- `agent_get_agent_registry()` includes all 4 CAN agents
- End-to-end chat test passes (submit → poll → complete → artifact URI returned)

**Dependencies:** Epic 1-6 (all adapters and skills built)

## 5. Dependency Summary

```
Epic 1 (Ingest & Decode)
  └── Epic 2 (Profile & Edge Map)
        └── Epic 3 (Synthetic Generation)
              └── Epic 4 (Model Training)
                    └── Epic 5 (Live Inference)
                          └── Epic 6 (Agentic Skills)
                                └── Epic 7 (Pipeline Wiring)
```

Epics 1-5 are sequential. Epic 6 (skills) can be developed in parallel with Epic 3-5 once the pipeline stages are defined.

## 6. External Dependencies

| Package | Purpose | Required For |
|---|---|---|
| `asammdf` | MF4/MDF 4.11 parsing | Epic 1 |
| `polars` | High-performance DataFrame operations | Epic 1-3 |
| `cantools` or `opendbc` | DBC file parsing and signal decoding | Epic 1 |
| `tsfresh` | Automated time-series feature extraction | Epic 4 (LightGBM) |
| `sdv` | Synthetic data generation (CTGAN, Copulas) | Epic 3 |
| `lightgbm` | Gradient-boosted tree model | Epic 4 |
| `torch` | LSTM, TCN, PatchTST models | Epic 4 |
| `scikit-learn` | Metrics, preprocessing, train/test splits | Epic 4 |

## 7. Open Questions

1. **Failure labels:** Do you have annotated failure timestamps in your data, or must we generate synthetic failure labels? This determines Epic 3 complexity.
2. **Vehicle identity:** Do you know the vehicle make/model? This affects DBC matching confidence.
3. **Live bus access:** Do you have a CAN bus adapter (e.g., Kvaser, Vector) for live inference, or is this offline analysis only?
4. **Scale:** How large should the synthetic corpus be? 10x, 100x, 1000x the real data?
5. **Deployment target:** Local laptop inference, or edge device (Raspberry Pi, Jetson) on the vehicle?
6. **Record schema evolution:** How do CAN-specific `DatasetStagePort` adapters coexist with the existing `ConversationRecord`-validating executor? (Resolved in Section 9.1.)
7. **Training infrastructure:** Should time-series model training live in `machine_learning` (new port), a new component, or somewhere else? (Resolved in Section 9.2.)
8. **Artifact format:** What's the canonical artifact format for CAN datasets? `frames.parquet` + `episodes.parquet` + `labels.parquet` + `splits.json`? Does this map to `DatasetArtifactRef.available_views`?
9. **Taxonomy-to-recipe binding:** Does a CAN recipe include a taxonomy snapshot URI in its `DatasetGenerationRequest`, or is taxonomy a separate `graph` brick query at recipe-authoring time?
10. **Checkpoint format:** CAN stage outputs (NumPy arrays, Polars DataFrames) are not JSONL `ConversationRecord` lines. How does the checkpoint store handle non-JSON-serializable artifacts?

## 8. References

### Repository References
- [Dataset brick interface](../../components/dataset/src/factory/dataset/interface.py)
- [Machine learning runtime](../../components/machine_learning/src/factory/machine_learning/runtime/runtime.py)
- [Evals brick](../../components/evals/)
- [Graph taxonomy registry](../../components/graph/src/factory/graph/runtime/taxonomy_registry.py)
- [Agent skills directory](../../components/agent/src/factory/agent/skills/)

### Spec References
- [ML Dataset Generation Spec](./ml-dataset-generation.md)
- [CAN Failure Prediction Spec](./can-failure-prediction.md)
- [CAN Frame Analysis Spec](./can-frame-analysis-variation-synthesis.md)

### Source Data
- 67 MF4 files in `~/Downloads/CAN Data/`
- opendbc candidate DBC files in `~/Downloads/CAN Data/dbc/candidates/opendbc/`
- Public datasets (CSV/TXT):
  - Car-Hacking attack CSVs (2.8M records) — Hacking/Counter Measurement Lab, Korea
  - OTIDS normal_run_data TXT (400K records) — Open Threat Intelligence Dataset
- Hyundai/Kia DBC from opendbc project — decodes Kia public datasets to physical signals

---

## 9. Pre-Implementation Blocking Gaps (Meta-Architect Review)

These three gaps must be resolved before any CAN stage adapter is written. The existing bricks are optimized for LLM workflows (text in → text out), and CAN data breaks those assumptions at multiple layers.

### 9.1 Gap 1: Data Shape Mismatch — `ConversationRecord` vs. CAN Frames

**Severity: HIGH — BLOCKER**

The dataset recipe executor (`stage_runner.py`, `agentic_datasets.py`, `recipe.py`) validates every record as `ConversationRecord` from `agentic_datasets.schemas.messages`. CAN frame records, signal arrays, and windowed tensors are not `ConversationRecord` instances. The spec assumes CAN stages "drop in" as `DatasetStagePort` adapters, but the current executor would reject CAN-shaped records at every stage boundary.

**Evidence:**
- `validation.py` — `validate_conversation_records()` imports `ConversationRecord` and calls `.model_validate()` on every input
- `stage_runner.py` — after stage execution, checkpoint reload calls `validate_conversation_records` again
- `recipe.py` — `load_records()` also validates as `ConversationRecord`

**Decision: Polymorphic `DatasetStagePort` with per-recipe record schema.**

The `DatasetRecipe` model gains a `record_schema` field:

```python
class DatasetRecipe(BaseModel):
    version: str
    schema_version: str = "1.0"
    stages: list[DatasetRecipeStage] = Field(min_length=1)
    record_schema: Literal["conversation", "can_frame", "generic"] = "conversation"
```

The recipe executor dispatches to the appropriate validator based on `record_schema`:
- `"conversation"` — existing `validate_conversation_records()` (backward-compatible default)
- `"can_frame"` — new `validate_can_frame_records()` that accepts CAN-specific Pydantic models
- `"generic"` — pass-through validation (length check only, no schema enforcement)

This enables mixed recipes (CAN ingest → LLM labeling stages) and keeps the existing conversation pipeline untouched.

### 9.2 Gap 2: `machine_learning` Brick is LLM-Only

**Severity: HIGH — BLOCKER**

The `machine_learning` brick's `FineTuningMethod` enum is `{lora, adalora, ia3, prefix_tuning, full, mlx_lora}`. The `ml_create_finetuning_job` tool expects `base_model`, `lora_rank`, `lora_alpha`, `quantization_bits` — parameters for language model adaptation, not for training LightGBM classifiers, LSTM recurrent networks, or TCN convolutions.

**Decision: Extend `machine_learning` with a `TimeSeriesTrainingPort`.**

A new adapter port in `runtime/ports.py`:

```python
class TimeSeriesTrainingPort(Protocol):
    """Train time-series classifiers on windowed CAN data."""
    def train_lightgbm(self, X_train, y_train, config: dict) -> str: ...
    def train_lstm(self, X_train, y_train, config: dict) -> str: ...
    def train_tcn(self, X_train, y_train, config: dict) -> str: ...
    def train_patchtst(self, X_train, y_train, config: dict) -> str: ...
    def predict(self, model_id: str, X: Any) -> Any: ...
    def get_model(self, model_id: str) -> dict | None: ...
```

The existing experiment tracking surface (MLflow, metrics logging, run management) extends naturally — a training run creates an experiment, logs metrics (AUROC, AUPRC, etc.), and persists the model artifact. Only the training loop and model serialization are new adapters.

New MCP tools (registered alongside existing `ml_*` tools):
- `ml_train_timeseries(model_type, X_uri, y_uri, config)` → returns `job_id`
- `ml_predict_timeseries(job_id, X_uri)` → returns predictions URI
- `ml_compare_timeseries(job_ids)` → returns comparison table

### 9.3 Gap 3: `evals` Brick Evaluators are LLM-as-Judge

**Severity: MEDIUM — BLOCKER**

The `evals` brick's evaluators (`output`, `helpfulness`, `faithfulness`, `coherence`, `trajectory`, `goal_success`) are Strands LLM-as-judge evaluators. CAN-specific metrics (AUROC, AUPRC, Brier score, lead-time accuracy, false alarm rate, episode-level recall) are mathematical/computational metrics, not LLM judgments. The `evals_evaluate` tool expects `input_text`, `output_text` — string arguments, not numeric arrays.

**Decision: Register computational evaluators alongside LLM-as-judge evaluators.**

The `evals` brick's evaluator registry accepts two types:
- **LLM evaluators** (existing) — text-in/text-out, uses Strands Evals SDK
- **Computational evaluators** (new) — array-in/score-out, uses scikit-learn/numpy

New evaluator names registered in the evaluator lookup:
- `can_auroc` — Area Under ROC Curve
- `can_auprc` — Area Under Precision-Recall Curve
- `can_brier` — Brier score (calibration)
- `can_lead_time` — Lead-time accuracy (how far before failure)
- `can_false_alarm` — False alarm rate
- `can_episode_recall` — Episode-level recall

The training pipeline computes metrics via scikit-learn, then persists results through `evals_record_run` with the computed scores. This uses the existing storage layer without modifying the LLM evaluator interface.

---

## 10. Agent Orchestration Architecture (Strands Expert Review)

### 10.1 Graph, Not Swarm

The CAN pipeline has **deterministic stage ordering** with data dependencies. The `GraphExecutor` is the right primitive — not swarms (free-form collaboration) or standalone agents.

**Graph definition:**

```python
CAN_PIPELINE_GRAPH = {
    "id": "can-pipeline",
    "name": "CAN Analysis Pipeline",
    "description": "6-stage CAN frame analysis: ingest → profile → synthesize → window → label → quality",
    "nodes": [
        {"id": "ingest", "type": "agent", "agent_id": "can-ingest"},
        {"id": "profile", "type": "agent", "agent_id": "can-profiler"},
        {"id": "synthesize", "type": "agent", "agent_id": "can-synthesizer"},
        {"id": "window", "type": "agent", "agent_id": "can-windower"},
        {"id": "label", "type": "agent", "agent_id": "can-labeler"},
        {"id": "quality", "type": "agent", "agent_id": "can-qa"},
    ],
    "edges": [
        {"source": "ingest", "target": "profile"},
        {"source": "profile", "target": "synthesize"},
        {"source": "synthesize", "target": "window"},
        {"source": "window", "target": "label"},
        {"source": "label", "target": "quality"},
        {"source": "quality", "target": "synthesize",
         "condition": "needs_resynthesis"},  # feedback loop
    ],
    "entry_points": ["ingest"],
}
```

Each node is an `AgentConfig` with CAN-specific skills and scoped MCP tools.

**Dispatch flow:**
```
User: "Analyze my 67 CAN captures"
  → the control-plane runtime chat agent
    → invoke_graph(graph_id="can-pipeline", task="Analyze 67 MF4 files")
      → GraphExecutor runs 6 nodes sequentially
        → Each node calls dataset_submit_generation for its stage
        → Polls dataset_get_job until complete
        → Stores results in memory with tags
      → Quality gate passes or routes back to synthesize
    → Chat agent reports: "Pipeline complete. Dataset URI: dataset://..."
```

### 10.2 Three Skills, Not One

| Skill | Purpose | MCP Tools Referenced |
|-------|---------|---------------------|
| `can-analyst` | MF4 parsing, DBC matching, signal profiling | `dataset_submit_generation`, `dataset_get_job`, `memory_store`, `memory_retrieve` |
| `can-recipe-author` | Compose CAN-specific dataset recipes | `dataset_submit_generation` with CAN recipe URIs, recipe digest computation |
| `can-evaluator` | Run model comparisons, recommend architecture | `evals_evaluate`, `ml_list_finetuning_jobs`, `ml_get_job_status` |

**`can-analyst` SKILL.md outline:**

```markdown
---
name: can-analyst
description: MF4 CAN log analysis, DBC matching, signal profiling, and constraint schema generation.
---
# CAN Analyst

You are analyzing raw MF4 CAN bus captures to extract signal boundaries,
temporal dynamics, and protocol constraints.

## MCP Tools

### Submit a CAN ingest job
dataset_submit_generation(request={
  "recipe_uri": "recipe://local/can-ingest@1",
  "recipe_digest": "<sha256>",
  "input_artifacts": [{"uri": "file://...", "digest": "<sha256>"}],
  ...
})

### Poll for completion
dataset_get_job(job_id="<job_id>")

### Store profiling results in memory
memory_store(user_id='can-analyst', content='PROFILE: ...', category='fact',
  metadata={"tags": ["can-profile", "<vehicle_id>"], "dbc_match": "<confidence>"})

### Retrieve prior profiles for comparison
memory_retrieve(user_id='can-analyst', query='CAN profile for <vehicle_id>',
  tags=["can-profile"], limit=5)

## Chained Workflow
1. Submit MF4 ingest → poll until completed
2. Retrieve constraint schema from artifact
3. Score DBC candidates (CAN ID overlap, DLC match, frequency)
4. Store profile in memory with vehicle_id tag
5. Hand constraint schema to can-recipe-author for synthesis
```

### 10.3 Agent Registration

```python
# defaults_can_agents.py
CAN_AGENTS = [
    AgentConfig(
        id="can-ingest",
        name="CAN Ingest Agent",
        model=SONNET,
        system_prompt="You parse MF4 files, match DBC candidates, and extract decoded signals.",
        skills=["can-analyst", "compx-platform"],
    ),
    AgentConfig(
        id="can-profiler",
        name="CAN Profiler Agent",
        model=SONNET,
        system_prompt="You map signal boundaries, temporal correlations, and delta thresholds.",
        skills=["can-analyst", "compx-platform"],
    ),
    # ... one per pipeline stage (6 total)
]
```

The `can-analyst` skill is also added to the `the control-plane runtime-default` chat agent so users can trigger CAN analysis directly from chat.

### 10.4 Taxonomy Registration

Register via the existing `taxonomy_registry.py`:

```python
register_extension(
    "can_failure",
    node_types={
        "Vehicle": {"properties": ["vehicle_id", "make", "model", "year"]},
        "Trip": {"properties": ["trip_id", "start_ts", "end_ts", "odometer_km"]},
        "CANBus": {"properties": ["bus_name", "channel", "baud_rate"]},
        "ECU": {"properties": ["ecu_id", "firmware_version"]},
        "Frame": {"properties": ["arbitration_id", "dlc", "frame_type"]},
        "Signal": {"properties": ["signal_name", "unit", "min_value", "max_value"]},
        "DTC": {"properties": ["dtc_code", "description", "severity"]},
        "FailureMode": {"properties": ["mode_name", "category", "symptoms"]},
    },
    relationship_types={
        "HAS_ECU": {"source": "Vehicle", "target": "ECU"},
        "PART_OF_TRIP": {"source": "Frame", "target": "Trip"},
        "EMITS_FRAME": {"source": "ECU", "target": "Frame"},
        "DECODES_TO": {"source": "Frame", "target": "Signal"},
        "CORRELATES_WITH": {"source": "Signal", "target": "Signal"},
        "PRECEDES_FAILURE": {"source": "Signal", "target": "FailureMode"},
        "ANNOTATED_AS": {"source": "Frame", "target": "DTC"},
    },
)
```

Surfaces through the existing `graph://schemas/taxonomy/{domain}` resource template — no new MCP code needed.

### 10.5 Memory Convention for Failure Episodes

```python
# Storing a failure episode
memory_store(
    user_id="can-analyst",
    content="EPISODE: vehicle=V001 trip=T042 failure_mode=coolant_leak "
            "lead_time=45min signals=[coolant_temp:105→120, fan_rpm:0→2800] "
            "dtc=P1234 confidence=0.92",
    category="fact",
    memory_type="long_term",
    metadata={
        "tags": ["can-episode", "failure", "coolant"],
        "vehicle_id": "V001",
        "failure_mode": "coolant_leak",
        "taxonomy_version": "1",
    },
)

# Retrieving similar episodes during labeling
memory_retrieve(
    user_id="can-analyst",
    query="coolant temperature failure pattern",
    tags=["can-episode", "failure"],
    metadata={"vehicle_id": "V001"},
    limit=10,
)
```

### 10.6 Live Inference MCP Tool

```python
@mcp.tool()
def can_get_live_state() -> dict:
    """Get current CAN bus prediction state.

    Returns recent anomaly scores, active alerts, and signal context.
    Use this to answer conversational questions about vehicle health.
    """
    return {
        "anomaly_score": 0.87,
        "prediction": "coolant_system_failure",
        "lead_time_minutes": 12,
        "confidence": 0.91,
        "active_signals": {
            "coolant_temp": 118.5,
            "fan_rpm": 3200,
            "vehicle_speed": 0,
        },
        "alert_level": "warning",
        "recent_episodes": [...],  # from memory_retrieve
    }
```

Added to the the control-plane runtime chat agent's tool list so it can answer "What's going to happen?" by reading the live inference state.

---

## 11. Risk Assessment (Meta-Architect Review)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Data shape mismatch** blocks stage execution | HIGH | Blocker — CAN stages can't run in current recipe executor | Section 9.1: polymorphic `record_schema` field |
| **Model training infrastructure** doesn't exist for time-series | HIGH | Blocker — no way to train LightGBM/LSTM/TCN through `machine_learning` | Section 9.2: `TimeSeriesTrainingPort` adapter |
| **200 LOC violations** from 6+ new adapters | MEDIUM | Guardian check will fail, blocking merge | Deliberate file splitting: one adapter per file, shared CAN utilities in separate modules |
| **DBC match quality** insufficient for signal decoding | MEDIUM | Falls back to raw bytes; synthetic data less meaningful | Spec accounts for fallback (Section 2.1); add fallback contract |
| **Synthetic data quality** fails temporal fidelity checks | MEDIUM | Model trained on bad synthetic data, poor real-world performance | SDV→TimeGAN progression path reduces this risk |
| **`evals` brick incompatibility** with mathematical metrics | MEDIUM | CAN metrics can't be computed through evals pipeline | Section 9.3: computational evaluator registration |
| **MF4 parsing failures** for gzipped or malformed files | LOW-MEDIUM | Incomplete dataset, biased training | `asammdf` handles both; add parse-error handling |
| **GPU dependency** for LSTM/TCN/PatchTST training | LOW | User on laptop without GPU | LightGBM baseline runs on CPU; progressive model approach mitigates |

---

## 12. File Budget (200 LOC Compliance)

| File | Brick | Max LOC | Purpose |
|---|---|---|---|
| `runtime/adapters/can_ingest.py` | dataset | 200 | MF4 parsing + DBC matching |
| `runtime/adapters/can_profile.py` | dataset | 200 | Signal profiling + constraint schema |
| `runtime/adapters/can_synthesize.py` | dataset | 200 | SDV/TimeGAN synthetic generation |
| `runtime/adapters/can_window.py` | dataset | 150 | Polars rolling window construction |
| `runtime/adapters/can_label.py` | dataset | 150 | Failure label injection |
| `runtime/can_utils.py` | dataset | 150 | Shared CAN helpers (record models, validation) |
| `runtime/adapters/timeseries_training.py` | machine_learning | 200 | LightGBM/LSTM/TCN/PatchTST training |
| `mcp/can_evaluators.py` | evals | 150 | AUROC, AUPRC, Brier, lead-time, false alarm |
| `skills/can-analyst/SKILL.md` | agent | 150 | CAN analyst skill |
| `skills/can-recipe-author/SKILL.md` | agent | 100 | Recipe authoring skill |
| `skills/can-evaluator/SKILL.md` | agent | 100 | Model evaluation skill |
| `registry/defaults_can_agents.py` | agent | 100 | 6 agent configs |
| `registry/defaults_can_pipeline.py` | agent | 80 | Graph config |

---

## 13. Canary Tests (Strands Expert Review)

| # | Test | Asserts | When |
|---|---|---|---|
| C1 | Taxonomy registration | `resolve_domain_taxonomy("can_failure")` returns CAN node/relationship types without security base pollution | After taxonomy registration |
| C2 | Recipe resolution | `resolve_recipe` handles `recipe://local/can-ingest@1` with CAN-specific stages | After Epic 1 |
| C3 | Graph execution | `GraphExecutor` runs `can-pipeline` with 6 nodes in correct order | After Epic 6 |
| C4 | Skill discovery | `agent_list_skills()` returns `can-analyst`, `can-recipe-author`, `can-evaluator` | After Epic 6 |
| C5 | Memory convention | Failure episodes stored with `tags=["can-episode"]` are retrievable via `memory_retrieve` | After Epic 3 |
| C6 | Record polymorphism | CAN frame records pass through recipe executor without `ConversationRecord` validation error | After Section 9.1 implementation |
| C7 | Time-series training | `ml_train_timeseries(model_type="lightgbm", ...)` returns a valid `job_id` | After Section 9.2 implementation |
| C8 | Computational evaluators | `evals_evaluate(evaluator="can_auroc", ...)` returns a numeric score | After Section 9.3 implementation |

---

## 14. Verification Gates

| Gate | When | Command |
|---|---|---|
| `foreman_guardian_check` passes with all CAN files under 200 LOC | After file budget implementation | `foreman_guardian_check` |
| `foreman_resolve_dependencies` resolves `dataset`+`machine_learning`+`evals` with new `pip_packages` | After Section 9.2+9.3 | `foreman_resolve_dependencies(bricks=["dataset","machine_learning","evals"])` |
| All 5 existing `dataset` MCP tools work with CAN recipe submissions | After Section 9.1 | `dataset_submit_generation` with `record_schema="can_frame"` |
| All 8 canary tests pass | After each epic | `pytest` with canary test markers |

---

## 15. Honest Assessment (2026-07-21)

### What Works

| Component | Status | Evidence |
|-----------|--------|----------|
| 5-stage pipeline | ✅ Complete | ingest → profile → synthesize → window → augment |
| Data | ✅ 92M+ decoded records | Toyota (92M) + Kia (210K) + S3 OBD-II (100K) across 5 vehicles |
| LightGBM training | ✅ AUROC 0.95-1.00 | Tested on 5 CAN IDs, dominates other architectures |
| Pipeline MCP tool | ✅ Built | `can_run_full_pipeline` chains all stages |
| CAN taxonomy | ✅ Built | 10 node types, 8 relationships in graph brick |
| Synthetic evaluators | ✅ 4 evaluators | distribution_similarity, temporal_coherence, statistical_fidelity, mode_coverage |
| TimeGAN | ✅ Implemented | Generator + Discriminator, 6 tests pass, MCP tools ready |
| CTGAN | ✅ Implemented | Drop-in for GaussianCopula |
| Hyundai DBC decoding | ✅ Working | Unlocked 3.2M Kia records from public datasets |
| Evals harness | ✅ Wired | `evals_evaluate_can_model` MCP tool in training loop |
| SCANIA validation | ✅ Done | Real failure data validated against modeling approach |

### What Doesn't Work Yet

| Component | Status | Why |
|-----------|--------|-----|
| LSTM/TCN | ⚠️ Underperform | AUROC 0.73-0.77, need more data per CAN ID |
| Heuristic baseline | ❌ ~0.5 AUROC | Threshold rules can't learn CAN patterns |
| Cross-dataset validation | ❌ Not done | Don't know if models generalize across vehicles |
| TimeGAN at scale | ❌ Not tested | Only trained on 1 CAN ID |
| Real failure labels | ⚠️ Partial | SCANIA data available, not yet integrated |
| Live inference | ❌ Untested | can_inference.py exists but untested |
| Live feedback loop | ❌ Not built | python-factory-sbhyq.3 tracked |

### Training Techniques Comparison

| Model | Type | How It Works | Our Result |
|-------|------|-------------|------------|
| LightGBM | Gradient-boosted trees | Extracts features from windowed signals, learns decision rules | ✅ Best performer |
| LSTM | Recurrent neural network | Reads sequential signal patterns, learns temporal dependencies | ⚠️ Needs more data |
| TCN | Temporal convolutional | 1D convolutions across time windows, parallelizable | ⚠️ Needs more data |
| TimeGAN | Adversarial generative | Generator vs Discriminator learn to produce realistic CAN windows | 🔧 Built, untested at scale |
| GaussianCopula | Statistical generative | Fits per-signal distributions, samples independently | ✅ Fast, decent quality |
| CTGAN | Tabular GAN | Mode-specific normalization, better for non-Gaussian | ✅ Drop-in replacement |
| Heuristic | Threshold rules | Signal exceeds mean ± 2σ → anomaly | ❌ Can't learn patterns |

### Next Steps (Priority Order)

| Priority | Task | Bead |
|----------|------|------|
| P1 | Train LightGBM on all 44 CAN IDs | python-factory-10b |
| P2 | Wire 6 production evaluators | python-factory-10c |
| P2 | Test TimeGAN vs SDV | python-factory-10d |
| P3 | Cross-dataset validation | python-factory-10e |
| P3 | TimeGAN at scale | python-factory-10f |
| P3 | Integrate SCANIA real-failure data | python-factory-sbhyq.1 |
| P3 | Build live feedback loop | python-factory-sbhyq.3 |
