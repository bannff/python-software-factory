# Dataset Brick

Durable asynchronous dataset generation with immutable, content-addressed artifact storage. The normative ownership split is defined in [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md).

## Control-Plane Boundary

An Agent Graph may research and revise a bounded immutable blueprint; Dataset validates allowlisted references and materializes that blueprint. Dataset may replay only bounded idempotent internal work over frozen inputs or checkpoints. Workflow owns cross-brick attempts, global budgets, retries, and stopping; Evals independently applies frozen criteria and returns immutable evidence-bound reports and typed deficiencies.

## Architecture

```
runtime/
├── contracts.py          # Pydantic models (request, job, artifact, manifest, quality)
├── ports.py              # Protocol interfaces (storage, executor, materializer, stage)
├── local.py              # Local durable store, recipe materializer, subprocess executor
├── recipe.py             # Recipe resolution and JSONL input loading
├── validation.py         # Upstream ConversationRecord schema validation
├── quality.py            # Quality gates (schema, completeness, duplicates, length)
└── adapters/
    ├── checkpoints.py       # Immutable write-once checkpoint store
    └── stage_canary.py      # Upstream signature/version verification
```

## MCP Surface

All 16 tools retain flat kwargs, enforce strict Dataset-local Pydantic v2 ingress, and return `ToolResult[OutputDTO]` envelopes; normal domain outcomes remain typed data.

| Tool | Type | Description |
|------|------|-------------|
| `dataset_validate_blueprint` | deterministic | Validate a frozen blueprint and its registered references without writes |
| `dataset_materialize_blueprint` | operational | Submit an exactly approved blueprint through the durable job path |
| `dataset_submit_generation` | operational | Submit a flat recipe request and return a durable job receipt |
| `dataset_publish_scenario_pack` | operational | Validate and immutably publish canonical ScenarioPack draft JSON |
| `dataset_get_scenario_pack` | deterministic | Verify and return a ScenarioPack through a typed reference |
| `dataset_get_job` | operational | Return durable job status |
| `dataset_get_artifact` | deterministic | Return an immutable artifact reference |
| `dataset_resolve_artifact` | deterministic | Resolve a dataset URI to its reproducibility manifest |
| `dataset_resolve_trajectory_zone` | deterministic | Resolve a digest-verified Evals trajectory landing-zone rowset (frozen v1 digest-only contract) |
| `dataset_materialize_can_training_bundle` | operational | Materialize an immutable, ML-ready CAN causal training bundle |
| `dataset_cancel_job` | operational | Cancel a non-terminal job |
| `can_pipeline_overview` | deterministic | Describe the Dataset-owned CAN materialization terminal |
| `dataset_query_dbc_catalog` | deterministic | List approved DBC metadata and local verification status |
| `dataset_resolve_dbc_candidate` | deterministic | Rank or verify an approved DBC candidate |
| `dataset_list_failure_patterns` | deterministic | List immutable approved failure-pattern references |
| `dataset_inspect_failure_pattern` | deterministic | Inspect one approved failure pattern and its evidence |
| `dataset_project_can_graph` | operational | Project canonical CAN frames through named Graph MCP mutations |

**Resources:** `dataset://schemas/blueprint`, `dataset://schemas/generation-request`, `dataset://schemas/job`, `dataset://schemas/artifact`, `dataset://schemas/scenario-pack`, `dataset://schemas/can-intelligence`, `dataset://dbc/catalog`, `dataset://can/failure-patterns`, `dataset://docs/can-intelligence-scope`

**Prompt:** `prepare_dataset_generation` — walkthrough for the submit/poll/resolve workflow.

Cross-brick consumers invoke these tools through the project-level `tool_invoker`; they do not import the Dataset interface or runtime. `storage_root` must be identical across validation, materialization, status, artifact, and resolution calls so one pipeline run observes the same caller-owned store.

## DatasetBlueprint Contract

`DatasetBlueprint` is frozen and rejects extra fields. It carries typed recipe, ordered stage, output-schema, ScenarioPack evidence, capability, and opaque Evals quality-policy references. It cannot carry executable validators, evaluators, imports, callables, scripts, commands, or acceptance/promotion controls. Stage order is semantic; evidence and capability references are unique and set-canonical.

