# Recipe: Graph → Workflow Migration

Migrate (or author) an agent-brick registration to a SDK-native
`kind: workflow` shape backed by `strands_tools.workflow`. The
registry now treats `kind: graph` and `kind: workflow` as
first-class discriminated-union variants — not a partial migration
tail. Some registrations migrate, some stay graph by design.

## Bricks Used

- `agent` — Hosts SDK-native graph/workflow registrations for agent coordination
- `workflow` — Owns durable, retryable named-MCP execution for production workflows
- `dataset` — Owns CAN recipe execution, materialization, and provenance policy
- `machine_learning` — Owns native model lifecycles, passports, and promotion policy
- `evals` — Owns evaluation evidence

> **Scope:** `kind: workflow` below is an agent-brick registration backed by
> `strands_tools.workflow`. It is not the durable workflow-brick sequence added
> by `python-factory-sbhyq.10.1/.10.2`; do not use the agent executor as a
> substitute for durable state, evidence, retry/resume, or owning-brick policy.

## Prerequisites

- `strands-agents-tools==0.4.1` (exact-pinned; `_workflow_manager.py` overrides private SDK methods, so a minor bump is a breaking change)

## Migration Status

| Registration | Kind | Id | Factory key | bd |
|--------------|------|----|-----------:|----|
| SAST targeted (canary) | workflow | `rt-sast-scan` | `sast_targeted` | a4h7 ✅ |
| Recon | workflow | `recon-app` | `recon` | s5ev ✅ |
| Sandbox setup | workflow | `sandbox-setup` | `sandbox_setup` | m4cp ✅ |
| SAST open | workflow | `sast` | `sast_open` | c3hx ✅ |
| DAST open | workflow | `dast` | `dast_open` | vy9r ✅ |
| `redteam-pipeline` (meta) | graph (Option E) | `redteam-pipeline` | — | nrt5 ✅ |
| Hybrid arms (recon / sandbox / sast / idor) | graph | `rt-*-hybrid` | — | 2rc0 / 1nzr / lxku / i5yr ❌ obsolete |

**Why hybrids stay `kind=graph`** (bd-2rc0/1nzr/lxku/i5yr closed
obsolete after nrt5):

- Strands `WorkflowManager` tasks **cannot embed a Swarm**. The 4
  hybrid registrations are graph-of-2-agent-swarm-teams shapes —
  flattening them to sibling workflow tasks collapses the swarm
  layer.
- They are **azca experiment arms** (`graph` vs `swarm` vs `hybrid`
  vs `workflow` model-diversity comparison). Migrating any arm
  invalidates the experiment.
- Post-nrt5, `GraphExecutor.run` recursively dispatches nested
  `kind=workflow` leaves and `type=swarm` leaves through
  `SwarmNode` / `_build_nested_graph_node`. Hybrids exercise this
  path; they are not legacy.

## Variant Convention (open vs targeted)

When a workflow has both a single-class and a class-agnostic
shape, follow the `<purpose>_<variant>` factory-key convention:

- **Targeted** — keeps `vuln_class` in `context_vars`, prompt
  parameterized for one class. Factory key like `sast_targeted`.
  Used for GT-eval comparison runs.
- **Open** — drops `vuln_class`, prompt asks the agent to chain
  attacks across all 9 classes (IDOR / SQLi / XSS / SSRF / CSRF /
  Path-Traversal / Cmd-Injection / Deserialization / Mass-Assignment).
  Factory key like `sast_open`.

Both variants share the DAG topology — Strands `WorkflowManager` has
no conditional fan-out, so broader scope is owned by the **prompt**,
not the DAG shape.

## False-Promise Rule

Learned via bd-1v2t: a workflow registration's `description` must
not overstate what its skill stack delivers.

If you ship a multi-class workflow, the SKILL.md it activates must
be **class-agnostic**. For c3hx/vy9r, the meta-architect (memory
`f4d01009`) blocked the original design which loaded
`idor-code-scan` (an IDOR-specific 150-LOC playbook) as the SAST
"open" wedge — the registration would have promised cross-class
chaining while priming the model toward IDOR. bd-1v2t produced
`sast-open-scan` and `dast-open-scan` SKILL.md files (~285 LOC each,
9 vuln classes + PHASE 6 ATTACK CHAINING) to honour the promise.

Rule: **the registration description, factory key, and SKILL stack
must agree.** If you can't honestly describe what the skill stack
covers, fix the skill stack first.

