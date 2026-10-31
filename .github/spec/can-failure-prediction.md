# CAN Failure Prediction and Agentic Dataset Spec

This spec depends on the ML dataset-generation working copy:

- [ML Dataset Generation Spec](./ml-dataset-generation.md)
- [CAN Frame Analysis and Variation Synthesis Spec](./can-frame-analysis-variation-synthesis.md) for the sibling offline CAN analysis and protocol-valid variation synthesis workflow.

## 1. Purpose

This spec defines how to turn CAN frame data into agentic datasets and then train models that predict vehicle failures.

The first implementation should live in the control-plane runtime, not as a separate standalone project, but only after the ML dataset-generation working copy is in place. the control-plane runtime already has the richer substrate in this workspace: agent orchestration, graph, memory, events, storage, dataset, evals, and machine_learning support. A separate project under `projects/` should only be introduced later if the product needs its own deployment boundary, runtime isolation, or customer-facing packaging.

The intended workflow is:

1. Ingest raw CAN logs and optional DBC files.
2. Normalize logs into labeled episodes and windows.
3. Use taxonomy-aware graph and memory retrieval to help agents propose or validate labels.
4. Materialize a dataset artifact as a URI-addressable output.
5. Train and evaluate models from that dataset.

## 2. Why Taxonomy Helps

Yes, the spec is materially better with taxonomy.

CAN frame data is transport-level telemetry, not a semantic label space. The identifier, DLC, payload, and error state tell you what happened on the bus, but not what it means for the vehicle. A taxonomy gives the system a shared semantic layer for:

- Vehicles, ECUs, trips, buses, and firmware versions.
- Frame-level behavior, signal-level features, and error events.
- Failure modes, maintenance events, repair outcomes, and DTCs.
- Label provenance and confidence.

That matters because the goal is not just prediction. The goal is agentic dataset creation: agents should be able to inspect CAN traces, join them to domain context, propose labels, compare with prior cases, and emit training-ready artifacts with provenance.

### 2.1 Recommended CAN Taxonomy Shape

Use the graph taxonomy registry to define a CAN domain extension, for example `can_failure`.

Suggested node types:

- `Vehicle`
- `Trip`
- `CANBus`
- `ECU`
- `Frame`
- `Signal`
- `DBCVersion`
- `DTC`
- `FailureMode`
- `MaintenanceEvent`

Suggested relationships:

- `HAS_ECU`
- `PART_OF_TRIP`
- `EMITS_FRAME`
- `DECODES_TO`
- `CORRELATES_WITH`
- `PRECEDES_FAILURE`
- `REPAIRED_BY`
- `ANNOTATED_AS`

### 2.2 Why This Improves Prediction

Taxonomy helps in four concrete ways:

1. It supports weak supervision when hard labels are sparse.
2. It lets agents reuse prior failure episodes, not just raw telemetry.
3. It makes labels explainable and reproducible.
4. It allows a single dataset to support multiple targets, such as failure-within-horizon, failure class, and time-to-failure.

## 3. Scope

### In Scope

- Raw Classical CAN and CAN FD frame data.
- Optional DBC decoding.
- Multi-target failure prediction.
- Agentic dataset generation and label refinement.
- Offline evaluation and training.

### Out of Scope For v1

- Direct vehicle actuation.
- Physical-layer simulation or bus emulation.
- Firmware flashing or live ECU control.
- Real-time safety-critical decisions.

## 4. Data Contract

The canonical input should be a raw frame event. If DBC is available, decoded signals are enrichment, not the source of truth.

### 4.1 Canonical Frame Record

Each raw CAN event should be representable as a record with at least:

| Field | Purpose |
|---|---|
| `timestamp_ns` | Event ordering and latency analysis |
| `vehicle_id` | Fleet or asset identity |
| `trip_id` / `session_id` | Episode boundary |
| `bus_name` / `channel` | Which bus the frame came from |
| `arbitration_id` | CAN identifier |
| `is_extended` | Standard or extended frame |
| `is_fd` | Classical CAN vs CAN FD |
| `dlc` | Frame length code |
| `data_bytes` | Raw payload bytes |
| `frame_type` | Data, error, remote, overload, etc. |
| `error_state` | Normal, error active, error passive, bus off, if known |
| `ack_seen` | Whether the transmitter observed ACK behavior |
| `source_ecu` | Optional origin ECU |
| `capture_source` | Logger, gateway, vehicle probe, or simulator |

### 4.2 Episode Record

The spec should define an episode as a contiguous operational slice, usually a drive, ignition cycle, or maintenance window.

Suggested fields:

- `episode_id`
- `vehicle_id`
- `start_ts`
- `end_ts`
- `odometer_km` if available
- `dbc_version` if applicable
- `label_source`
- `label_confidence`
- `taxonomy_version`

