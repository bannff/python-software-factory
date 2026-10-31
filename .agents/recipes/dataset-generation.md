# Recipe: Dataset Blueprint Materialization

Validate the first non-security frozen blueprint through named Dataset MCP, exact human approval, durable materialization, replay, and lineage resolution.

## Bricks Used
- `dataset` — Validates registered blueprint references and materializes immutable artifacts through the existing job pipeline

## Prerequisites
- the control-plane runtime running from the current checkout so the `dataset` brick and new named tools are registered
- Writable caller-owned storage root, such as `./.dataset_store`
- A valid ScenarioPack draft for the initial `scenario-generate` fixture
- Opaque quality-policy and exact human-approval records configured in the Dataset process environment
- The `the control-plane runtime` Kiro power activated for audited MCP calls

## Steps

### Step 1: Discover the named blueprint surface

```python
kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="get_brick_tools", arguments={"brick_name": "dataset"},
)
kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="get_brick_resources", arguments={"brick_name": "dataset"},
)
```

Confirm `dataset_validate_blueprint`, `dataset_materialize_blueprint`, and `dataset://schemas/blueprint` are present. If a long-lived the control-plane runtime process reports `Unknown brick: dataset` or lacks these names, restart it from the current checkout; do not substitute raw HTTP or direct imports.

### Step 2: Publish the source ScenarioPack

Call `dataset_publish_scenario_pack` with the non-security ScenarioPack draft and retain the returned `ref` (`identity`, `version`, `uri`, `digest`). Publication is immutable create-or-match; changed content under the same identity/version conflicts.

```python
pack = kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="call_brick_tool",
    arguments={
        "brick_name": "dataset",
        "tool_name": "dataset_publish_scenario_pack",
        "arguments": "<JSON containing the ScenarioPack draft and storage_root>",
    },
)
```

### Step 3: Build the exact initial blueprint and authority config

The initial registry accepts only this reference set; substitute the published ScenarioPack artifact ref and a registered opaque quality-policy ref:

```json
{
  "identity": "scenario-blueprint",
  "version": "1",
  "recipe": {"id": "scenario-generate", "version": "1", "digest": "5ffb0eac35e9d36555a29f9112ea1f4d63d25c9ef7ae2eb0df52176bfef0e88c"},
  "stages": [{"id": "scenario_generate", "version": "scenario-generate-1.0", "digest": "48de10b10d61e952d91d216800298052630edb59a19f94eac1b19a1935ed7825"}],
  "output_schema": {"id": "generic", "version": "1.0", "digest": "0e81870711c78f8e7dd66c562467358de8d14efb07c6f67a11076b88cc92c187"},
  "source_evidence": [{
    "id": "ScenarioPack",
    "version": "1",
    "digest": "c1c9ba02c5ceb40368b8b8364190cadeb6a301c364e111f6673293ea2e1f3979",
    "artifact": {"identity": "<pack-id>", "version": "<pack-version>", "uri": "<pack-uri>", "digest": "<pack-sha256>"}
  }],
  "capabilities": [{"id": "deterministic-template", "version": "1.0", "digest": "c49a33089d753f55a2674b6a21492befe9319f305eb7b8249837a2dbce8c42a7"}],
  "quality_policy": {"id": "scenario-quality", "revision": "1", "digest": "4c35d476c4a1fc8535b88f4b105ce1cc48777bd6d006a9f89c224d0d03ee956a"},
  "generation_seed": 41,
  "requested_views": ["default"]
}
```

Canonicalize with compact key-sorted UTF-8 JSON (`separators=(",", ":")`, `ensure_ascii=false`, `allow_nan=false`) and SHA-256 it. Configure the the control-plane runtime/Dataset process with JSON arrays:

```bash
export DATASET_QUALITY_POLICY_REFS_JSON='[{"id":"scenario-quality","revision":"1","digest":"4c35d476c4a1fc8535b88f4b105ce1cc48777bd6d006a9f89c224d0d03ee956a"}]'
export DATASET_HUMAN_APPROVALS_JSON='[{"id":"approval-41","revision":"1","blueprint_digest":"<canonical-blueprint-sha256>","quality_policy":{"id":"scenario-quality","revision":"1","digest":"4c35d476c4a1fc8535b88f4b105ce1cc48777bd6d006a9f89c224d0d03ee956a"}}]'
```