## Steps

### Step 1: Author the factory function

Pure, deterministic over runtime context. Returns `list[dict]` of `WorkflowManager` tasks.

```python
# components/agent/src/factory/agent/registry/defaults_code_scan.py
def build_sast_targeted_tasks(vuln_class: str) -> list[dict]:
    return [
        _task("gptoss-sast", _SAST_PROMPT, _SCAN_TOOLS, GPT_OSS, [], 5, vuln_class),
        _task("sonnet-sast", _SAST_PROMPT, _SCAN_TOOLS, SONNET, [], 5, vuln_class),
        # downstream tasks declare `dependencies=[<task_id>, ...]`
        _task("validator", _VALIDATOR_PROMPT, _VALIDATOR_TOOLS, GLM5,
              ["consolidator"], 2, vuln_class),
    ]
```

For an **open** variant the factory takes no domain input and
returns a constant task list:

```python
# components/agent/src/factory/agent/registry/defaults_sast_open.py
def build_sast_open_tasks() -> list[dict]:
    return [
        _task("gptoss-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, GPT_OSS, [], 5),
        _task("sonnet-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, SONNET, [], 5),
        _task("glm5-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, GLM5, [], 5),
        # ... hierarchy-analyzer, consolidator, validator
    ]
```

### Step 2: Register the factory key

```python
# components/agent/src/factory/agent/registry/factories.py
FACTORY_REGISTRY: dict[str, FactoryFn] = {
    "sast_targeted": lambda ctx: build_sast_targeted_tasks(
        str(ctx.get("vuln_class", "")),
    ),
    "sast_open":     lambda ctx: build_sast_open_tasks(),
    "dast_open":     lambda ctx: build_dast_open_tasks(),
}
```

Keep the lambda thin — it just adapts runtime context to the factory's signature.

### Step 3: Author the registration as data

```python
SAST_TARGETED_REGISTRATION: dict = {
    "id": "rt-sast-scan",        # in-place migration kept its id
    "kind": "workflow",          # discriminator
    "factory": "sast_targeted",  # FACTORY_REGISTRY key, NOT a callable
    "name": "SAST Code Scan (Workflow)",
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": ["vuln_class", "target_app", "run_id"],
    "execution_timeout": 5400,
    "node_timeout": 1800,
}

SAST_OPEN_REGISTRATION = WorkflowConfig(
    id="sast",                   # NEW workflow → drop `rt-` prefix
    kind="workflow",
    factory="sast_open",
    name="SAST Open Scan (Workflow)",
    description=(
        "Open-scope SAST for {{target_app}}: 3 models scan in parallel; "
        "agent chains exploits across 9 vuln classes (IDOR/SQLi/XSS/"
        "SSRF/CSRF/Path-Traversal/Cmd-Injection/Deserialization/"
        "Mass-Assignment)."
    ),
    required_bricks=["graph", "security", "memory", "kb"],
    context_vars=["target_app", "run_id", "target_packages", "sast_workspace"],
    execution_timeout=5400,
    node_timeout=1800,
)
```

No callables in the dict — registrations stay JSON-serializable and
diffable. Naming: NEW kind=workflow registrations drop the `rt-`
prefix (`recon-app`, `sandbox-setup`, `sast`, `dast`). In-place
migrations like `rt-sast-scan` keep their original id for
consumer back-compat. Hybrids and other `kind=graph` registrations
keep the `rt-` prefix.

### Step 4: Invoke as before

The managed path (`runtime/managed_launch.py`) enrolls any `kind=graph`/`kind=workflow` registration as a Workflow-managed run via `launch_managed_graph`. No dispatch changes for new workflow-kind registrations; the MCP surface is unchanged.

```python
agent_invoke_graph(graph_id="rt-sast-scan", task="...",
                   context={"vuln_class": "IDOR", "target_app": "vampi", "run_id": "..."})

agent_invoke_graph(graph_id="sast", task="...",
                   context={"target_app": "vampi", "run_id": "..."})
```

## CAN Portfolio Parity and Deletion Gate

For `python-factory-sbhyq`, durable workflow migration follows this exact order:

`sbhyq.11 → sbhyq.8.3 → sbhyq.8.4 → sbhyq.8.8 → sbhyq.8.5 → sbhyq.10.1 → sbhyq.10.2 → sbhyq.8.7`

