# Foreman

Foreman provides Polylith scaffolding, workspace structure management, and repository governance through its MCP surface. It keeps these operations at a typed boundary so clients can safely discover the workspace, validate compliance, and make repeatable structural changes.

## MCP contract

All 14 public FastMCP tools retain **flat keyword arguments** and validate ingress with strict, Foreman-local Pydantic v2 DTOs (`extra="forbid"`). Each returns a `ToolResult[OutputDTO]` envelope:

```json
{"schema_version":"v1","ok":true,"data":{},"error":null,"idempotency_key":null}
```

Check `result.ok` before consuming a response. On success, read the typed payload from `result.data`; when `ok` is false, `data` is null and `error` explains the failure. Normal domain outcomes remain typed data rather than envelope failures.

## Public tools

### Deterministic (9)

| Tool | Purpose |
| --- | --- |
| `get_capabilities` | Return Foreman features and its MCP catalog. |
| `health_check` | Report Foreman service health. |
| `describe_config_schema` | Describe Foreman's configuration schema. |
| `foreman_info` | Inspect workspace information. |
| `foreman_check` | Run the Polylith structural check. |
| `foreman_guardian_check` | Run repository governance and compliance checks. |
| `foreman_get_repo_guardrails` | Return repository workflow and governance guardrails. |
| `foreman_build_bricks_index` | Build the derived brick index without writing it. |
| `foreman_resolve_dependencies` | Resolve dependencies for selected bricks. |

### Operational (5)

| Tool | Purpose |
| --- | --- |
| `foreman_create_component` | Create a Polylith component. |
| `foreman_create_base` | Create a Polylith base. |
| `foreman_write_bricks_index` | Write the derived brick index. |
| `foreman_create_project` | Create a project from selected bricks. |
| `foreman_sync_brick_deps` | Synchronize project brick dependencies. |

## Related contracts

- [BRICK.yaml](BRICK.yaml) is the machine-readable Foreman catalog, including resources and prompts.
- [MCP Tool Patterns](../../.agents/steering/mcp-tools.md) defines the factory-wide typed-boundary and result-envelope rules.
