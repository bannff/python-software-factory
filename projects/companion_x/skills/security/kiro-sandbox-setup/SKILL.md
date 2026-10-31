---
name: kiro-sandbox-setup
description: Provisions sandbox environments using profile-based Docker containers. Configures the target app, verifies health, and prepares for DAST testing. Use when a running target is needed for dynamic security testing.
---

# Sandbox Setup

You provision and configure sandbox environments for downstream DAST workflows.
You have access to the control-plane runtime power for sandbox, graph, memory, and KB brick tools.

## Inputs (provided by orchestrator)

- `target_app`: e.g. idor_warehouse, webgoat, dvwa
- `run_id`: unique run identifier
- `profile`: sandbox profile name (e.g. "webgoat", "dvwa", "vampi", "juice_shop", "idor_warehouse")

## Mandatory Workflow

### Step 0 — Retrieve Prior Learnings
Check memory for prior sandbox setup issues, timeouts, or profile-specific quirks:
```
call_brick_tool(brick_name="memory", tool_name="memory_retrieve",
  arguments='{"query": "sandbox setup {profile} learnings", "user_id": "kiro-agent", "limit": 5}')
```

### Step 1 — List Available Profiles
Verify the requested profile exists before provisioning:
```
call_brick_tool(brick_name="sandbox", tool_name="sandbox.list_profiles",
  arguments='{}')
```
If the profile is not in the returned list, STOP and report the error.

### Step 2 — Provision the Target
Provision the sandbox using the profile. This auto-terminates any existing sandbox:
```
call_brick_tool(brick_name="sandbox", tool_name="sandbox.provision",
  arguments='{"profile": "{profile}"}')
```
Capture `env_id` from the response. If provisioning fails, STOP and report.

### Step 3 — Wait for Health Check
The profile defines a `health_check_url`. Poll it up to 5 times with 10s sleep:
```
for attempt in 1..5:
  call_brick_tool(brick_name="sandbox", tool_name="sandbox.execute",
    arguments='{"env_id": "{env_id}", "command": "curl -sf http://localhost:{port}{health_path} || echo HEALTH_FAIL"}')
  if stdout does NOT contain "HEALTH_FAIL" → health OK, break
  sleep 10s
```
Profile health endpoints:
| Profile | Port | Path |
|---------|------|------|
| webgoat | 8080 | /WebGoat |
| dvwa | 8080 | /login.php |
| vampi | 5050 | / |
| juice_shop | 3000 | / |
| idor_warehouse | 5050 | /health |

If all 5 attempts fail, STOP and report health check failure with last stdout/stderr.

### Step 4 — API Discovery
Verify the app is responding and discover available endpoints:
```
call_brick_tool(brick_name="sandbox", tool_name="sandbox.execute",
  arguments='{"env_id": "{env_id}", "command": "curl -sf http://localhost:{port}/openapi.json || curl -sf http://localhost:{port}/swagger.json || curl -sf http://localhost:{port}/api-docs || echo NO_DOCS"}')
```
Also try the root path and any profile-specific discovery paths.
Record discovered endpoints for the report.

### Step 5 — Store SandboxEnv in Graph
Persist the sandbox environment as a graph entity for downstream workflows:
```
call_brick_tool(brick_name="graph", tool_name="graph_add_entity",
  arguments='{"entity_id": "sandbox-{run_id}",
    "entity_type": "SandboxEnv",
    "properties": {
      "env_id": "{env_id}",
      "profile": "{profile}",
      "target_app": "{target_app}",
      "run_id": "{run_id}",
      "status": "healthy",
      "health_check_url": "http://localhost:{port}{health_path}",
      "discovered_endpoints": [...],
      "created_at": "{ISO timestamp}"
    }}')
```

### Step 6 — Store Learnings in Memory
```
call_brick_tool(brick_name="memory", tool_name="memory_store",
  arguments='{"content": "Sandbox setup {run_id}: provisioned {profile} for {target_app}, env_id={env_id}, health OK, discovered N endpoints",
    "user_id": "kiro-agent", "category": "fact",
    "tags": ["sandbox-setup", "{profile}", "{run_id}"]}')
```

### Step 7 — Report
Return to orchestrator:
```json
{
  "env_id": "<env_id>",
  "profile": "<profile>",
  "target_app": "<target_app>",
  "health_status": "healthy",
  "health_check_url": "http://localhost:<port><path>",
  "discovered_endpoints": ["..."],
  "run_id": "<run_id>"
}
```

## Grounding Rules
- NEVER report health as OK unless you received a successful curl response
- NEVER fabricate endpoint lists — only report what curl actually returned
- If provisioning or health fails, report the failure clearly with raw output
- The env_id MUST come from the sandbox.provision response, not invented
