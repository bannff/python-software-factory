# ML Dataset Generation Spec

Working copy mirrored from the Kiro ML dataset-generation spec:

- [Requirements](../../.kiro/specs/ml-dataset-generation/requirements.md)
- [Design](../../.kiro/specs/ml-dataset-generation/design.md)
- [Plan](../../.kiro/specs/ml-dataset-generation/plan.md)

This is the spec to work first. The CAN failure prediction spec depends on this ML/dataset foundation.

## 1. Purpose

Dataset generation must be owned by the dedicated `dataset` brick, not by `machine_learning`.

The brick should:

- generate datasets asynchronously,
- return a `job_id` immediately,
- expose a durable dataset URI when the job completes,
- keep stage-specific implementation details inside the worker layer,
- and let `machine_learning`, `evals`, and other consumers operate only on dataset URIs.

## 2. Requirements

### P0: Extraction and Async Decoupling

1. Dataset generation must occur within `components/dataset/`, not `machine_learning`.
2. Generated datasets must be consumable by `evals`, RAG apps, or `machine_learning` as simple URIs.
3. Pipeline tasks may take hours, so the public API and MCP tools must return immediately with a `job_id`.
4. Domain-specific stage logic such as `s2m` must remain an internal implementation detail of the worker layer.

### P1: Queue Architecture Selection

The implementation should research the worker backend rather than hard-coding one up front.

Possible options:

- RQ
- Celery
- a subprocess/state-tracking approach using `state` / `storage`

### P2: Machine Learning Refactor

The `machine_learning` API must be stripped of generation logic and should assume datasets already exist, referenced only by URI or ID.

## 3. Design

### 3.0 Factory Architecture

The target is two cooperating bricks:

- `dataset` owns asynchronous creation, validation, versioning, and
  materialization of immutable dataset bundles.
- `machine_learning` owns experiment tracking, training execution,
  checkpoints, model/adapter artifacts, and model export.

`machine_learning` consumes a durable `dataset_uri` plus a versioned manifest;
it must not own generation jobs or depend on a generator's local file paths.
The manifest records the dataset digest, schema version, training views, quality
gates, and provenance so an ML run can be reproduced independently of the
generation backend.

#### Brick boundary contract

