# Recipe: ML Page — UI Data Flow

End-to-end data flow from the machine_learning brick MCP tools through the Next.js renderer to the the control-plane runtime dashboard.

## Bricks Used
- `machine_learning` — Fine-tuning jobs, experiment tracking

## Scenario

Create and start a fine-tuning job, then verify the rendering pipeline: job list → method filter pills → status dots → loss values → detail tab job info → experiments tab.

## Prerequisites

- the control-plane runtime gateway running (MCP aggregator available)
- No AWS required (memory backend)

## Known Bug: Tool Name Prefix Mismatch

The brick is named `machine_learning` but tools use the `ml_` prefix (e.g. `ml_get_views`). The gateway may prefix tools with the full brick name (`machine_learning_ml_get_views`). The frontend must call `ml_get_views` — verify the gateway resolves this correctly. If the view tool 404s, check the MCP aggregator's tool registry for the actual registered name.

## Steps

### Step 1: Create a Fine-Tuning Job

```python
job = ml_create_finetuning_job(
    method="lora",
    base_model="meta-llama/Llama-3.2-1B",
    dataset_uri="artifact://security-qa-v1",
    manifest_uri="artifact://security-qa-v1/manifest",
    dataset_digest="<sha256>",
    view_name="sft",
    view_schema_version="1.0",
    batch_size=4,
    learning_rate=1e-4,
    lora_rank=8,
    lora_alpha=16,
)
# → {"id": "ft-...", "status": "pending", "method": "lora"}
job_id = job["id"]
```

### Step 2: Start the Job

```python
started = ml_start_finetuning_job(job_id=job_id)
# → {"id": "ft-...", "status": "completed", "metrics": {"loss": 0.42}, "checkpoints": 1}
```

### Step 3: Create an Experiment for Tracking

```python
exp = tracking_create_experiment(name="lora-sweep", description="LoRA rank sweep")
run = tracking_start_run(experiment_id=exp["id"], name="rank-8")
tracking_log_params(run_id=run["id"], params={"rank": 8, "alpha": 16})
tracking_log_metrics(run_id=run["id"], metrics={"loss": 0.42, "accuracy": 0.91}, step=100)
tracking_end_run(run_id=run["id"], status="completed")
```

### Step 4: View Definition Drives the Renderer

```python
views = ml_get_views()
# Returns a single "ml-finetuning" view with one item_list component
```

The view's `props` declare the rendering contract:

```typescript
// renderers-item-list.tsx reads these props:
{
  data_tool: "ml_list_finetuning_jobs",
  item_key: "id",
  filters: {
    field: "method",
    values: ["lora", "adalora", "ia3", "prefix_tuning", "full", "mlx_lora"],
    colors: { lora: "violet", adalora: "purple", ia3: "blue", ... },
  },
  item_layout: {
    status_dot: { value_path: "$.status", states: { completed: "emerald", failed: "red", running: "blue", pending: "yellow" } },
    title: "$.base_model",
    badge: { field: "method", color_map: "filters.colors" },  // "lora" in violet
    value: { path: "$.loss", format: "number" },
    trend: { direction: "$.trend", change_pct: "$.loss_change_pct" },
  },
  detail: {
    tabs: [
      { id: "details", label: "Job Details", tool: "ml_get_finetuning_job", args: { job_id: "$.id" }, render_as: "detail" },
      { id: "experiments", label: "Experiments", tool: "tracking_list_experiments", args: {}, render_as: "list" },
    ],
  }
}
```

### Step 5: Frontend Rendering Pipeline

```typescript
// 1. BrickViewRenderer calls ml_get_views via useToolData
const { data } = useToolData("ml_get_views");
// → normalizeNodes() → ComponentTree → ItemListRenderer

// 2. ItemListRenderer fetches job list
const { data: rawData } = useToolData("ml_list_finetuning_jobs");
// → { jobs: [{id, status, method, base_model, loss, ...}], count }

// 3. Each row renders:
//    - Status dot: maps $.status → color
//    - Title: $.base_model ("meta-llama/Llama-3.2-1B")
//    - Badge: method with color from filters.colors ("lora" in violet)
//    - Value: $.loss (0.42)

// 4. Method filter pills: lora | adalora | ia3 | prefix_tuning | full | mlx_lora

// 5. Detail tabs:
//    - "Job Details": callTool("ml_get_finetuning_job", { job_id: item.id })
//    - "Experiments": callTool("tracking_list_experiments", {})
```

### Step 6: Verify Data Flow

```python
# List — drives the item rows
jobs = ml_list_finetuning_jobs()
# → {"jobs": [{"id": "ft-...", "status": "completed", "method": "lora", "base_model": "meta-llama/Llama-3.2-1B", "loss": 0.42, ...}], "count": 1}

# Detail tab — job details
detail = ml_get_finetuning_job(job_id=job_id)
# → {"found": True, "id": "ft-...", "status": "completed", "method": "lora", "lora_rank": 8, ...}

# Experiments tab
exps = tracking_list_experiments()
# → {"experiments": [{"id": "...", "name": "lora-sweep"}], "count": 1}
```

## Success Criteria

- [ ] `ml_create_finetuning_job` + `ml_start_finetuning_job` produces a completed job
- [ ] `ml_list_finetuning_jobs` returns jobs with `loss` field populated
- [ ] Method filter pills render all 6 methods with correct colors
- [ ] Status dots reflect job status (emerald/red/blue/yellow)
- [ ] Job title shows `base_model`, badge shows `method`
- [ ] Detail tab "Job Details" shows full job info via `ml_get_finetuning_job`
- [ ] Detail tab "Experiments" lists experiments via `tracking_list_experiments`
- [ ] Gateway resolves `ml_get_views` without prefix mismatch

## API Reference

| Tool | Category | Key Args | Returns |
|------|----------|----------|---------|
| `ml_create_finetuning_job` | operational | `method, base_model, dataset_ref, lora_rank, ...` | `{id, status, method}` |
| `ml_start_finetuning_job` | operational | `job_id` | `{id, status, metrics, checkpoints}` |
| `ml_get_views` | deterministic | — | `[{id, components: [item_list]}]` |
| `ml_list_finetuning_jobs` | deterministic | — | `{jobs: [{id, status, method, loss, ...}], count}` |
| `ml_get_finetuning_job` | deterministic | `job_id` | `{found, id, status, method, lora_rank, ...}` |
| `tracking_create_experiment` | operational | `name, description` | `{id, name}` |
| `tracking_list_experiments` | deterministic | — | `{experiments: [{id, name}], count}` |
