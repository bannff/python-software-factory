# Kiro Sandbox Setup Workflow — Recipe

Kiro provisions a sandbox environment for a target app, verifies health,
and stores the SandboxEnv entity in graph for downstream SAST/DAST workflows.

## Context Variables

- `target_app`: e.g. idor_warehouse
- `run_id`: e.g. kiro-sandbox-warehouse-001
- `profile`: sandbox profile (webgoat, dvwa, vampi, juice_shop, idor_warehouse)

## Phase 1: Provision

Dispatch `security-engineer` sub-agent with `kiro-sandbox-setup` skill.
Agent provisions the profile-based container via `sandbox.provision`.

## Phase 2: Health Verification

Sub-agent polls the profile's health_check_url up to 5 times (10s intervals).
If health fails after all retries, workflow stops with error report.

## Phase 3: API Discovery

Sub-agent probes for OpenAPI/Swagger docs and enumerates available endpoints.
Discovered endpoints are included in the SandboxEnv graph entity.

## Phase 4: Graph Persistence

Sub-agent writes `SandboxEnv` entity to graph with:
- `env_id`, `profile`, `target_app`, `run_id`, `status`, `health_check_url`
- `discovered_endpoints` array

## Phase 5: Handoff

Sub-agent returns `env_id` and health status to orchestrator.
Downstream workflows (SAST, DAST) query the graph for the SandboxEnv entity:
```
call_brick_tool(brick_name="graph", tool_name="graph_find_entities",
  arguments='{"entity_type": "SandboxEnv", "properties": {"run_id": "{run_id}"}, "limit": 20}')
```

## Integration Points

- **DAST workflow**: reads `env_id` + `health_check_url` from SandboxEnv entity
- **SAST workflow**: can run independently (no sandbox needed for static analysis)
- **Recon workflow**: may provision sandbox for LocalStack-based infra replication