These boundaries apply the single normative control-plane doctrine in
[`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md) to dataset generation; this spec does not create a competing authority.

<a name="dataset-owns-agentic-datasets"></a>
##### `dataset` owns Agentic-Datasets
AgentInstruct, S2M, APIGenMT, and ReviewInstruct are upstream frameworks that
produce dataset-stage artifacts; they are implemented **only** as internal
`DatasetStagePort` adapters inside `components/dataset/`. No other brick may
reimplement, wrap, or directly import these stage callables or their upstream
pipeline contract.

<a name="agent-authors-recipes-not-stages"></a>
##### `agent` authors recipes, not stages
The `agent` brick exposes skills, playbooks, and Strands tooling that describe
*how* to compose a dataset recipe and which `dataset` MCP tools to invoke. It
does not own the Agentic-Datasets frameworks, execute stage adapters, sequence
worker stages, retry failed stage runs, or route LLM calls on behalf of the
`dataset` brick.

<a name="ml-consumes-dataset-artifacts"></a>
##### `machine_learning` consumes dataset artifacts
The `machine_learning` brick receives a typed `DatasetTrainingInput` — a
dataset URI, manifest URI, digest, selected view name, and view schema version —
from any caller. It owns fine-tuning and experiment-tracking frameworks (e.g.,
MLX, AI-Fine-Tuning, MLflow, Weights & Biases). It resolves and validates the
artifact through the `dataset` MCP surface before training and never imports
dataset internals.

<a name="dataset-depends-on-llm-gateway"></a>
##### Current compatibility path: pinned stage model access

The existing Agentic-Datasets compatibility adapters resolve a frozen backend,
model, and inference configuration through the `llm_gateway` MCP surface. This
is model access for an already selected, allowlisted stage invocation; Dataset
does not use it to choose a strategy, revise a blueprint, or orchestrate agents.
New intelligent composition belongs to the Agent brick.

Dataset stage recipes declare a registered `backend`, optional `model`, and only
the recognized inference overrides: `temperature`, `max_tokens`, `timeout`,
`num_retries`, and `fallbacks`. Recipe configs MUST NOT pass raw `llm_config`
blobs. `DatasetLLMConfigPort` resolves the frozen selection so provenance,
fallback authorization, and cost observability can be recorded in the manifest.

#### Agentic-Datasets Compatibility Integration

The pinned AgentInstruct, S2M, APIGenMT, and ReviewInstruct v2 callables are a
current compatibility surface whose upstream internals may perform LLM-driven
transformation or agent orchestration. Treat that behavior as current-state
debt subordinate to the normative control-plane split; it is not authority for
new Dataset-owned intelligence.

Dataset invokes each callable only through an allowlisted `DatasetStagePort`
adapter with frozen stage/version/config and immutable input references. The
adapter translates typed artifact contracts and captures outputs and evidence;
it does not choose stages, alter objectives, revise prompts after results, or
make acceptance and promotion decisions.

The Agent brick authors or selects an immutable blueprint through a bounded registered Graph; the control-plane runtime invokes that Agent surface and submits the result. The Dataset brick validates allowlisted references and materializes the blueprint as the durable job owner. It persists immutable outputs, applies quality gates, emits lifecycle events, and resumes only through bounded idempotent replay over frozen checkpoints. Workflow owns cross-brick attempts, global budgets, retries, and stopping; Evals freezes policy before execution and returns immutable evidence-bound reports and typed deficiencies to the next Agent revision attempt.

Keep an internal `AgenticDatasetsPipelinePort` only for a pinned upstream-native
pipeline contract that provides required semantics not safely represented as
individually checkpointable stage calls. It is not the default integration path.
The reviewed upstream pipeline and Strands orchestration are not sufficient to
be treated as a production orchestration framework without adapter validation.

The implemented Agentic-Datasets integration primitives are pinned to the unpublished upstream
commit `26cb6833a5fec672d429efa54c17d83ee8e61b4e` from
`https://github.com/bannff/Agentic-Datasets.git`. The factory imports the four
v2 callables from their stage modules, validates canonical `ConversationRecord`
inputs and outputs at every adapter boundary, and provides immutable,
digest-addressed stage checkpoint storage. These adapters and checkpoint
utilities are wired into the active worker recipe executor. An
import/version/signature canary fails closed if the installed VCS revision or
callable parameters differ.

These skills and playbooks are behavioral guidance only. They must not import
`factory.dataset.runtime`, instantiate `DatasetStagePort` adapters, execute stage
transformations, retry stages, or write recipe artifacts outside the `dataset`
MCP surface. Cross-brick composition happens only through MCP tool calls and the
shared Pydantic contracts (`DatasetGenerationRequest`, `DatasetManifest`,
`DatasetJobReceipt`, etc.).

#### Dataset Recipe and Artifact Contract

The public MCP surface remains job-oriented regardless of the selected
integration shape:

- `dataset_submit_generation(request: DatasetGenerationRequest) -> DatasetJobReceipt`
- `dataset_get_job(job_id: JobId) -> DatasetJobStatus`
- `dataset_get_artifact(job_id: JobId) -> DatasetArtifactRef`
- `dataset_resolve_artifact(dataset_uri: DatasetUri) -> DatasetManifest`

A recipe is a versioned declarative graph of stage invocations. For an
agentic-conversation dataset, it may compose AgentInstruct, S2M, APIGenMT, and
ReviewInstruct and expose CPT, SFT, or DPO-compatible views. For CAN failure
prediction, the recipe is separate: ingest, normalize, episode, enrich, label,
validate, split, and materialize. Failure injection is recipe/stage execution
whose truth is the materialized Dataset artifact—not a training-time ML
mutation or process-local object. Seed, mode, selected signals, event count,
event boundaries, source-record identity, stage/recipe versions, and input/output
digests must survive in manifest provenance. Agentic stages may aid labeling or
review, but cannot replace canonical frame records, provenance, or leakage
checks.

Seeded injection is deterministic over the immutable recipe and inputs. In
particular, `ecu_timeout` must zero every decoded signal throughout each
injected event window, while `signal_freeze` must hold only the selected signals
at one stable prior value for the full window. Event rate/count/boundaries must
also be repeatable, with non-target modes and provenance preserved. This P0
correctness gate is `python-factory-sbhyq.11`; it is separate from
`python-factory-bzm3s`, which broadens physics-constrained correlated
multi-signal realism.

When `can_window` emits its optional timing plane, fixed-grid timing represents
elapsed integration per cell: one `grid_ns` value for every observation cell,
independent of frame sparsity, with no read into the label horizon. Duplicate or
regressing source timestamps fail closed per CAN ID when timing emission is
requested. This keeps Dataset timing deterministic while allowing promoted LNN
inference to provide a separate request-scoped live timing artifact.

`DatasetGenerationRequest` contains an immutable recipe reference and digest,
input artifact URIs and digests, an optional immutable context-snapshot
reference, requested training views, an execution policy, and an idempotency
key. `DatasetArtifactRef` contains `dataset_uri`, `manifest_uri`, digest,
schema version, available named views, and an optional backend-usable
`training_uri`.

Each completed job materializes a self-contained bundle through `storage`. Its
manifest includes source and output URIs, content digests, recipe and stage
adapter versions, pinned upstream revision and implementation variant,
immutable context and tool-schema snapshots, quality results, provenance,
and authorized fallback data. `graph` holds taxonomy and evidence relationships, `memory`
supplies bounded retrieval context to agents, `events` records lifecycle
outcomes, and `evals` evaluates frozen bundle and model artifacts. Raw
high-volume data remains in storage, not graph, memory, or blockchain.

Upstream fallback behavior is fail-closed by default. A recipe may authorize a
specific fallback only when it records the requested and actual backend, the
fallback reason, and degraded-quality status in the stage result and final
manifest. Every stage validates its output against the canonical schema before
the next stage starts. APIGenMT must use an immutable, allowlisted MCP
tool-schema snapshot and never invoke arbitrary production tools while creating
training data. Retries begin from immutable stage artifacts and may not silently
refresh mutable graph or memory context.

#### Fine-Tuning Placement

Do not create a separate `fine_tuning` brick. AI-Fine-Tuning's CPT/SFT/DPO,
PEFT LoRA/QLoRA, and MLX capabilities should become adapters behind the existing
`machine_learning` fine-tuning port. Training and experiment lineage share a
single lifecycle: dataset compatibility, configuration, run metrics,
checkpoints, final model/adapter artifact, and export.

`machine_learning` receives a typed training input containing the dataset URI,
manifest URI, digest, selected view name, and view schema version. It resolves
and validates that artifact through the `dataset` MCP surface before training;
it never imports dataset internals or accepts a worker-local output path.

`machine_learning` can use a tracking adapter such as MLflow or Weights & Biases
when that operational need exists, but the factory's own port remains the stable
interface. Select one initial production tracker after an operational evaluation;
do not implement competing tracker integrations speculatively.

### 3.1 Public Contract

The public Python interface and MCP surface use the canonical job and artifact
vocabulary from section 3.0. Stage execution is not a public API. Recipe
authoring is an `@authoring` operation; job submission and job-state operations
are `@operational`; artifact resolution is `@deterministic`.

### 3.2 Execution Layer

The long-running pipeline should run outside the request path.

The Dataset brick dispatches and tracks the bounded materialization job while a
persistent worker queue executes frozen recipe stages. The worker owns stage
artifacts, quality checks, final materialization, and bounded idempotent replay
over immutable inputs or checkpoints. Workflow owns cross-brick attempt history,
global retry policy, budgets, cancellation, recovery, stopping, and terminal
reasons. A base may transport a job request but cannot contain dataset-stage
business logic.

### 3.3 MCP Surface

The MCP-facing tools are non-blocking state managers rather than full pipeline
executors: `dataset_submit_generation`, `dataset_get_job`,
`dataset_get_artifact`, and `dataset_resolve_artifact`.

### 3.4 Removal Of Cross-Coupling

The `machine_learning` brick should no longer manage generation. It should accept a resolvable `dataset_uri` representing an artifact produced by the `dataset` brick.

## 4. Implementation Plan

### 4.0 Authoritative CAN Portfolio Order

The post-`.8.2` work is one dependency chain under the existing
`python-factory-sbhyq` epic:

`sbhyq.11 → sbhyq.8.3 → sbhyq.8.4 → sbhyq.8.8 → sbhyq.8.5 → sbhyq.10.1 → sbhyq.10.2 → sbhyq.8.7`

This places native exact-pinned `ChronosPipeline` lifecycle and
framework/PEFT serialization (`.8.4`) before MLX-native lifecycle/cold loading
(`.8.8`). The single portfolio conformance gate (`.8.5`; `.8.6` closed as
superseded) then covers LightGBM, LSTM, TCN, PatchTST, native LNN/LTC, Chronos,
and supported MLX before durable workflow execution and legacy deletion.
See [CAN Failure Prediction Review](./can-failure-prediction-review.md#8-recommended-sequencing)
and [CAN Agentic Orchestration](./can-agentic-orchestration.md#6-implementation-plan).

1. Freeze the versioned generation request, job, artifact, manifest, and recipe
	contracts, including schema and provenance requirements.
2. Build the compliant `dataset` runtime: durable job-state and queue ports, a
	memory test adapter, one persistent worker adapter, and canonical MCP tools.
3. Integrate pinned Agentic-Datasets v2 stage primitives through internal stage
	adapters, with immutable stage artifacts, schema gates, explicit fallback
	policy, and upstream signature/version canaries.
4. Refactor `machine_learning` to remove `DatasetGeneratorPort`, generation
	models, adapters, tools, resources, and prompts. Update its fine-tuning
	contract to consume a typed dataset artifact and selected training view.
5. Add the exact-pinned native `ChronosPipeline` lifecycle behind the existing
	ML port, including framework/PEFT serialization and passport-bound
	backbone/revision authority.
6. Only after Chronos, add AI-Fine-Tuning-backed MLX/PEFT execution adapters
	behind `FineTuningPort`; use MLX-native train/save/cold-load paths and evaluate
	licensing and maintenance before copying or vendoring upstream scripts.
7. Deliver a CAN vertical recipe only after the generic bundle contract is
	working: ingest, normalize, episode, enrich, label, validate, split, and
	materialize.

### 4.1 Implementation Status And Tracked Remaining Work

The following status records implementation state for this spec. Work begins from a corresponding Beads issue; newly discovered scope must first be tracked with a `discovered-from` issue. The repository-wide control-plane authority remains `.agents/steering/factory-protocol.md`.

| Area | Bead | Status | Completion boundary |
|---|---|---|---|
| Dataset brick ownership, public contracts, MCP tools | — | Complete | Async receipt, durable status, artifact lookup, and manifest resolution are covered by tests. |
| ML generation removal and typed dataset handoff | — | Complete | ML has no dataset-generation authority and consumes `DatasetTrainingInput`. |
| Agentic-Datasets v2 adapters and compatibility canaries | — | Complete | Four adapters, schema gates, checkpoint storage, canaries, and schema validation tests exist. |
| Recipe graph and worker-owned stage execution | — | Complete | A versioned recipe resolves to stages, executes them in order, persists validated stage checkpoints, and materializes requested views. |
| Durable recovery and idempotency | — | Complete | Storage-backed claim/restart, idempotency dedup, checkpoint resume, cancellation, and job state persistence all tested. |
| Quality, provenance, fallback, and tool-schema policy | — | Complete | 6 quality checks, fail-closed enforcement, fallback authorization, manifest records all digests/provenance/fallback. |
| Dataset-to-ML end-to-end handoff | — | Complete | The resolver boundary exists, the worker emits a verified backend-usable `training_uri`, and `machine_learning` validates the selected view against the manifest before training. |
| Dataset MCP tools callable | — | Complete | All 5 tools (submit, get_job, cancel, get_artifact, resolve_artifact) verified end-to-end through fastmcp. Pydantic deserialization fix applied. |
| the control-plane runtime control-plane workflow | `python-factory-dim.5` | Complete | End-to-end dataset→ML handoff validated with real dataset resolver integration. Tests: `test_dim5_e2e_handoff.py`. |
| MLX and AI-Fine-Tuning adapters | `python-factory-dim.7` | Complete | MLX backend routing (`mlx_lora` → `"mlx"`), LoRA config forwarding to subprocess, real metric parsing from stdout. Tests: `test_mlx_backend_routing.py`. |
| Production experiment tracker | `python-factory-dim.6` | Complete | MLflow selected as production tracker. Adapter bugs fixed (run context leak, wrong run end). 11 tests added. Config schema updated. |
| CAN failure-prediction recipe | `python-factory-dim.8` | Complete | Implemented as Rando (`.github/spec/Rando.md`). 7 epics closed: MF4 ingest, profiling, SDV synthesis, LightGBM training, inference bridge, agentic skills, pipeline wiring. |
| Dataset stage LLM routing | `python-factory-vw6` | Complete | Dataset stage recipes declare `backend` + optional `model`; `DatasetLLMConfigPort` resolves them through `llm_gateway` into an upstream `llm_config`; `llm_config` blobs are rejected in recipes. |
| Minimal Ollama e2e recipe fixture | `python-factory-2sq` | Complete | End-to-end recipe fixture validating full submit → poll → artifact → manifest lifecycle. Tests: `test_ollama_e2e.py`. |
| Dataset AgentSkills in `agent` brick | `python-factory-1y6` | Complete | `skills/dataset-generation/SKILL.md` with MCP tool guidance, chained examples, LLM routing docs. Wired into `the control-plane runtime-default`. |

### 4.2 Session Stop — 2026-07-15 (updated 2026-07-16)

All critical-path items through `dim.8` are complete. The generic dataset
bundle, durable recovery, quality/provenance enforcement, MCP tool surface,
`llm_gateway`-routed compatibility-stage configuration, MLflow tracker
selection, MLX backend routing, dataset→ML handoff, and CAN failure-prediction
recipe are complete and tested.

The parent epic (`python-factory-dim`) acceptance criteria are met. Follow-on
control-plane improvements are tracked separately under GitHub #708 and the
`python-factory-9mz1j` Beads epic.

## 5. Current Repository Surfaces To Reuse

| Surface | Use |
|---|---|
| [dataset brick interface](../../components/dataset/src/factory/dataset/interface.py) | Current async dispatch seam for dataset jobs |
| [dataset brick CLI worker](../../components/dataset/src/factory/dataset/cli.py) | Detached worker entrypoint |
| [machine_learning runtime](../../components/machine_learning/src/factory/machine_learning/runtime/runtime.py) | Experiment tracking and training lifecycle |
| [machine_learning models](../../components/machine_learning/src/factory/machine_learning/runtime/models.py) | Job, artifact, and checkpoint models |
| [machine_learning MCP tools](../../components/machine_learning/src/factory/machine_learning/mcp/finetuning_tools.py) | Fine-tuning tool surface to keep dataset generation out of |

## 6. Acceptance Criteria

The spec is complete when all of the following are true:

- A dataset job can be submitted and returns immediately with a `job_id`.
- A completed job resolves to a dataset URI.
- The dataset artifact and selected training view can be passed directly into
	`machine_learning` and are validated against its manifest.
- The worker backend is isolated from the request path.
- Dataset generation details are not hard-coded into the public ML interface.
- Every materialized bundle records immutable recipe/input/context/tool-schema
	digests, upstream stage revision, stage lineage, quality outcomes, and
	authorized fallback details.
- Upstream stage signature/version canaries and schema-validation tests fail
	before an incompatible or pass-through stage result is materialized.

## 7. References

### Kiro Source Spec

- [ml-dataset-generation requirements](../../.kiro/specs/ml-dataset-generation/requirements.md)
- [ml-dataset-generation design](../../.kiro/specs/ml-dataset-generation/design.md)
- [ml-dataset-generation plan](../../.kiro/specs/ml-dataset-generation/plan.md)

### Repository References

- [Dataset brick interface](../../components/dataset/src/factory/dataset/interface.py)
- [Dataset brick CLI worker](../../components/dataset/src/factory/dataset/cli.py)
- [Machine learning runtime](../../components/machine_learning/src/factory/machine_learning/runtime/runtime.py)
- [Machine learning models](../../components/machine_learning/src/factory/machine_learning/runtime/models.py)
- [Machine learning MCP fine-tuning tools](../../components/machine_learning/src/factory/machine_learning/mcp/finetuning_tools.py)