The first fail-closed, non-security registry entry accepts exactly:

- recipe `scenario-generate` version `1`, resolving to `recipe://local/scenario-generate@1`
- one ordered stage: `scenario_generate` version `scenario-generate-1.0`
- output schema `generic` version `1.0`
- capability `deterministic-template` version `1.0`
- exactly one `ScenarioPack` version `1` evidence reference with its immutable artifact ref

Blueprint and approval digests are SHA-256 over compact, key-sorted UTF-8 JSON (`ensure_ascii=false`, `allow_nan=false`). The digest therefore binds recipe, stage order, schema, evidence, capabilities, policy, seed, and requested views.

Policy and approval authorities are config seams pending their owning sibling bricks. Both default to empty registries and fail closed:

```bash
export DATASET_QUALITY_POLICY_REFS_JSON='[{"id":"scenario-quality","revision":"1","digest":"<policy-sha256>"}]'
export DATASET_HUMAN_APPROVALS_JSON='[{"id":"approval-41","revision":"1","blueprint_digest":"<blueprint-sha256>","quality_policy":{"id":"scenario-quality","revision":"1","digest":"<policy-sha256>"}}]'
```

Pass `approval-41`, revision `1`, and the SHA-256 digest of that canonical approval record to `dataset_materialize_blueprint`; there is no boolean approval. Dataset persists an immutable approval binding containing that exact approval ref, approved blueprint digest, and exact opaque policy ref in both `DatasetGenerationRequest` and `DatasetManifest`. Both the public Python `dataset_submit_generation` entry point and its flat legacy MCP tool reject the registered scenario route unless both blueprint and approval bindings are present; unrelated recipes remain compatible.

The named MCP acceptance path is:

```text
dataset_publish_scenario_pack → dataset_validate_blueprint
→ dataset_materialize_blueprint → dataset_get_job (poll)
→ dataset_get_artifact → dataset_resolve_artifact
```

Validation is write-free. Blueprint publication is linearizable per identity/version under a permanent no-follow local lock: the winner writes content and the identity ref, while a divergent loser returns conflict without orphan content. Materialization uses a blueprint-digest-derived idempotency key; exact replay returns the same job/artifact, while divergent key reuse conflicts before downstream effects. Before submission and again before detached-worker recipe, checkpoint, stage, artifact, or manifest effects, Dataset reloads the exact blueprint, re-requires the configured opaque policy ref, revalidates the configured approval ref, and compares every request field. The manifest records the exact approval binding plus blueprint, policy, source, recipe, ordered stages, schema, and capability lineage.

This slice is only Dataset's human-gated materialization seam; it is not a full generate → evaluate → revise loop. Bead `python-factory-9mz1j.3` owns policy semantics, evaluator execution, evidence-bound reports, typed deficiencies, acceptance, and promotion. Bead `python-factory-9mz1j.4` owns durable attempts, global budgets, retries, cancellation, recovery, stopping, and correction rounds. Bead `python-factory-9mz1j.2` remains open because this Dataset-only slice does not satisfy its full generate → evaluate → revise acceptance criterion.

## Job Lifecycle

```
submit → queued → running → completed (with artifact)
                         → failed (on error or cancellation)
```

Submission is idempotent via `idempotency_key` + request fingerprint. The worker runs as a detached subprocess (`start_new_session=True`) and resumes from immutable stage checkpoints on restart.

## Recipe Format

A recipe is a versioned declarative list of retained deterministic stage invocations. Dataset rejects every other stage at admission before it creates a durable job:

```json
{
  "version": "my-recipe-v1",
  "stages": [
    {"name": "local-validate", "config": {}}
  ]
}
```

Built-in: `recipe://local/pass-through@1` (passthrough for legacy compatibility) and `recipe://local/scenario-generate@1` (typed `scenario_pack` input role, deterministic complete outcome-conditioned episodes).

ScenarioPack publications are canonical SHA-256 artifacts indexed by identity/version. Identical publication is idempotent; changed content under the same identity/version returns a typed conflict. Scenario generation persists the verified pack ref, sources, assumptions, generator/version, root seed, and per-episode identity/digest/scenario/outcome/ordinal/split-group through checkpoints and the final manifest.

## Quality Gates