### 4.3 Label Record

The system should support multiple targets per episode or per time window.

Recommended label fields:

- `target_name`
- `target_value`
- `target_type` (`binary`, `multi_class`, `regression`)
- `prediction_horizon_minutes`
- `label_source`
- `provenance`
- `confidence`
- `taxonomy_node_id` when a taxonomy concept anchors the label

### 4.4 Split Policy

The dataset spec should require:

- Chronological splits.
- Vehicle-separated splits.
- Leakage checks across trips, sessions, and maintenance windows.
- A frozen taxonomy snapshot for each dataset version.

## 5. Artifact Layout

The dataset URI produced by the `dataset` brick should point at a self-contained artifact bundle, not just a single file.

Recommended contents:

- `frames.parquet` or `frames.jsonl`
- `episodes.parquet` or `episodes.jsonl`
- `labels.parquet` or `labels.jsonl`
- `splits.json`
- `manifest.json`
- `taxonomy.json`
- `provenance.json`

This makes the dataset reproducible, inspectable, and safe to hand to `machine_learning`, `evals`, or any RAG-like consumer.

## 6. the control-plane runtime Surfaces To Reuse

the control-plane runtime already contains the most useful bricks for this workflow.

| Brick | Use in this spec | Relevant files |
|---|---|---|
| `dataset` | Async job dispatch and status tracking for dataset creation | [interface.py](../../components/dataset/src/factory/dataset/interface.py), [cli.py](../../components/dataset/src/factory/dataset/cli.py) |
| `graph` | Taxonomy registry, domain schema, graph-backed context | [taxonomy_registry.py](../../components/graph/src/factory/graph/runtime/taxonomy_registry.py), [resources.py](../../components/graph/src/factory/graph/mcp/resources.py), [docs.py](../../components/graph/src/factory/graph/mcp/docs.py) |
| `games` | Domain-aware RL loop and label/reward plumbing | [operational.py](../../components/games/src/factory/games/mcp/operational.py) |
| `events` | Reward, feedback, and provenance flow | [learning_contracts.py](../../components/events/src/factory/events/runtime/learning_contracts.py), [rewards_handler.py](../../components/events/src/factory/events/runtime/rewards_handler.py) |
| `memory` | Retrieval of prior episodes, failure patterns, and annotations | [interface.py](../../components/memory/src/factory/memory/interface.py), [runtime.py](../../components/memory/src/factory/memory/runtime/runtime.py) |
| `agent` | CAN analyst persona and skills for data inspection and label QA | [defaults.py](../../components/agent/src/factory/agent/registry/defaults.py), [skills/](../../components/agent/src/factory/agent/skills/) |
| `machine_learning` | Tracking, training, checkpointing, and model lifecycle | [runtime.py](../../components/machine_learning/src/factory/machine_learning/runtime/runtime.py), [models.py](../../components/machine_learning/src/factory/machine_learning/runtime/models.py), [finetuning_tools.py](../../components/machine_learning/src/factory/machine_learning/mcp/finetuning_tools.py) |
| `storage` | Raw log and artifact persistence | [interface.py](../../components/storage/src/factory/storage/interface.py), [blob_local.py](../../components/storage/src/factory/storage/runtime/adapters/blob_local.py) |
| `evals` | Offline scoring, calibration, and experiment persistence | [runtime.py](../../components/evals/src/factory/evals/runtime/runtime.py), [_persist_score.py](../../components/evals/src/factory/evals/runtime/_persist_score.py) |

## 7. Agentic Dataset Workflow

The workflow should be agentic, not just batch ETL.

### 7.1 Ingest

Bring CAN logs, DBC files, and maintenance outcomes into storage.

### 7.2 Normalize

Convert frames into canonical records and episode windows.

### 7.3 Enrich

Use graph taxonomy, prior failures, and memory recall to add contextual fields.

### 7.4 Label

Let agents propose or validate labels using taxonomy-aware reasoning:

- failure within horizon
- failure mode class
- anomaly score
- DTC correlation
- time-to-failure regression target

### 7.5 Validate

Run label quality checks, leakage checks, and split checks before export.

### 7.6 Materialize

The `dataset` brick should return a `job_id` immediately, then eventually expose a `dataset_uri` for downstream consumers.

### 7.7 Train

Feed the dataset URI into `machine_learning` for experiment tracking and model training.

## 8. Modeling Path

Do not start with a complex model.

Recommended progression:

1. Baseline heuristic rules.
2. Classical tabular model on windowed features.
3. Sequence model on frame windows.
4. Taxonomy-aware model that mixes raw frames with graph and memory features.

### 8.1 Suggested Targets

The spec should support multiple outputs, not just one:

- `failure_within_horizon`
- `failure_mode`
- `time_to_failure`
- `anomaly_score`

