# CAN Frame Analysis and Variation Synthesis Spec

This spec depends on the ML dataset-generation working copy:

- [ML Dataset Generation Spec](./ml-dataset-generation.md)

This is the canonical offline home for CAN frame analysis and protocol-valid variation synthesis. It is distinct from [CAN Failure Prediction and Agentic Dataset Spec](./can-failure-prediction.md). The durable dataset-job and artifact-URI lifecycle stays with ml-dataset-generation; this spec only defines the offline analysis, synthesis, and handoff contract for the frozen dataset input.

## 1. Purpose

This spec defines how raw Classical CAN and CAN FD captures are analyzed offline, expanded into bounded protocol-valid sequence/value variations, and synthesized into a frozen dataset artifact for downstream SLM/ML training.

It does not own durable dataset-job or artifact-URI lifecycle, labels, taxonomy, failure prediction, or model evaluation.

It is intentionally distinct from CAN failure prediction. It does not define failure labels, taxonomy design, label generation, or model evaluation.

## 2. Scope

### In Scope

- Raw Classical CAN and CAN FD frame analysis.
- Offline normalization of frame records for synthesis.
- Enumeration of viable protocol-valid sequence/value variation families.
- Visualization of variation families, coverage, and payload/sequence distributions.
- Large-scale frozen dataset synthesis for downstream SLM/ML training.
- Provenance and reproducibility metadata for the synthesized corpus.

### Out of Scope

- Live-bus transmission, ECU writes, actuation, vehicle-state mutation, or control-loop behavior.
- Labels, taxonomy ownership, failure prediction, or model evaluation.
- Real-time decisioning or online adaptation.
- Durable dataset-job handling or artifact-URI lifecycle management.

## 3. Canonical Contract

### 3.1 Canonical Frame Record

Each raw frame should be representable as a record with at least:

| Field | Purpose |
|---|---|
| `timestamp_ns` | Temporal ordering and windowing |
| `vehicle_id` | Optional asset identity |
| `session_id` / `trip_id` | Offline capture boundary |
| `bus_name` / `channel` | Which CAN segment produced the frame |
| `arbitration_id` | CAN identifier |
| `is_extended` | Standard vs extended frame |
| `is_fd` | Classical CAN vs CAN FD |
| `dlc` | Declared data length |
| `data_bytes` | Raw payload bytes |
| `frame_type` | Data, error, remote, overload, or similar |
| `error_state` | Optional bus state if known |
| `capture_source` | Logger, gateway, probe, or archive source |
| `provenance` | Source artifact and ingest metadata |

### 3.2 Variation Inventory Record

Each synthesized variation should be traceable as a record with at least:

| Field | Purpose |
|---|---|
| `variation_id` | Stable identifier for the variant |
| `source_frame_ref` | Frame or window that informed the variant |
| `variation_family` | Sequence, value, or combined family |
| `protocol_valid` | Whether the variant stays within CAN/CAN FD legality |
| `variation_summary` | Brief human-readable description |
| `deterministic_seed` | Reproducible synthesis input |
| `provenance` | Source and recipe digests |

### 3.3 Frozen Corpus Descriptor

The frozen dataset is treated as a downstream training input, not as a new lifecycle owner. The analysis layer may describe the corpus with digest, family counts, and recipe provenance, but the durable materialization and resolvable artifact contract remain defined by ml-dataset-generation.

## 4. Workflow

### 4.1 Ingest

Load raw CAN and CAN FD captures, plus optional capture metadata, into the offline analysis pipeline.

### 4.2 Normalize

Convert raw inputs into canonical frame records and check them for structural completeness.

### 4.3 Analyze

Inspect the frame corpus for protocol shape, field distribution, sequence context, and reusable variation opportunities.

### 4.4 Enumerate Variations

Derive bounded, protocol-valid variation families that preserve frame legality and remain suitable for offline synthesis.

### 4.5 Synthesize

Assemble a large frozen dataset corpus from the analyzed frames and enumerated variations.

### 4.6 Visualize

Render coverage plots, sequence/value distribution plots, and family summaries so the viable variation space is inspectable before export.

### 4.7 Freeze and Hand Off

Produce the frozen corpus for downstream SLM/ML training and hand it to the dataset-generation contract as the dataset input reference.

## 5. Acceptance Criteria

The spec is complete when all of the following are true:

- Raw Classical CAN and CAN FD frame captures can be analyzed offline.
- The pipeline can enumerate more than one protocol-valid sequence/value variation family from the same corpus.
- The pipeline can render plots or summaries that describe the viable variation space.
- The synthesis step produces a large frozen dataset corpus without live-bus transmission, ECU writes, actuation, or vehicle-state mutation.
- The frozen corpus can be handed to SLM/ML training as a dataset input through the existing dataset-generation contract.
- The spec remains separate from failure prediction, taxonomy, label generation, and model evaluation.
- The spec does not define a second durable dataset-job or artifact-URI lifecycle.

## 6. References

- [ML Dataset Generation Spec](./ml-dataset-generation.md)
- [CAN Failure Prediction and Agentic Dataset Spec](./can-failure-prediction.md)