`.8.5` is the one portfolio-wide native conformance gate; `.8.6` is closed as
superseded and must not become a parallel matrix. For every supported family—
LightGBM, LSTM, TCN, PatchTST, `ncps.torch.LTC`, exact-pinned Chronos, and
supported MLX—the matrix must prove:

| Requirement | Evidence |
|---|---|
| Native training and serialization | Exact framework/backbone/revision pins and artifact digests |
| Cold load and restart | Fresh-process load with no warm registry or process-local dictionary authority |
| Inference parity | Warm vs cold predictions within the family contract tolerance |
| Contract authority | Dataset/feature/timespan contract and adapter descriptor match the passport |
| Tamper rejection | Digest, descriptor, revision, and contract mismatches fail closed |
| Promotion authority | Owning ML/evals policy accepts the immutable evidence bundle |

`.10.1` then supplies generic durable allowlisted named-MCP execution. Named steps
must opt in with `task_mode: named_mcp`; unannotated task steps continue through
the configured local/Celery/Dagster executor, including `task_options`, until
`.8.7`. A named run requires a caller-owned `run_key`; the bound workflow
snapshot plus canonical input derives its `wfr:v1:<sha256>` run ID, and reusing
the key with any different workflow/version/input/tenant fails closed.

Named MCP invocation is intentionally **at least once**, not exactly once.
Lease reclaim reuses the deterministic `wfa:v1:<sha256>` attempt ID as the
`ToolInvokerPort.idempotency_key`; owning tools must deduplicate committed
external effects by that key. The workflow journal fences stale lease writers,
but it cannot roll back an external effect after a process dies between tool
completion and journal commit.

`.10.2`
defines the Dataset → causal materialization → ML training → eval → passport →
cold conformance → promotion sequence as workflow data. **Do not delete any
legacy path under `.8.7` until every family passes `.8.5` and the end-to-end
workflow completes durably under `.10.2`.** Agents coordinate evidence; owning
bricks retain policy, and no direct cross-brick imports are permitted.

## Success Criteria

- [ ] `get_factory("<key>")` resolves without `KeyError`
- [ ] Registration round-trips through `json.dumps`/`json.loads`
- [ ] `agent_invoke_graph(graph_id=<id>)` emits `graph.launched` with `kind: "workflow"`
- [ ] `test_canary_sdk_method_names_present` passes (catches SDK private-method renames)
- [ ] For open variants: `test_<name>_open_no_vuln_class_in_prompts` passes (regression guard against `{{vuln_class}}` revival)
- [ ] For open variants: registration description is honest about what the skill stack actually covers (false-promise rule)
- [ ] For the CAN portfolio: `.8.5` records one complete seven-family native lifecycle matrix, including tamper and adapter-descriptor checks
- [ ] For the CAN portfolio: `.10.2` completes durably before `.8.7` deletes any legacy path

## API Reference

| Brick | Import | Key Symbols |
|-------|--------|-------------|
| agent | `factory.agent.registry.factories` | `FACTORY_REGISTRY`, `get_factory`, `known_factories` |
| agent | `factory.agent.executors.workflow` | `WorkflowExecutor` |
| agent | `factory.agent.executors._workflow_manager` | `make_factory_manager`, `build_parent_agent` |

## MCP Tools

| Tool | Brick | Description |
|------|-------|-------------|
| `agent_invoke_graph` | agent | Invokes a registered DAG by id; routes to `GraphExecutor` or `WorkflowExecutor` based on `kind` |
| `agent_invoke_graph_async` | agent | Async variant; same dispatch rules |
| `agent_get_workflow_status` | agent | Polls progress for either kind |
| `agent_get_graph_registry` | agent | Lists all registrations with `kind`, `factory`, and `context_vars`; how callers discover new `sast` / `dast` ids |

## SDK Gap Notes

`_workflow_manager.py::FactoryWorkflowManager` overrides two upstream private methods to work around SDK gaps (bd `python-factory-pfg3` plugin propagation, bd `python-factory-2gao` per-task timeout) plus `make_wf_id` (bd `python-factory-nrt5`) which namespaces `wf_id` by `graph_id` so nested workflows under the same outer `run_id` don't collide on `WorkflowManager` JSON state. This is the shape of the SDK-First "build it but document the gap" clause in `dev-principles.md`.

For nested composition (`redteam-pipeline` Option E), `_build_nested_graph_node` propagates `_mcp_tools` and `graph_registry` to child `GraphExecutor` instances — without that fix, nested workflows would silently lose ~80% of their tool surface (bd-nrt5 GAP-1).