### 8.2 Suggested Metrics

- AUROC
- AUPRC
- calibration / Brier score
- lead-time accuracy
- false alarm rate
- episode-level recall

## 9. the control-plane runtime Implementation Notes

The existing the control-plane runtime stack can enhance the predictions in ways a standalone ML project cannot:

- The graph brick gives you a place to model vehicle and ECU relationships.
- The taxonomy registry gives you a stable CAN domain ontology.
- The memory brick lets agents retrieve similar failure episodes and prior judgments.
- The events brick preserves provenance for label creation and feedback.
- The games brick provides a reusable reward and improvement loop for agentic labeling workflows.
- The dataset brick gives you the async boundary needed for long-running generation jobs.
- The machine_learning brick already owns training and evaluation lifecycle primitives.

## 10. Implementation Phases

### Phase 0: Finish The ML Baseline

Work from [ML Dataset Generation Spec](./ml-dataset-generation.md) first.

### Phase 1: Lock The CAN Data Contract

Define canonical frame, episode, label, and split records.

### Phase 2: Add CAN Taxonomy

Register a `can_failure` taxonomy extension in the graph registry and expose it through `graph://schemas/taxonomy/{domain}`.

### Phase 3: Build Agentic Dataset Jobs

Use the dataset brick to create async jobs that generate training-ready artifacts.

### Phase 4: Wire Agentic Labeling

Add a CAN analyst persona and use graph/memory/events/games to propose and validate labels.

### Phase 5: Train And Evaluate

Use `machine_learning` to train models against dataset URIs and compare against a frozen baseline.

## 11. Acceptance Criteria

The implementation is ready when all of the following are true:

- A CAN dataset job can be submitted and returns immediately with a `job_id`.
- The job eventually resolves to a durable `dataset_uri`.
- The dataset bundle includes raw frames, labels, splits, taxonomy snapshot, and provenance.
- A CAN taxonomy extension exists and can be resolved through the graph resource API.
- An agent can retrieve prior episodes or labels through memory and graph context.
- `machine_learning` can train from the dataset URI without knowing how the dataset was generated.
- Offline evaluation reports baseline and model metrics on a held-out fleet slice.

## 12. Notes From The Existing Kiro Spec

The current Kiro spec is already pointing in the right direction:

- Dataset creation belongs in `components/dataset/`, not `machine_learning`.
- The dataset job must be non-blocking and async.
- Domain-specific stage logic must stay inside the dataset worker layer.
- `machine_learning` should consume dataset URIs, not own dataset generation.

This GitHub spec is the working copy that should be used for implementation work.

## 13. References

### Repository References

- [the control-plane runtime README](../../projects/the control-plane project/README.md)
- [the control-plane runtime entrypoint](../../projects/the control-plane project/main.py)
- [the control-plane runtime ML job example](../../projects/the control-plane project/run_ml_job.py)
- [Dataset brick interface](../../components/dataset/src/factory/dataset/interface.py)
- [Dataset brick CLI worker](../../components/dataset/src/factory/dataset/cli.py)
- [Graph taxonomy registry](../../components/graph/src/factory/graph/runtime/taxonomy_registry.py)
- [Graph taxonomy resource wiring](../../components/graph/src/factory/graph/mcp/resources.py)
- [Games RL surface](../../components/games/src/factory/games/mcp/operational.py)
- [Events learning contract](../../components/events/src/factory/events/runtime/learning_contracts.py)
- [Memory public interface](../../components/memory/src/factory/memory/interface.py)
- [Machine learning runtime](../../components/machine_learning/src/factory/machine_learning/runtime/runtime.py)
- [Machine learning models](../../components/machine_learning/src/factory/machine_learning/runtime/models.py)
- [Machine learning MCP fine-tuning tools](../../components/machine_learning/src/factory/machine_learning/mcp/finetuning_tools.py)
- [Storage public interface](../../components/storage/src/factory/storage/interface.py)
- [Evals score persistence](../../components/evals/src/factory/evals/runtime/_persist_score.py)

### Kiro Source Spec

- [ml-dataset-generation requirements](../../.kiro/specs/ml-dataset-generation/requirements.md)
- [ml-dataset-generation design](../../.kiro/specs/ml-dataset-generation/design.md)
- [ml-dataset-generation plan](../../.kiro/specs/ml-dataset-generation/plan.md)

### External CAN References

- [CAN bus](https://en.wikipedia.org/wiki/CAN_bus)
- [CAN bus DBC files section](https://en.wikipedia.org/wiki/CAN_bus#DBC_(CAN_database_files))
- [Kvaser CAN Bus Protocol Tutorial](https://www.kvaser.com/can-protocol-tutorial/)
- [ISO 11898-1](https://www.iso.org/standard/63648.html)
