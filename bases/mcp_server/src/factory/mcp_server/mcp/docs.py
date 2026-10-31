"""Documentation for the MCP aggregator server."""

AGGREGATOR_OVERVIEW = """
# MCP Aggregator Server

The MCP Aggregator provides one progressive MCP interface to every enabled brick
in the Python Factory workspace. Clients discover and invoke brick capabilities
through a fixed ten-tool core surface instead of loading every brick tool upfront.

## Core Progressive Surface

Nine core tools use strict same-base Pydantic v2 DTO ingress and
`ToolResult[OutputDTO]` egress: `get_capabilities`, `health_check`,
`list_bricks`, `get_brick_tools`, `get_brick_resources`, `get_brick_prompts`,
`get_tool_catalog`, `read_brick_resource`, and `render_brick_prompt`.

`call_brick_tool` also has strict DTO ingress and preserves the invoked tool's
native MCP v2 result or task payload without adding an incompatible outer
envelope.

## Benefits

- **Single Connection**: One server instead of many
- **Progressive Discovery**: Load only the brick schemas a client needs
- **Aggregated Health**: Status across all bricks
- **Complete Catalog**: Opt into server-side eager loading with `get_tool_catalog`
"""

BRICKS_DISCOVERY = """
# Brick Discovery

The aggregator reads `BRICKS_INDEX.yaml` to find MCP-enabled bricks. In
progressive mode, `list_bricks` reports registered bricks and an unloaded brick
has `tools_count: -1`. Call `get_brick_tools(brick_name)` to load that brick and
retrieve its exact tool schemas.

## Discovery Process

1. Call `list_bricks` to identify registered bricks
2. Call `get_brick_tools`, `get_brick_resources`, or `get_brick_prompts` for a brick
3. Invoke a discovered tool with `call_brick_tool`
4. Use `get_tool_catalog` only when a complete, eagerly loaded registry is required;
   load failures are returned in `bricks_failed`

## Adding New Bricks

1. Create the brick with `mcp_enabled: true` in `BRICK.yaml`
2. Run `foreman_write_bricks_index`
3. Restart the aggregator
"""

CONFIGURATION_GUIDE = """
# Configuration

Configure via environment variables and config files.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_ROOT` | `.` | Workspace root path |
| `MCP_HOST` | `localhost` | Server bind address |
| `MCP_PORT` | `8000` | Server port |
| `MCP_LOG_LEVEL` | `INFO` | Logging verbosity |
| `MCP_DISCOVERY_MODE` | `progressive` | `progressive` exposes the core surface; `flat` mounts included brick tools |

## Config File (`config/mcp_server.yaml`)

```yaml
server:
  host: localhost
  port: 8000

discovery:
  index_path: BRICKS_INDEX.yaml
```
"""

USAGE_GUIDE = """
# Usage Guide

Use the progressive surface rather than assuming every brick tool is registered
at connection time.

## Discover and Invoke

```python
bricks = await client.call_tool("list_bricks", {})
schemas = await client.call_tool("get_brick_tools", {"brick_name": "cache"})
result = await client.call_tool(
    "call_brick_tool",
    {"brick_name": "cache", "tool_name": "cache_get", "arguments": '{"key":"my-key"}'},
)
```

For the nine `ToolResult` tools, inspect `ok` and consume successful data from
`data`. `call_brick_tool` is different by design: consume the invoked tool's
native envelope or task payload directly; do not expect an outer `ToolResult`.

## Checking Health

- Aggregated: `health_check`
- Per brick: discover the brick, then invoke its health tool through `call_brick_tool`
"""

DOCS = {
    "overview": AGGREGATOR_OVERVIEW,
    "bricks": BRICKS_DISCOVERY,
    "configuration": CONFIGURATION_GUIDE,
    "usage": USAGE_GUIDE,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