The MCP `approval_digest` argument is the SHA-256 of the canonical approval record above. Approval is an exact `(id, revision, digest)` reference bound to both blueprint digest and policy; no boolean approval is accepted. Both registries default to `[]` and fail closed.

### Step 4: Validate, then materialize through named MCP

```python
validated = kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="call_brick_tool",
    arguments={
        "brick_name": "dataset", "tool_name": "dataset_validate_blueprint",
        "arguments": "{\"blueprint_json\":\"<escaped-canonical-blueprint-json>\",\"storage_root\":\"./.dataset_store\"}",
    },
)
submitted = kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="call_brick_tool",
    arguments={
        "brick_name": "dataset", "tool_name": "dataset_materialize_blueprint",
        "arguments": "{\"blueprint_json\":\"<escaped-canonical-blueprint-json>\",\"approval_id\":\"approval-41\",\"approval_revision\":\"1\",\"approval_digest\":\"<canonical-approval-sha256>\",\"storage_root\":\"./.dataset_store\"}",
    },
)
```

Validation must return `status=validated`, recipe URI `recipe://local/scenario-generate@1`, and stage names `['scenario_generate']` without writing. Materialization returns `status=queued`, a content-addressed blueprint ref, and `job_id`. The resulting generation request carries the exact immutable approval binding (approval ref + approved blueprint digest + opaque policy ref); the manifest must preserve the same binding.

### Step 5: Poll, fetch, and resolve

Poll `dataset_get_job` with the returned job ID and the same `storage_root` until `completed`; then call `dataset_get_artifact` and `dataset_resolve_artifact`. The named acceptance test invokes all three through `fastmcp.Client.call_tool`; it does not substitute direct Python interface calls. Verify the manifest's exact approval binding, `blueprint_binding`, and `blueprint_lineage` preserve the policy, ScenarioPack source, recipe, ordered stage, generic schema, and deterministic-template capability.

### Step 6: Verify replay and conflict behavior

Repeat `dataset_materialize_blueprint` with the identical blueprint and approval. It must return the same job and artifact. Then change `generation_seed` while retaining the same identity/version and use a separately digest-bound approval: publication is serialized by identity/version, so the losing call must return `status=conflict` without creating orphan content, job, or artifact effects.

## Success Criteria
- [ ] Blueprint schema rejects extra or executable validator/evaluator/import/callable/script/command/promotion fields
- [ ] `dataset_validate_blueprint` is write-free and validates every reference fail-closed
- [ ] Materialization requires an exact policy-bound and blueprint-digest-bound approval reference
- [ ] Generic public/MCP submission rejects unbound `scenario-generate@1` requests before job or worker effects; unrelated legacy recipes remain compatible
- [ ] Named MCP completes validate → materialize → poll → artifact → resolve, with status/artifact/resolve all invoked through `Client.call_tool`
- [ ] Manifest records the exact approval binding plus blueprint and policy/source/recipe/stage/schema/capability lineage
- [ ] Exact replay returns the same job/artifact; divergent identity/version reuse conflicts before effects
- [ ] No security/CAN branch, evaluator execution, training, promotion, or correction loop is implied

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| `dataset` | MCP via `call_brick_tool` | `dataset_validate_blueprint`, `dataset_materialize_blueprint`, `dataset_get_job`, `dataset_get_artifact`, `dataset_resolve_artifact` |

## MCP Tools

| Tool | Brick | Description |
|------|-------|-------------|
| `dataset_publish_scenario_pack` | `dataset` | Publish immutable source evidence |
| `dataset_validate_blueprint` | `dataset` | Write-free contract and registry validation |
| `dataset_materialize_blueprint` | `dataset` | Human-gated submission through the existing job pipeline |
| `dataset_get_job` | `dataset` | Poll durable job status |
| `dataset_get_artifact` | `dataset` | Fetch the immutable artifact reference |
| `dataset_resolve_artifact` | `dataset` | Resolve exact manifest lineage |

This is only Dataset's human-gated materialization seam, not a complete generate → evaluate → revise loop. Evals and Workflow are not invoked by this slice. `python-factory-9mz1j.3` owns policy semantics, evaluator execution, reports, deficiencies, acceptance, and promotion; `python-factory-9mz1j.4` owns durable attempts, global budgets, retries, cancellation, recovery, stopping, and correction rounds. Bead `python-factory-9mz1j.2` remains open because this Dataset-only slice does not satisfy its full generate → evaluate → revise acceptance criterion.