Materialization runs 6 quality checks on output records:

| Check | Behavior |
|-------|----------|
| `schema` | Validates against upstream `ConversationRecord` |
| `record_count` | Informational — reports count |
| `empty_messages` | **Blocks** if any record has empty messages or empty content |
| `role_coverage` | **Blocks** if no "user" or no "assistant" role present |
| `duplicate_detection` | Warns on content-hash duplicates (non-fatal) |
| `max_message_length` | **Blocks** if any message exceeds 100k characters |

Quality results are attached to every stage checkpoint and the final manifest.

## Multi-View Support

Requests can specify up to 10 named views (e.g. `["sft", "dpo", "cpt"]`). Each view is materialized as a separate `view-{name}-{digest}.jsonl` file. The first view is the default `training_uri` for ML consumers.

## Content-Addressed Storage

All artifacts are immutable and digest-verified:
- Dataset files: `dataset-{sha256}.jsonl` with `.ref.json` sidecar
- Manifests: `manifest-{sha256}.json`
- Checkpoints: `stage-{name}.checkpoint.json`
- All files written with `chmod 0o444`

## Execution Policy

- `fail_closed: true` — materialization rejected if any check fails
- `retry_from_checkpoint_only: true` — retries reuse frozen immutable context
- `allowed_fallbacks` — explicit backend allowlist for authorized fallbacks

## Local Dev

Use the the control-plane runtime power so calls cross the same MCP boundary as deployed consumers:

```python
kiroPowers(
    action="use",
    powerName="the control-plane runtime",
    serverName="the control-plane runtime",
    toolName="call_brick_tool",
    arguments={
        "brick_name": "dataset",
        "tool_name": "dataset_submit_generation",
        "arguments": "{\"recipe_uri\":\"recipe://local/pass-through@1\",\"recipe_digest\":\"<sha256>\",\"context_snapshot_uri\":\"file:///tmp/context.json\",\"context_snapshot_digest\":\"<sha256>\",\"tool_schema_snapshot_uri\":\"file:///tmp/tools.json\",\"tool_schema_snapshot_digest\":\"<sha256>\",\"storage_root\":\"./.dataset_store\"}",
    },
)
```

Poll `dataset_get_job` and fetch `dataset_get_artifact` with the returned `job_id` and the same `storage_root`. The worker writes logs to `jobs/{job_id}.log` beneath that root.

## CAN Bus Support

The dataset brick supports CAN bus telemetry analysis via built-in recipe URIs:

| Recipe URI | Stage | Purpose |
|---|---|---|
| `recipe://local/can-ingest@1` | Ingest | Parse MF4 files, decode with DBC, extract canonical frames |
| `recipe://local/can-profile@1` | Profile | Signal boundaries, correlations, delta thresholds, frame rates |
| `recipe://local/can-synthesize@1` | Synthesize | SDV GaussianCopula synthetic generation + failure injection |
| `recipe://local/can-pipeline@1` | Full | All 3 stages chained |

MF4 paths are supplied as `input_artifact_uris` with matching `input_artifact_digests`; optional `input_artifact_roles` provides positional typed routing. DBC and other stage configuration ride in the context snapshot.

### CAN fixed-grid timing plane

Set `emit_timespans=true` on `can_window` when a downstream native model needs
an explicit timing plane. The stage emits one elapsed value per represented
observation cell: every value is exactly one `grid_ns`, and the values sum to
the observation cutoff. Timing never reads the label horizon. Multiple strictly
increasing frames may still land in one cell (the last frame supplies feature
values), but duplicate or regressing source timestamps fail closed per CAN ID
before timing emission. When timing is not requested, the existing window output
remains timing-omission compatible.

Workflow is the canonical controller for a durable cross-brick CAN attempt: it journals state and owns global budgets, retries, cancellation, recovery, stopping, and terminal reasons. The Machine Learning `can_run_full_pipeline` tool is the current capability-local entry point for one bounded pipeline invocation. It calls `dataset_submit_generation`, `dataset_get_job`, and `dataset_get_artifact` by flat MCP tool name through `tool_invoker`, passing one per-run `storage_root` to every call. This preserves the brick boundary and keeps each stage independently observable and resumable without granting Machine Learning durable control-plane ownership.
