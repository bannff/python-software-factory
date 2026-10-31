---
name: dataset-generation
description: Asynchronous dataset generation, validation, and ML handoff via the dataset and machine_learning MCP bricks.
---
# Dataset Generation

You are composing and submitting dataset generation jobs. The `dataset` brick owns async creation, validation, versioning, and materialization of immutable dataset bundles. The `machine_learning` brick owns fine-tuning and experiment tracking.

## Dataset MCP Tools

### Submit a generation job (immediate receipt)

```
dataset_submit_generation(request={
  "recipe_uri": "recipe://local/pass-through@1",
  "recipe_digest": "<sha256-hex>",
  "input_artifacts": [],
  "context_snapshot": {"uri": "snapshot://...", "digest": "<sha256-hex>"},
  "tool_schema_snapshot": {"uri": "schema://...", "digest": "<sha256-hex>", "allowed_tools": []},
  "requested_views": ["default"],
  "idempotency_key": "optional-dedup-key"
})
```

Returns: `{job_id, status: "queued", submitted_at}`. The job runs in a background worker.

### Poll job status

```
dataset_get_job(job_id="<job_id>")
```

Returns: `{job_id, status, submitted_at, started_at, completed_at, artifact, error}`. Status is one of: `queued`, `running`, `completed`, `failed`.

### Cancel a running job

```
dataset_cancel_job(job_id="<job_id>", reason="cancelled")
```

### Get immutable artifact reference (after completion)

```
dataset_get_artifact(job_id="<job_id>")
```

Returns: `{dataset_uri, manifest_uri, digest, schema_version, available_views, training_uri}`.

### Resolve a dataset URI to its manifest

```
dataset_resolve_artifact(dataset_uri="<dataset_uri>")
```

Returns full reproducibility manifest: recipe digest, input artifacts, quality results, provenance, stage lineage, fallback records.

## LLM Routing

Dataset stage recipes route LLM calls through `llm_gateway`. Declare a `backend` name and optional `model`:

```
backend: "ollama"        # or "bedrock", "openai", "anthropic"
model: "llama3.2"        # optional override
```

Do NOT pass raw `llm_config` blobs in recipe configs. Routing must go through `llm_gateway` for provenance, fallback authorization, and cost observability.

## Chained Tool Examples

### Chain 1: Submit a minimal recipe and poll to completion

```
# Step 1: Submit the job
dataset_submit_generation(request={
  "recipe_uri": "recipe://local/pass-through@1",
  "recipe_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "input_artifacts": [],
  "context_snapshot": {"uri": "snapshot://local/compat@1", "digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
  "tool_schema_snapshot": {"uri": "schema://local/empty@1", "digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "allowed_tools": []},
  "requested_views": ["default"]
})

# Step 2: Poll until completed
dataset_get_job(job_id="<job_id_from_step_1>")

# Step 3: Get the artifact
dataset_get_artifact(job_id="<job_id>")

# Step 4: Resolve the manifest
dataset_resolve_artifact(dataset_uri="<dataset_uri_from_step_3>")
```

### Chain 2: Generate a dataset and hand off to ML fine-tuning

```
# Step 1-4: Generate and resolve (same as Chain 1)

# Step 5: Construct ML training input from the artifact
# The artifact provides dataset_uri, manifest_uri, digest, and available_views.
# Pick a view (e.g., "sft" for supervised fine-tuning) and build the input:
{
  "dataset_uri": "<artifact.dataset_uri>",
  "manifest_uri": "<artifact.manifest_uri>",
  "dataset_digest": "<artifact.digest>",
  "view_name": "sft",
  "view_schema_version": "<manifest.view_schema_versions.sft>"
}

# Step 6: Submit fine-tuning to the ML brick
# Use the ML brick's fine-tuning tools with the training input above.
# The ML brick validates the view against the manifest before training.
```

### Chain 3: Ollama local e2e (no heavy backends)

```
# Step 1: Submit with Ollama as the LLM backend
dataset_submit_generation(request={
  "recipe_uri": "recipe://local/ollama-e2e@1",
  "recipe_digest": "<sha256>",
  "input_artifacts": [],
  "context_snapshot": {"uri": "snapshot://local/ollama@1", "digest": "<sha256>"},
  "tool_schema_snapshot": {"uri": "schema://local/empty@1", "digest": "<sha256>", "allowed_tools": []},
  "requested_views": ["default"]
})

# Step 2: Poll — the worker routes LLM calls through llm_gateway with backend="ollama"
dataset_get_job(job_id="<job_id>")

# Step 3: On completion, verify the artifact
dataset_get_artifact(job_id="<job_id>")
dataset_resolve_artifact(dataset_uri="<dataset_uri>")
```

## Key Rules

- `dataset` owns generation; `machine_learning` consumes artifacts by URI.
- Recipes must not pass raw `llm_config` — route through `llm_gateway`.
- Every completed bundle records immutable digests, provenance, quality results, and fallback records.
- `dataset_cancel_job` transitions non-terminal jobs to `failed`.
- Use `idempotency_key` to safely retry submissions.
- The `training_uri` on the artifact is backend-usable and passed directly to ML.
